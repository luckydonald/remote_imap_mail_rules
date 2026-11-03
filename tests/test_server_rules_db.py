"""Database mode: rules stored as rows, behind the same editor endpoints."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from cryptography.fernet import Fernet

from remote_imap_mail_rules.rules.loader import parse_rules
from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.test_server import INVALID_SCHEMA, INVALID_YAML, VALID

ACCOUNT = "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11"

WITH_TEMPLATE = f"""templates:
  from-sender: &from-sender
    type: template
    defaults:
      domain: example.com
    content:
      type: address
      field: from
      part: domain
      operator: equals
      value: !var domain
rules:
  - name: One
    locations:
      - account_id: {ACCOUNT}
    when:
      <<: *from-sender
      variables:
        domain: news.example.org
    actions:
      - type: move
        folder: News
  - name: Two
    enabled: false
    locations:
      - account_id: {ACCOUNT}
        folder: Archive
        recursive: true
    when:
      <<: *from-sender
    actions: []
"""


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None,
        rules_path=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(Fernet.generate_key().decode()),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
    # end with
# end def


def test_empty_database(client: TestClient) -> None:
    assert client.get("/api/editor/config").json() == {"mode": "server", "source": "database", "file_name": None, "exists": False}
    assert client.get("/api/editor/rules").status_code == 404
# end def


def test_save_and_read_back(client: TestClient) -> None:
    assert client.put("/api/editor/rules", content=VALID).status_code == 204
    assert client.get("/api/editor/config").json()["exists"] is True
    text = client.get("/api/editor/rules").text
    assert parse_rules(text) == parse_rules(VALID)
# end def


def test_templates_survive_the_round_trip(client: TestClient) -> None:
    assert client.put("/api/editor/rules", content=WITH_TEMPLATE).status_code == 204
    text = client.get("/api/editor/rules").text
    assert parse_rules(text) == parse_rules(WITH_TEMPLATE)
    # Saving what was read back stays valid and stable.
    assert client.put("/api/editor/rules", content=text).status_code == 204
    assert client.get("/api/editor/rules").text == text
# end def


@pytest.mark.parametrize("text", [INVALID_SCHEMA, INVALID_YAML])
def test_invalid_is_422_and_changes_nothing(client: TestClient, text: str) -> None:
    client.put("/api/editor/rules", content=VALID)
    before = client.get("/api/editor/rules").text
    response = client.put("/api/editor/rules", content=text)
    assert response.status_code == 422 and response.json()["detail"]
    assert client.get("/api/editor/rules").text == before
# end def


def test_unchanged_rule_keeps_its_row_id(client: TestClient, tmp_path: Path) -> None:
    from sqlalchemy import create_engine, text

    def ids() -> dict[str, str]:
        engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite3'}")
        with engine.connect() as connection:
            rows = dict(connection.execute(text("select name, id from rules")).all())
        # end with
        engine.dispose()
        return rows
    # end def

    client.put("/api/editor/rules", content=WITH_TEMPLATE)
    first = ids()
    # Rename one rule, the other keeps its row.
    swapped = WITH_TEMPLATE.replace("name: Two", "name: Three")
    client.put("/api/editor/rules", content=swapped)
    second = ids()
    assert second["One"] == first["One"]
    assert "Two" not in second and "Three" in second
# end def


def test_deleting_an_account_used_by_a_rule_is_409(client: TestClient) -> None:
    account = client.post(
        "/api/accounts", json={"name": "A", "host": "h", "port": 993, "ssl": True, "username": "u", "password": "p"}
    ).json()
    # The id is generated server side, so build a rule that refers to it.
    rules = VALID.replace(ACCOUNT, account["id"])
    client.put("/api/editor/rules", content=rules)
    response = client.delete(f"/api/accounts/{account['id']}")
    assert response.status_code == 409 and "Newsletters" in response.json()["detail"][0]
    client.put("/api/editor/rules", content="rules: []\n")
    assert client.delete(f"/api/accounts/{account['id']}").status_code == 204
# end def
