"""The admin's settings in the database, shared by every browser."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings

DEFAULTS = {"cache_unread": True, "cache_opened_unread": True, "cache_inbox": True, "cache_inbox_count": 200, "cache_max_age_days": 30, "auto_read": "off"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None, rules_path=None, data_dir=tmp_path / "data", database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing", watch_enabled=False,
        secret_key=SecretStr(Fernet.generate_key().decode()), admin_username="admin", admin_password=SecretStr("admin-secret"),
    )
    with TestClient(create_app(settings)) as test_client:
        test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        yield test_client
    # end with
# end def


def test_needs_login(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/settings").status_code == 401
    assert client.put("/api/settings", json=DEFAULTS).status_code == 401
# end def


def test_defaults_then_saved_values_for_every_client(client: TestClient) -> None:
    assert client.get("/api/settings").json() == DEFAULTS
    changed = {"cache_unread": False, "cache_opened_unread": True, "cache_inbox": False, "cache_inbox_count": 50, "cache_max_age_days": 0, "auto_read": "scrolled"}
    assert client.put("/api/settings", json=changed).json() == changed
    assert client.get("/api/settings").json() == changed
    # The row is kept, a second save updates it.
    assert client.put("/api/settings", json={**changed, "cache_inbox_count": 10}).json()["cache_inbox_count"] == 10
# end def


@pytest.mark.parametrize("field,value", [("cache_inbox_count", -1), ("cache_max_age_days", -5), ("cache_inbox", "maybe"), ("auto_read", "always")])
def test_invalid_values_are_rejected(client: TestClient, field: str, value: object) -> None:
    assert client.put("/api/settings", json={**DEFAULTS, field: value}).status_code == 422
# end def
