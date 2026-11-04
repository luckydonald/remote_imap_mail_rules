"""The Coolify compose file only sets variables the server reads."""

from pathlib import Path

import yaml

from remote_imap_mail_rules.config import ImapSettings
from remote_imap_mail_rules.server.settings import ServerSettings

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.coolify.yml"
# Read by uvicorn itself, or magic variables that Coolify fills in.
FOREIGN = {"FORWARDED_ALLOW_IPS", "SERVICE_FQDN_APP_8000"}


def environment_names() -> set[str]:
    service = yaml.safe_load(COMPOSE.read_text())["services"]["app"]
    return {entry.split("=", 1)[0] for entry in service["environment"]}
# end def


def test_compose_sets_only_known_variables() -> None:
    known = {name.upper() for name in [*ServerSettings.model_fields, *ImapSettings.model_fields]}
    assert environment_names() - FOREIGN <= known
# end def


def test_compose_requires_what_the_first_login_needs() -> None:
    text = COMPOSE.read_text()
    for name in ("SECRET_KEY", "IMAP_ACCOUNT_ID", "IMAP_HOST", "IMAP_USERNAME", "IMAP_PASSWORD"):
        assert f"${{{name}:?}}" in text, name
    # end for
# end def


def test_compose_keeps_actions_off_by_default() -> None:
    assert "${ACTIONS_ENABLED:-false}" in COMPOSE.read_text()
# end def
