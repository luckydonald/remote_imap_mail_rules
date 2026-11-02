from pydantic_settings import SettingsConfigDict

from remote_imap_mail_rules.config import ImapSettings


class TestImapSettings(ImapSettings):
    """Reads `TEST_` prefixed variables only and ignores `.env`."""

    __test__ = False
    model_config = SettingsConfigDict(env_prefix="TEST_", env_file=None, extra="ignore")
# end class
