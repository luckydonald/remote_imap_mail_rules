"""The login that gates the whole API."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, SESSION_SECONDS
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.test_server_accounts import BODY, KEY, make_env

LOGIN = {"username": "admin", "password": "admin-secret"}


def make_settings(tmp_path: Path, **values: Any) -> ServerSettings:
    values.setdefault("secret_key", SecretStr(KEY))
    values.setdefault("admin_username", "admin")
    values.setdefault("admin_password", SecretStr("admin-secret"))
    return ServerSettings(
        _env_file=None, rules_path=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}", frontend_dist=tmp_path / "missing", **values
    )
# end def


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings(tmp_path), make_env())) as test_client:
        yield test_client
    # end with
# end def


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/editor/config"), ("get", "/api/editor/rules"), ("put", "/api/editor/rules"), ("get", "/api/accounts"), ("post", "/api/accounts")],
)
def test_api_needs_login(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
# end def


def test_every_route_but_auth_is_protected(client: TestClient) -> None:
    """A router added later without the dependency would show up here."""
    paths: dict[str, dict[str, object]] = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    checked = 0
    for path, methods in paths.items():
        if path.startswith(("/api/auth/", "/api/public/")):
            continue
        # end if
        for method in methods:
            url = path.replace("{account_id}", "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11")
            assert client.request(method, url).status_code == 401, f"{method} {path}"
            checked += 1
        # end for
    # end for
    assert checked >= 5
# end def


def test_login_and_logout(client: TestClient) -> None:
    client.post("/api/auth/login", json=LOGIN).raise_for_status()
    assert SESSION_COOKIE in client.cookies
    assert client.get("/api/auth/me").status_code == 204
    assert client.get("/api/editor/config").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
# end def


@pytest.mark.parametrize(
    "body",
    [
        {"username": "admin", "password": "wrong"},
        {"username": "nobody", "password": "admin-secret"},
        # The credentials of the stored mail account do not unlock the service.
        {"username": "me@example.com", "password": "secret"},
    ],
)
def test_wrong_credentials(client: TestClient, body: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("remote_imap_mail_rules.server.auth.FAILED_LOGIN_DELAY", 0)
    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 401
    assert SESSION_COOKIE not in client.cookies
    assert "secret" not in response.text
# end def


def test_changing_the_admin_password_ends_the_sessions(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path))) as first:
        first.post("/api/auth/login", json=LOGIN).raise_for_status()
        cookie = first.cookies[SESSION_COOKIE]
    # end with
    with TestClient(create_app(make_settings(tmp_path))) as same:
        same.cookies.set(SESSION_COOKIE, cookie)
        assert same.get("/api/auth/me").status_code == 204
    # end with
    with TestClient(create_app(make_settings(tmp_path, admin_password=SecretStr("changed")))) as changed:
        changed.cookies.set(SESSION_COOKIE, cookie)
        assert changed.get("/api/auth/me").status_code == 401
    # end with
# end def


def test_works_without_any_mail_account(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path))) as client:
        client.post("/api/auth/login", json=LOGIN).raise_for_status()
        assert client.get("/api/accounts").json() == []
    # end with
# end def


def test_forged_and_expired_tokens(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.cookies.set(SESSION_COOKIE, Fernet(Fernet.generate_key()).encrypt(b"logged-in").decode())
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    client.post("/api/auth/login", json=LOGIN)
    assert client.get("/api/auth/me").status_code == 204
    real_time = __import__("time").time
    monkeypatch.setattr("time.time", lambda: real_time() + SESSION_SECONDS + 10)
    assert client.get("/api/auth/me").status_code == 401
# end def


def test_cookie_is_httponly(client: TestClient) -> None:
    header = client.post("/api/auth/login", json=LOGIN).headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header
# end def


@pytest.mark.parametrize("missing", [{"secret_key": None}, {"admin_username": None}, {"admin_password": None}])
def test_without_secret_key_or_admin_login_is_503(tmp_path: Path, missing: dict[str, None]) -> None:
    with TestClient(create_app(make_settings(tmp_path, **missing))) as client:
        assert client.post("/api/auth/login", json=LOGIN).status_code == 503
        assert client.get("/api/editor/config").status_code == 503
    # end with
# end def
