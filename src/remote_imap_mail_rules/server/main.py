"""Starts the server: `uv run python -m remote_imap_mail_rules.server.main`."""

import logging
import logging.config

import uvicorn
from pydantic import ValidationError

from ..config import ImapSettings
from .app import create_app
from .logs import get_log_config
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
    logger.info("Editing rules file %s", settings.rules_path)
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
