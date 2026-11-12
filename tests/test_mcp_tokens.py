"""The MCP tokens: created in the web UI, stored as a hash, shown once."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.mcp_server.scopes import Scope
from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings


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
    assert client.get("/api/mcp-tokens").status_code == 401
    assert client.post("/api/mcp-tokens", json={"name": "x", "scopes": ["rules:read"]}).status_code == 401
    assert client.get("/api/mcp-tokens/scopes").status_code == 401
# end def


def test_token_is_shown_once_and_only_the_hash_is_stored(client: TestClient) -> None:
    created = client.post("/api/mcp-tokens", json={"name": "claude", "scopes": ["rules:write", "rules:read", "rules:read"]})
    assert created.status_code == 201
    body = created.json()
    token = body["token"]
    assert token.startswith("rimr_") and body["prefix"] == token[:8]
    assert body["scopes"] == ["rules:read", "rules:write"]
    listed = client.get("/api/mcp-tokens").json()
    assert [row["id"] for row in listed] == [body["id"]]
    assert "token" not in listed[0]
    assert token not in client.get("/api/mcp-tokens").text
# end def


def test_unknown_scope_is_rejected(client: TestClient) -> None:
    assert client.post("/api/mcp-tokens", json={"name": "x", "scopes": ["rules:x"]}).status_code == 422
    assert client.post("/api/mcp-tokens", json={"name": "x", "scopes": []}).status_code == 422
# end def


def test_scope_list_has_every_scope_and_presets(client: TestClient) -> None:
    data = client.get("/api/mcp-tokens/scopes").json()
    assert data["scopes"] == [scope.value for scope in Scope]
    assert set(data["presets"]) == {"read_only", "rules_editor", "everything"}
# end def


def test_revoke(client: TestClient) -> None:
    token_id = client.post("/api/mcp-tokens", json={"name": "claude", "scopes": ["rules:read"]}).json()["id"]
    assert client.delete(f"/api/mcp-tokens/{token_id}").status_code == 204
    assert client.get("/api/mcp-tokens").json()[0]["revoked_at"] is not None
    assert client.delete("/api/mcp-tokens/6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11").status_code == 404
# end def
