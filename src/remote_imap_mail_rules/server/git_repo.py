"""Runs the `git` binary on the rules folder: status, init, commit, fetch and push.

Credentials reach git only through the environment of the one process that needs them (`GIT_ASKPASS` for HTTPS, `GIT_SSH_COMMAND` for SSH),
never through the remote URL or the arguments, and every message is scrubbed of the token before it leaves this module.
"""

import asyncio
import os
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

REMOTE = "origin"
KEY_NAME = "id_ed25519"
KEY_COMMENT = "remote_imap_mail_rules"
ASKPASS = """#!{python}
import os
import sys

# Git calls this with the prompt as the argument, e.g. "Username for 'https://host': ".
print(os.environ["RIMR_GIT_USERNAME"] if sys.argv[1:] and sys.argv[1].startswith("Username") else os.environ["RIMR_GIT_TOKEN"])
"""


class GitError(Exception):
    """A git call failed; the message is readable and has no secrets."""
# end class


@dataclass(frozen=True)
class GitConfig:
    """What the repo needs from the stored settings for one operation."""

    branch: str = "main"
    remote_url: str = ""
    auth_method: str = "none"
    username: str = ""
    token: str = ""
    author_name: str = "remote_imap_mail_rules"
    author_email: str = "rules@localhost"
# end class


class GitStatus(BaseModel):
    git_available: bool
    initialized: bool
    branch: str | None = None
    changed: list[str] = []
    has_upstream: bool = False
    ahead: int = 0
    behind: int = 0
    last_commit: str | None = None
    remote_configured: bool = False
# end class


def git_available() -> bool:
    return shutil.which("git") is not None
# end def


def generate_ssh_key(state_dir: Path) -> str:
    """Writes a new ed25519 key (mode 0600) replacing any old one, returns the public key line."""
    ssh_dir = state_dir / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(ssh_dir, stat.S_IRWXU)
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption())
    path = ssh_dir / KEY_NAME
    path.unlink(missing_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as file:
        file.write(private)
    # end with
    public = key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode() + f" {KEY_COMMENT}"
    (ssh_dir / f"{KEY_NAME}.pub").write_text(public + "\n", encoding="utf-8")
    return public
# end def


def read_public_key(state_dir: Path) -> str | None:
    try:
        return (state_dir / "ssh" / f"{KEY_NAME}.pub").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    # end try
# end def


class GitRepo:
    """One folder; operations never overlap (`lock`)."""

    def __init__(self, directory: Path, state_dir: Path) -> None:
        self.directory = directory
        self.state_dir = state_dir
        self.lock = asyncio.Lock()
    # end def

    def is_initialized(self) -> bool:
        return (self.directory / ".git").exists()
    # end def

    def build_env(self, config: GitConfig, *, remote: bool) -> dict[str, str]:
        env = {key: value for key, value in os.environ.items() if not key.startswith(("GIT_", "RIMR_"))}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
        if not remote:
            return env
        # end if
        if config.auth_method == "https":
            self.state_dir.mkdir(parents=True, exist_ok=True)
            helper = self.state_dir / "askpass.py"
            text = ASKPASS.format(python=sys.executable)
            if not helper.exists() or helper.read_text(encoding="utf-8") != text:
                helper.write_text(text, encoding="utf-8")
            # end if
            os.chmod(helper, stat.S_IRWXU)
            env.update(GIT_ASKPASS=str(helper), RIMR_GIT_USERNAME=config.username, RIMR_GIT_TOKEN=config.token)
        elif config.auth_method == "ssh":
            ssh_dir = self.state_dir / "ssh"
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {ssh_dir / KEY_NAME} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new "
                f"-o UserKnownHostsFile={ssh_dir / 'known_hosts'}"
            )
        # end if
        return env
    # end def

    async def run(self, *args: str, config: GitConfig | None = None, remote: bool = False, check: bool = True) -> tuple[int, str]:
        """Returns `(exit code, stdout)`; with `check` a failure raises `GitError` carrying git's own message."""
        config = config or GitConfig()
        if not git_available():
            raise GitError("The git binary is not installed on the server.")
        # end if
        command = ["git", "-C", str(self.directory), "-c", f"safe.directory={self.directory}", "-c", f"user.name={config.author_name}", "-c", f"user.email={config.author_email}", *args]
        process = await asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=self.build_env(config, remote=remote)
        )
        out, err = await process.communicate()
        code = process.returncode or 0
        if check and code != 0:
            raise GitError(self.scrub(err.decode(errors="replace").strip() or f"git {args[0]} failed with exit code {code}", config))
        # end if
        return code, out.decode(errors="replace")
    # end def

    @staticmethod
    def scrub(message: str, config: GitConfig) -> str:
        if config.token:
            message = message.replace(config.token, "***")
        # end if
        return message
    # end def

    async def status(self, config: GitConfig) -> GitStatus:
        if not git_available():
            return GitStatus(git_available=False, initialized=False)
        # end if
        if not self.is_initialized():
            return GitStatus(git_available=True, initialized=False)
        # end if
        _, branch = await self.run("rev-parse", "--abbrev-ref", "HEAD", config=config, check=False)
        _, porcelain = await self.run("status", "--porcelain", "--untracked-files=all", config=config)
        code, log = await self.run("log", "-1", "--format=%h %s (%cr)", config=config, check=False)
        _, remote_url = await self.run("remote", "get-url", REMOTE, config=config, check=False)
        status = GitStatus(
            git_available=True,
            initialized=True,
            branch=branch.strip() or None,
            changed=[line[3:] for line in porcelain.splitlines()],
            last_commit=log.strip() if code == 0 and log.strip() else None,
            remote_configured=bool(remote_url.strip() or config.remote_url),
        )
        code, counts = await self.run("rev-list", "--left-right", "--count", "HEAD...@{upstream}", config=config, check=False)
        if code == 0:
            status.has_upstream = True
            ahead, behind = counts.split()
            status.ahead, status.behind = int(ahead), int(behind)
        elif status.remote_configured and status.last_commit:
            # Nothing pushed yet: every commit is waiting.
            _, total = await self.run("rev-list", "--count", "HEAD", config=config, check=False)
            status.ahead = int(total.strip() or 0)
        # end if
        return status
    # end def

    async def init(self, config: GitConfig) -> None:
        async with self.lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            await self.run("init", "-b", config.branch, config=config)
        # end with
    # end def

    async def commit(self, config: GitConfig, message: str = "Update rules") -> bool:
        """Commits everything; `False` when there was nothing to commit."""
        async with self.lock:
            if not self.is_initialized():
                raise GitError("The folder is not a git repository yet, initialise it first.")
            # end if
            await self.run("add", "-A", config=config)
            code, _ = await self.run("diff", "--cached", "--quiet", config=config, check=False)
            if code == 0:
                return False
            # end if
            await self.run("commit", "-m", message, config=config)
            return True
        # end with
    # end def

    async def ensure_remote(self, config: GitConfig) -> None:
        if not config.remote_url:
            raise GitError("No remote URL is set.")
        # end if
        code, _ = await self.run("remote", "get-url", REMOTE, config=config, check=False)
        await self.run("remote", "set-url" if code == 0 else "add", REMOTE, config.remote_url, config=config)
    # end def

    async def fetch(self, config: GitConfig) -> None:
        async with self.lock:
            await self.ensure_remote(config)
            await self.run("fetch", REMOTE, config=config, remote=True)
        # end with
    # end def

    async def push(self, config: GitConfig) -> None:
        """A rejected push (the remote has other commits) raises; there is no force push and no automatic pull."""
        async with self.lock:
            if not self.is_initialized():
                raise GitError("The folder is not a git repository yet, initialise it first.")
            # end if
            await self.ensure_remote(config)
            await self.run("push", "-u", REMOTE, f"HEAD:refs/heads/{config.branch}", config=config, remote=True)
        # end with
    # end def
# end class
