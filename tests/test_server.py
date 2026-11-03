"""The server: editor endpoints against a rules file in a temp folder."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings

KEY = Fernet.generate_key().decode()
VALID = """# my comment
rules:
  - name: Newsletters
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
    when:
      type: text
      field: subject
      operator: contains
      value: news
    actions: []
"""

INVALID_SCHEMA = "rules:\n  - name: broken\n    when:\n      type: nope\n"
INVALID_YAML = "rules: [unclosed\n"


@pytest.fixture
def rules_path(tmp_path: Path) -> Path:
    return tmp_path / "rules.yml"


@pytest.fixture
def client(rules_path: Path, tmp_path: Path) -> Iterator[TestClient]:
    settings = ServerSettings(_env_file=None, rules_path=rules_path, database_url=f"sqlite+aiosqlite:///{tmp_path.parent / (tmp_path.name + '-db.sqlite3')}", frontend_dist=tmp_path / "missing", secret_key=SecretStr(KEY))
    with TestClient(create_app(settings)) as test_client:
        test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        yield test_client
    # end with
# end def


def test_config_without_file(client: TestClient) -> None:
    response = client.get("/api/editor/config")
    assert response.json() == {"mode": "server", "source": "file", "file_name": "rules.yml", "exists": False, "actions_enabled": False}
# end def


def test_get_missing_file_is_404(client: TestClient) -> None:
    assert client.get("/api/editor/rules").status_code == 404
# end def


def test_get_existing_file(client: TestClient, rules_path: Path) -> None:
    rules_path.write_text(VALID, encoding="utf-8")
    assert client.get("/api/editor/config").json()["exists"] is True
    response = client.get("/api/editor/rules")
    assert response.status_code == 200
    assert response.text == VALID
# end def


def test_put_valid_writes_file_with_comments(client: TestClient, rules_path: Path) -> None:
    response = client.put("/api/editor/rules", content=VALID, headers={"Content-Type": "text/plain"})
    assert response.status_code == 204
    assert rules_path.read_text(encoding="utf-8") == VALID
    assert [p.name for p in rules_path.parent.iterdir()] == ["rules.yml"]
# end def


@pytest.mark.parametrize("text", [INVALID_SCHEMA, INVALID_YAML])
def test_put_invalid_is_422_and_keeps_file(client: TestClient, rules_path: Path, text: str) -> None:
    rules_path.write_text(VALID, encoding="utf-8")
    response = client.put("/api/editor/rules", content=text, headers={"Content-Type": "text/plain"})
    assert response.status_code == 422
    assert response.json()["detail"]
    assert rules_path.read_text(encoding="utf-8") == VALID
    assert [p.name for p in rules_path.parent.iterdir()] == ["rules.yml"]
# end def


def test_serves_built_frontend(rules_path: Path, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>editor</html>", encoding="utf-8")
    settings = ServerSettings(_env_file=None, rules_path=rules_path, database_url=f"sqlite+aiosqlite:///{tmp_path.parent / (tmp_path.name + '-db.sqlite3')}", frontend_dist=dist, secret_key=SecretStr(KEY))
    with TestClient(create_app(settings)) as test_client:
        test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        assert "editor" in test_client.get("/").text
        # Deep links of the frontend router get the app, API and asset misses stay 404.
        assert "editor" in test_client.get("/mail/some-account/INBOX%2FSub/12").text
        assert "editor" in test_client.get("/mail/some-account/INBOX.Sub").text
        assert test_client.get("/api/nope").status_code == 404
        assert test_client.get("/assets/missing.js").status_code == 404
        assert test_client.get("/api/editor/config").status_code == 200
    # end with
# end def
