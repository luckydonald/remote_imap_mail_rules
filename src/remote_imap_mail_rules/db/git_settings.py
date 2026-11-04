"""Repository of the single git settings row."""

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from .crypto import decrypt, encrypt
from .models import GitSettings
from .models.git_settings import ROW_ID


async def get_settings(session: AsyncSession) -> GitSettings:
    """The row, or a transient one with the defaults when nothing was saved yet."""
    row = await session.get(GitSettings, ROW_ID)
    if row is None:
        row = GitSettings(
            id=ROW_ID, enabled=False, auto_commit=False, auto_push=False, remote_url="", branch="main", auth_method="none", username="",
            token_encrypted="", author_name="remote_imap_mail_rules", author_email="rules@localhost",
        )
    # end if
    return row
# end def


async def save_settings(session: AsyncSession, secret_key: SecretStr | None, values: dict[str, object], token: str | None) -> GitSettings:
    """Applies `values` (field names of the row). `token` `None` keeps the stored one, `""` clears it."""
    row = await session.get(GitSettings, ROW_ID)
    if row is None:
        row = await get_settings(session)
        session.add(row)
    # end if
    for key, value in values.items():
        setattr(row, key, value)
    # end for
    if token is not None:
        row.token_encrypted = encrypt(secret_key, token) if token else ""
    # end if
    await session.flush()
    return row
# end def


def read_token(secret_key: SecretStr | None, row: GitSettings) -> str:
    return decrypt(secret_key, row.token_encrypted) if row.token_encrypted else ""
# end def
