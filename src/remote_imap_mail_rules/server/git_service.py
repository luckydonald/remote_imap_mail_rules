"""The git feature of the server: stored settings, the repo, and the automatic commit and push after a rules save."""

import logging
from typing import Literal

from pydantic import BaseModel, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db import git_settings as settings_repository
from ..db.crypto import CryptoError
from ..db.models import GitSettings
from .git_repo import GitConfig, GitError, GitRepo, GitStatus, generate_ssh_key, git_available, read_public_key

logger = logging.getLogger(__name__)

AuthMethod = Literal["none", "https", "ssh"]


class GitSettingsView(BaseModel):
    """The settings as the API shows them: the token is never included."""

    enabled: bool
    auto_commit: bool
    auto_push: bool
    remote_url: str
    branch: str
    auth_method: AuthMethod
    username: str
    has_token: bool
    author_name: str
    author_email: str
# end class


class GitState(BaseModel):
    settings: GitSettingsView
    status: GitStatus
    public_key: str | None
    last_error: str | None
    directory: str
# end class


def to_view(row: GitSettings) -> GitSettingsView:
    return GitSettingsView(
        enabled=row.enabled, auto_commit=row.auto_commit, auto_push=row.auto_push, remote_url=row.remote_url, branch=row.branch,
        auth_method=row.auth_method, username=row.username, has_token=bool(row.token_encrypted), author_name=row.author_name, author_email=row.author_email,  # type: ignore[arg-type]
    )
# end def


class GitService:
    def __init__(self, repo: GitRepo, session_factory: async_sessionmaker[AsyncSession], secret_key: SecretStr | None) -> None:
        self.repo = repo
        self.session_factory = session_factory
        self.secret_key = secret_key
        self.last_error: str | None = None
    # end def

    async def load(self) -> tuple[GitSettings, GitConfig]:
        async with self.session_factory() as session:
            row = await settings_repository.get_settings(session)
        # end with
        try:
            token = settings_repository.read_token(self.secret_key, row)
        except CryptoError as e:
            raise GitError(str(e)) from e
        # end try
        config = GitConfig(
            branch=row.branch, remote_url=row.remote_url, auth_method=row.auth_method, username=row.username, token=token,
            author_name=row.author_name, author_email=row.author_email,
        )
        return row, config
    # end def

    async def state(self) -> GitState:
        row, config = await self.load()
        status = await self.repo.status(config)
        return GitState(settings=to_view(row), status=status, public_key=read_public_key(self.repo.state_dir), last_error=self.last_error, directory=str(self.repo.directory))
    # end def

    async def update_settings(self, values: dict[str, object], token: str | None) -> None:
        async with self.session_factory() as session:
            await settings_repository.save_settings(session, self.secret_key, values, token)
            await session.commit()
        # end with
    # end def

    def generate_key(self) -> str:
        return generate_ssh_key(self.repo.state_dir)
    # end def

    async def run(self, action: Literal["init", "commit", "push", "fetch"]) -> bool:
        """Runs one action by hand; a failure is remembered for the status and re-raised. Returns `False` for a commit with nothing to commit."""
        _, config = await self.load()
        try:
            result = True
            if action == "init":
                await self.repo.init(config)
            elif action == "commit":
                result = await self.repo.commit(config)
            elif action == "push":
                await self.repo.push(config)
            else:
                await self.repo.fetch(config)
            # end if
        except GitError as e:
            self.last_error = str(e)
            raise
        # end try
        self.last_error = None
        return result
    # end def

    async def auto(self) -> None:
        """After a rules save: commit and push as far as the settings ask. Never raises, the save must not fail because of git."""
        try:
            row, _ = await self.load()
            if not (row.enabled and row.auto_commit) or not git_available() or not self.repo.is_initialized():
                return
            # end if
            await self.run("commit")
            if row.auto_push:
                await self.run("push")
            # end if
        except GitError as e:
            self.last_error = str(e)
            logger.warning("Automatic git step failed: %s", e)
        except Exception as e:  # noqa: BLE001
            self.last_error = f"Unexpected error: {type(e).__name__}"
            logger.exception("Automatic git step failed")
        # end try
    # end def
# end class
