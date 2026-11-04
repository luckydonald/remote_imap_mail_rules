"""Account repository: CRUD, seeding from the environment and the drift check."""

import logging
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import ImapSettings
from .crypto import decrypt, encrypt
from .models import Account

logger = logging.getLogger(__name__)


async def list_accounts(session: AsyncSession) -> list[Account]:
    return list((await session.scalars(select(Account).order_by(Account.created_at, Account.name))).all())
# end def


async def get_account(session: AsyncSession, account_id: UUID) -> Account | None:
    return await session.get(Account, account_id)
# end def


async def create_account(
    session: AsyncSession,
    secret_key: SecretStr | None,
    *,
    name: str,
    host: str,
    port: int,
    ssl: bool,
    username: str,
    password: str,
    page_size: int = 50,
    poll_interval: float = 60.0,
    account_id: UUID | None = None,
) -> Account:
    account = Account(
        id=account_id or uuid4(),
        name=name,
        host=host,
        port=port,
        ssl=ssl,
        username=username,
        password_encrypted=encrypt(secret_key, password),
        page_size=page_size,
        poll_interval=poll_interval,
    )
    session.add(account)
    await session.flush()
    return account
# end def


async def update_account(
    session: AsyncSession,
    secret_key: SecretStr | None,
    account: Account,
    *,
    name: str,
    host: str,
    port: int,
    ssl: bool,
    username: str,
    password: str | None,
    page_size: int,
    poll_interval: float,
) -> Account:
    """The id never changes. A `None` password keeps the stored one."""
    if password is not None:
        account.password_encrypted = encrypt(secret_key, password)
    # end if
    account.name = name
    account.host = host
    account.port = port
    account.ssl = ssl
    account.username = username
    account.page_size = page_size
    account.poll_interval = poll_interval
    await session.flush()
    return account
# end def


async def delete_account(session: AsyncSession, account: Account) -> None:
    await session.delete(account)
    await session.flush()
# end def


def env_differences(account: Account, env: ImapSettings, secret_key: SecretStr | None) -> list[str]:
    """Names of the fields that differ from the environment, never their values."""
    differing = [
        field
        for field, stored, wanted in (
            ("host", account.host, env.imap_host),
            ("port", account.port, env.imap_port),
            ("ssl", account.ssl, env.imap_ssl),
            ("username", account.username, env.imap_username),
        )
        if stored != wanted
    ]
    try:
        if decrypt(secret_key, account.password_encrypted) != env.imap_password.get_secret_value():
            differing.append("password")
        # end if
    except Exception:
        # Without a usable key the password cannot be compared; do not claim a difference.
        logger.warning("Cannot compare the password of account %s with the environment, the SECRET_KEY does not work.", account.id)
    # end try
    return differing
# end def


async def seed_from_env(session: AsyncSession, env: ImapSettings | None, secret_key: SecretStr | None) -> list[str]:
    """Inserts the environment's account once, and returns the fields of an existing one that differ.

    An existing account is never overwritten: it may have been edited on purpose.
    """
    if env is None:
        return []
    # end if
    account = await get_account(session, env.imap_account_id)
    if account is not None:
        differing = env_differences(account, env, secret_key)
        if differing:
            logger.warning("Account %s differs from the environment in: %s", account.id, ", ".join(differing))
        # end if
        return differing
    # end if
    if secret_key is None:
        logger.warning("SECRET_KEY is not set, so the account from the environment is not stored in the database.")
        return []
    # end if
    await create_account(
        session,
        secret_key,
        account_id=env.imap_account_id,
        name=env.imap_account_name or env.imap_username,
        host=env.imap_host,
        port=env.imap_port,
        ssl=env.imap_ssl,
        username=env.imap_username,
        password=env.imap_password.get_secret_value(),
        page_size=env.imap_page_size,
        poll_interval=env.imap_poll_interval,
    )
    logger.info("Seeded account %s from the environment.", env.imap_account_id)
    return []
# end def


def imap_settings(account: Account, secret_key: SecretStr | None) -> ImapSettings:
    """The connection settings of a stored account. Raises `CryptoError` if the password cannot be decrypted."""
    return ImapSettings(
        _env_file=None,  # type: ignore[call-arg]
        imap_account_id=account.id,
        imap_account_name=account.name,
        imap_host=account.host,
        imap_port=account.port,
        imap_ssl=account.ssl,
        imap_username=account.username,
        imap_password=SecretStr(decrypt(secret_key, account.password_encrypted)),
        imap_page_size=account.page_size,
        imap_poll_interval=account.poll_interval,
    )
# end def

