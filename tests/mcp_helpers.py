"""A server with a rules file and a tiny JSON-RPC client for `/mcp`, shared by the MCP tests."""

import json
from collections.abc import Iterator
from itertools import count
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings

ACCOUNT = "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11"
RULES = f"""# my rules
rules:
  - name: One
    locations:
      - account_id: {ACCOUNT}
    when:
      type: bool
      field: seen
    actions:
      - type: mark_read
"""
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
ids = count(1)


def make_client(tmp_path: Path, rules_path: Path | None = None) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None, rules_path=rules_path, data_dir=tmp_path / "data", database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing", watch_enabled=False,
        secret_key=SecretStr(Fernet.generate_key().decode()), admin_username="admin", admin_password=SecretStr("admin-secret"),
    )
    with TestClient(create_app(settings)) as client:
        client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        yield client
    # end with
# end def


def new_token(client: TestClient, scopes: list[str], name: str = "test") -> str:
    created = client.post("/api/mcp-tokens", json={"name": name, "scopes": scopes})
    assert created.status_code == 201, created.text
    return str(created.json()["token"])
# end def


def rpc(client: TestClient, token: str | None, method: str, params: dict[str, Any] | None = None) -> Any:
    headers = dict(HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    # end if
    response = client.post("/mcp", headers=headers, content=json.dumps({"jsonrpc": "2.0", "id": next(ids), "method": method, "params": params or {}}))
    return response
# end def


def call(client: TestClient, token: str, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """The `result` of a `tools/call`: `isError`, `content` and `structuredContent`."""
    response = rpc(client, token, "tools/call", {"name": name, "arguments": arguments or {}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "result" in body, body
    return dict(body["result"])
# end def


def text_of(result: dict[str, Any]) -> str:
    return "".join(part.get("text", "") for part in result["content"])
# end def


def tool_names(client: TestClient, token: str) -> set[str]:
    body = rpc(client, token, "tools/list").json()
    return {tool["name"] for tool in body["result"]["tools"]}
# end def


@pytest.fixture
def rules_file(tmp_path: Path) -> Path:
    path = tmp_path / "rules.yml"
    path.write_text(RULES)
    return path
# end def
