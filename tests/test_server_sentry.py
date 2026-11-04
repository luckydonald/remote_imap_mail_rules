"""Error reporting: off without a DSN, the release chain, and what the browser is told."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server import app as app_module
from remote_imap_mail_rules.server import sentry
from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.test_server_accounts import KEY, make_env
from tests.test_server_auth import LOGIN

DSN = "http://public@bugsink.example.com/1"


def make_settings(tmp_path: Path, **values: Any) -> ServerSettings:
    return ServerSettings(
        _env_file=None,
        rules_path=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(KEY), admin_username="admin", admin_password=SecretStr("admin-secret"),
        **values,
    )
# end def


@pytest.fixture
def no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sentry, "git_output", lambda *args: "")
# end def


def test_release_prefers_override_then_source_commit_then_git_then_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sentry, "git_output", lambda *args: "from-git")
    assert sentry.release_of(make_settings(tmp_path, sentry_release="v1", source_commit="abc")) == "v1"
    assert sentry.release_of(make_settings(tmp_path, source_commit="abc")) == "abc"
    assert sentry.release_of(make_settings(tmp_path)) == "from-git"
    monkeypatch.setattr(sentry, "git_output", lambda *args: "")
    assert sentry.release_of(make_settings(tmp_path)) == "unknown"
# end def


def test_frontend_falls_back_to_the_backend(tmp_path: Path, no_git: None) -> None:
    settings = make_settings(tmp_path, sentry_environment="production", source_commit="abc")
    assert sentry.frontend_release_of(settings) == "abc"
    assert sentry.frontend_environment_of(settings) == "production"
    settings = make_settings(tmp_path, sentry_environment="production", vite_sentry_environment="staging", vite_sentry_release="web-1")
    assert sentry.frontend_release_of(settings) == "web-1"
    assert sentry.frontend_environment_of(settings) == "staging"
# end def


def test_init_does_nothing_without_a_dsn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    assert sentry.init_sentry(make_settings(tmp_path)) is False
    assert calls == []
# end def


def test_init_passes_the_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_git: None) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(sentry.sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(sentry.sentry_sdk, "set_tag", lambda *args: None)
    settings = make_settings(tmp_path, sentry_dsn=DSN, sentry_environment="production", source_commit="abc", sentry_traces_sample_rate=0.5)
    assert sentry.init_sentry(settings) is True
    assert calls[0]["dsn"] == DSN
    assert calls[0]["environment"] == "production"
    assert calls[0]["release"] == "abc"
    assert calls[0]["traces_sample_rate"] == 0.5
    assert calls[0]["send_default_pii"] is False
# end def


def test_client_config_is_off_without_a_frontend_dsn(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path, sentry_dsn=DSN), make_env())) as client:
        assert client.get("/api/public/client-config").json() == {"sentry": None}
    # end with
# end def


def test_client_config_needs_no_login(tmp_path: Path, no_git: None) -> None:
    settings = make_settings(tmp_path, vite_sentry_dsn=DSN, sentry_environment="production", source_commit="abc", vite_sentry_traces_sample_rate=0.25)
    with TestClient(create_app(settings, make_env())) as client:
        assert client.get("/api/public/client-config").json() == {
            "sentry": {"dsn": DSN, "environment": "production", "release": "abc", "traces_sample_rate": 0.25}
        }
    # end with
# end def


def test_health_needs_no_login(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path), make_env())) as client:
        assert client.get("/api/public/health").json() == {"status": "ok"}
    # end with
# end def


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings(tmp_path), make_env()), raise_server_exceptions=False) as test_client:
        yield test_client
    # end with
# end def


def test_sample_error_needs_login_and_then_fails(client: TestClient) -> None:
    assert client.get("/api/sample-error").status_code == 401
    assert client.post("/api/auth/login", json=LOGIN).status_code == 204
    assert client.get("/api/sample-error").status_code == 500
# end def


def test_failing_start_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reported: list[BaseException] = []

    async def broken(database_url: str) -> None:
        raise RuntimeError("migration failed")
    # end def

    monkeypatch.setattr(app_module, "upgrade", broken)
    monkeypatch.setattr(app_module, "report_startup_failure", reported.append)
    with pytest.raises(RuntimeError, match="migration failed"):
        with TestClient(create_app(make_settings(tmp_path), make_env())):
            pass
        # end with
    # end with
    assert [str(e) for e in reported] == ["migration failed"]
# end def
