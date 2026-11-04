"""Starts the server: `uv run python -m remote_imap_mail_rules.server.main`."""

import logging
import logging.config

import uvicorn
from pydantic import ValidationError

from ..config import ImapSettings
from .app import create_app
from .logs import get_log_config
from .sentry import init_sentry
from .settings import ServerSettings

logger = logging.getLogger(__name__)


def load_env_account() -> ImapSettings | None:
    """The account from the environment, or `None` when its variables are not (all) set."""
    try:
        return ImapSettings()  # type: ignore[call-arg]
    except ValidationError:
        logger.info("No complete IMAP account in the environment, nothing to seed.")
        return None
    # end try
# end def


def main() -> None:
    logging.config.dictConfig(get_log_config())
    settings = ServerSettings()
    init_sentry(settings)
    logger.info("Rules in %s", f"file {settings.rules_path}" if settings.rules_path else "the database")
    uvicorn.run(
        create_app(settings, load_env_account()),
        host=settings.server_host,
        port=settings.server_port,
        # Keep existing loggers enabled so app loggers work
        log_config=get_log_config(),
    )
# end def


if __name__ == "__main__":
    main()
# end if
