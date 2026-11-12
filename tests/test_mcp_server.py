"""The `/mcp` endpoint: bearer tokens, scopes, and the tools over real JSON-RPC."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from .mcp_helpers import ACCOUNT, RULES, call, make_client, new_token, rpc, rules_file, text_of, tool_names  # noqa: F401


@pytest.fixture
def client(tmp_path: Path, rules_file: Path) -> Iterator[TestClient]:
    yield from make_client(tmp_path, rules_file)
# end def


def test_initialize_needs_a_valid_token(client: TestClient) -> None:
    assert rpc(client, None, "initialize").status_code == 401
    assert rpc(client, "rimr_nope", "initialize").status_code == 401
    token = new_token(client, ["rules:read"])
    response = rpc(client, token, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
    assert response.status_code == 200, response.text
    assert response.json()["result"]["serverInfo"]["name"] == "remote_imap_mail_rules"
    # Both spellings of the path work without a redirect.
    assert client.post("/mcp/", headers={"Authorization": "Bearer x"}, json={}).status_code == 401
# end def


def test_revoked_token_stops_working(client: TestClient) -> None:
    token = new_token(client, ["rules:read"])
    assert rpc(client, token, "tools/list").status_code == 200
    token_id = client.get("/api/mcp-tokens").json()[0]["id"]
    client.delete(f"/api/mcp-tokens/{token_id}")
    assert rpc(client, token, "tools/list").status_code == 401
# end def


def test_tools_list_follows_the_scopes(client: TestClient) -> None:
    read = tool_names(client, new_token(client, ["rules:read"]))
    assert {"list_rules", "get_rule", "get_rules_yaml", "dry_run"} <= read
    assert not read & {"create_rule", "delete_rule", "list_accounts", "list_events", "get_account_password"}
    everything = tool_names(client, new_token(client, [s["value"] if isinstance(s, dict) else s for s in client.get("/api/mcp-tokens/scopes").json()["scopes"]]))
    assert {"create_rule", "delete_rule", "list_accounts", "get_account_password", "set_account_password", "clear_events", "list_folders"} <= everything
    assert tool_names(client, new_token(client, ["folders:write", "mails:read"])) == set()
# end def


def test_a_tool_without_its_scope_is_refused(client: TestClient) -> None:
    token = new_token(client, ["rules:read"])
    result = call(client, token, "delete_rule", {"name": "One"})
    assert result["isError"] is True and "rules:delete" in text_of(result)
    assert "One" in client.get("/api/editor/rules").text
# end def


def test_read_tools(client: TestClient) -> None:
    token = new_token(client, ["rules:read"])
    assert text_of(call(client, token, "get_rules_yaml")) == RULES
    listed = call(client, token, "list_rules")["structuredContent"]["rules"]
    assert listed[0]["name"] == "One" and listed[0]["actions"] == ["mark_read"]
    assert call(client, token, "get_rule", {"name": "One"})["structuredContent"]["name"] == "One"
    assert call(client, token, "validate_rules_yaml", {"yaml": RULES})["structuredContent"] == {"valid": True, "messages": []}
    bad = call(client, token, "validate_rules_yaml", {"yaml": "rules: [{name: x}]"})["structuredContent"]
    assert bad["valid"] is False and bad["messages"]
    assert "properties" in call(client, token, "get_rules_schema")["structuredContent"]
    assert call(client, token, "get_rule", {"name": "Nope"})["isError"] is True
# end def


def test_edits_save_and_keep_comments(client: TestClient, rules_file: Path) -> None:
    token = new_token(client, ["rules:read", "rules:write", "rules:delete"])
    created = call(client, token, "create_rule", {"rule": {
        "name": "Two", "locations": [{"account_id": ACCOUNT}], "when": {"type": "bool", "field": "flagged"}, "actions": [{"type": "mark_read"}],
    }})
    assert created["structuredContent"] == {"index": 1}
    call(client, token, "add_condition", {"rule": "Two", "path": [], "condition": {"type": "bool", "field": "seen"}}) 
    assert call(client, token, "wrap_condition", {"rule": "Two", "path": [], "combinator": "all"})["isError"] is False
    assert call(client, token, "add_condition", {"rule": "Two", "path": [], "condition": {"type": "bool", "field": "seen"}})["isError"] is False
    assert call(client, token, "set_rule_enabled", {"name": "One", "enabled": False})["isError"] is False
    text = rules_file.read_text()
    assert text.startswith("# my rules") and "enabled: false" in text and "name: Two" in text
    assert call(client, token, "delete_rule", {"name": "Two"})["isError"] is False
    assert "Two" not in rules_file.read_text()
# end def


def test_an_invalid_edit_changes_nothing(client: TestClient, rules_file: Path) -> None:
    token = new_token(client, ["rules:read", "rules:write"])
    result = call(client, token, "update_rule", {"name": "One", "changes": {"when": {"type": "bool", "field": "nonsense"}}})
    assert result["isError"] is True and "nothing was saved" in text_of(result)
    result = call(client, token, "save_rules_yaml", {"yaml": "rules: nope"})
    assert result["isError"] is True
    assert rules_file.read_text() == RULES
# end def


def test_save_rules_yaml(client: TestClient, rules_file: Path) -> None:
    token = new_token(client, ["rules:write"])
    new = RULES.replace("One", "Renamed")
    assert call(client, token, "save_rules_yaml", {"yaml": new})["isError"] is False
    assert rules_file.read_text() == new
# end def
