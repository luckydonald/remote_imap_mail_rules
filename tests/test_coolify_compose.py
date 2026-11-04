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


def test_compose_requires_only_the_secret_key() -> None:
    text = COMPOSE.read_text()
    assert "${SECRET_KEY:?}" in text
    assert "?}" not in text.replace("${SECRET_KEY:?}", ""), "everything but SECRET_KEY must be optional or generated"
# end def


def test_compose_gets_the_admin_login_from_coolify() -> None:
    text = COMPOSE.read_text()
    assert "ADMIN_USERNAME=${SERVICE_USER_ADMIN}" in text
    assert "ADMIN_PASSWORD=${SERVICE_PASSWORD_ADMIN}" in text
# end def


def test_compose_keeps_actions_off_by_default() -> None:
    assert "${ACTIONS_ENABLED:-false}" in COMPOSE.read_text()
# end def
