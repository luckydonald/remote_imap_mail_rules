"""The login that gates the whole API."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, SESSION_SECONDS
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.test_server_accounts import BODY, KEY, make_env

LOGIN = {"username": "me@example.com", "password": "secret"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None,
        rules_path=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(KEY),
    )
    with TestClient(create_app(settings, make_env())) as test_client:
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


def test_login_with_any_account_and_logout(client: TestClient) -> None:
    client.post("/api/auth/login", json=LOGIN).raise_for_status()
    assert SESSION_COOKIE in client.cookies
    assert client.get("/api/auth/me").status_code == 204
    assert client.get("/api/editor/config").status_code == 200
    # A second account with other credentials works as well.
    other = {"username": "other@example.com", "password": "other-secret"}
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    client.post("/api/auth/login", json=LOGIN)
    client.post("/api/accounts", json={**BODY, **other}).raise_for_status()
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json=other).status_code == 204
# end def


@pytest.mark.parametrize("body", [{"username": "me@example.com", "password": "wrong"}, {"username": "nobody", "password": "secret"}])
def test_wrong_credentials(client: TestClient, body: dict[str, str]) -> None:
    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 401
    assert SESSION_COOKIE not in client.cookies
    assert "secret" not in response.text
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


def test_without_secret_key_login_is_503(tmp_path: Path) -> None:
    settings = ServerSettings(_env_file=None, rules_path=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}", frontend_dist=tmp_path / "missing")
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/auth/login", json=LOGIN).status_code == 503
        assert client.get("/api/editor/config").status_code == 503
    # end with
# end def
