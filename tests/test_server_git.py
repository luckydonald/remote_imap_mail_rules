"""Git control of the rules folder, against a real `git` in temporary folders and a local bare repository as the remote."""

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.git_repo import GitConfig, GitError, GitRepo, generate_ssh_key, git_available
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.test_server import VALID

pytestmark = pytest.mark.skipif(not git_available(), reason="git is not installed")

SETTINGS = {
    "enabled": True, "auto_commit": True, "auto_push": False, "remote_url": "", "branch": "main", "auth_method": "none", "username": "",
    "author_name": "Tester", "author_email": "tester@example.com",
}


@pytest.fixture
def bare(tmp_path: Path) -> Path:
    path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(path)], check=True, capture_output=True)
    return path


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


@pytest.mark.asyncio
async def test_repo_init_commit_push(tmp_path: Path, bare: Path) -> None:
    repo = GitRepo(tmp_path / "rules", tmp_path / "state")
    config = GitConfig(remote_url=str(bare))
    assert (await repo.status(config)).initialized is False
    await repo.init(config)
    (repo.directory / "rules.yml").write_text("rules: []\n")
    assert (await repo.status(config)).changed == ["rules.yml"]
    assert await repo.commit(config) is True
    assert await repo.commit(config) is False
    status = await repo.status(config)
    assert status.changed == [] and status.last_commit and status.ahead == 1 and status.remote_configured
    await repo.push(config)
    status = await repo.status(config)
    assert status.remote_configured and status.has_upstream and status.ahead == 0
    (repo.directory / "rules.yml").write_text("rules: []\n# more\n")
    await repo.commit(config)
    assert (await repo.status(config)).ahead == 1
# end def


@pytest.mark.asyncio
async def test_rejected_push_raises(tmp_path: Path, bare: Path) -> None:
    config = GitConfig(remote_url=str(bare))
    first, second = GitRepo(tmp_path / "a", tmp_path / "state"), GitRepo(tmp_path / "b", tmp_path / "state")
    for repo, text in ((first, "one\n"), (second, "two\n")):
        await repo.init(config)
        (repo.directory / "rules.yml").write_text(text)
        await repo.commit(config)
    # end for
    await first.push(config)
    with pytest.raises(GitError):
        await second.push(config)
    # end with
# end def


def test_https_env_keeps_the_token_out_of_the_arguments(tmp_path: Path) -> None:
    repo = GitRepo(tmp_path, tmp_path / "state")
    env = repo.build_env(GitConfig(auth_method="https", username="me", token="s3cret"), remote=True)
    assert env["RIMR_GIT_TOKEN"] == "s3cret" and Path(env["GIT_ASKPASS"]).is_file()
    assert "s3cret" not in "".join(arg for key, arg in env.items() if key not in {"RIMR_GIT_TOKEN"})
    assert GitRepo.scrub("fatal: s3cret rejected", GitConfig(token="s3cret")) == "fatal: *** rejected"
# end def


def test_ssh_key_is_private_and_public_is_shown(tmp_path: Path) -> None:
    public = generate_ssh_key(tmp_path)
    assert public.startswith("ssh-ed25519 ")
    assert (tmp_path / "ssh" / "id_ed25519").stat().st_mode & 0o777 == 0o600
    assert generate_ssh_key(tmp_path) != public
# end def


def test_requires_login(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/git").status_code == 401
# end def


def test_settings_round_trip_never_returns_the_token(client: TestClient) -> None:
    body = {**SETTINGS, "auth_method": "https", "username": "me", "token": "s3cret"}
    state = client.put("/api/git/settings", json=body).json()
    assert state["settings"]["has_token"] is True and "s3cret" not in str(state)
    # Omitting the token keeps it, an empty one clears it.
    assert client.put("/api/git/settings", json={**body, "token": None}).json()["settings"]["has_token"] is True
    assert client.put("/api/git/settings", json={**body, "token": ""}).json()["settings"]["has_token"] is False
# end def


def test_auto_push_needs_auto_commit(client: TestClient) -> None:
    assert client.put("/api/git/settings", json={**SETTINGS, "auto_commit": False, "auto_push": True}).status_code == 422
# end def


def test_manual_flow(client: TestClient, bare: Path) -> None:
    client.put("/api/git/settings", json={**SETTINGS, "remote_url": str(bare)})
    assert client.get("/api/git").json()["status"]["initialized"] is False
    # Nothing happens before the init, the save still works, and the mirror file is pending.
    assert client.put("/api/editor/rules", content=VALID).status_code == 204
    assert client.post("/api/git/commit").status_code == 502
    assert client.get("/api/git").json()["last_error"]
    assert client.post("/api/git/init").json()["state"]["status"]["initialized"] is True
    assert client.get("/api/git").json()["status"]["changed"] == ["rules.yml"]
    state = client.post("/api/git/commit").json()["state"]
    assert state["status"]["changed"] == [] and state["status"]["last_commit"] and state["status"]["ahead"] == 1
    state = client.post("/api/git/push").json()["state"]
    assert state["status"]["ahead"] == 0 and state["status"]["has_upstream"] and state["last_error"] is None
    assert client.post("/api/git/fetch").status_code == 200
# end def


def test_auto_push(client: TestClient, bare: Path) -> None:
    client.put("/api/git/settings", json={**SETTINGS, "remote_url": str(bare), "auto_push": True})
    client.post("/api/git/init")
    client.put("/api/editor/rules", content=VALID)
    status = client.get("/api/git").json()["status"]
    assert status["changed"] == [] and status["ahead"] == 0 and status["has_upstream"]
    log = subprocess.run(["git", "-C", str(bare), "log", "--format=%s"], capture_output=True, text=True, check=True).stdout
    assert log.strip() == "Update rules"
# end def


def test_mirror_is_written_and_nothing_commits_when_disabled(client: TestClient, tmp_path: Path) -> None:
    client.put("/api/git/settings", json={**SETTINGS, "enabled": False})
    client.post("/api/git/init")
    client.put("/api/editor/rules", content=VALID)
    assert (tmp_path / "data" / "rules" / "rules.yml").is_file()
    assert client.get("/api/git").json()["status"]["last_commit"] is None
# end def


def test_auto_commit_writes_a_commit_per_save(client: TestClient) -> None:
    client.put("/api/git/settings", json=SETTINGS)
    client.post("/api/git/init")
    client.put("/api/editor/rules", content=VALID)
    state = client.get("/api/git").json()
    assert state["status"]["changed"] == [] and state["status"]["last_commit"]
# end def


def test_missing_git_binary_is_reported(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("remote_imap_mail_rules.server.git_repo.git_available", lambda: False)
    assert client.get("/api/git").json()["status"]["git_available"] is False
    assert client.post("/api/git/init").status_code == 502
# end def
