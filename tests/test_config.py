from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from remote_imap_mail_rules.config import ImapSettings

from .settings import TestImapSettings


REQUIRED = {
    "TEST_IMAP_ACCOUNT_ID": "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11",
    "TEST_IMAP_HOST": "imap.example.com",
    "TEST_IMAP_USERNAME": "me@example.com",
    "TEST_IMAP_PASSWORD": "hunter2",
}


def set_env(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    for key, value in {**REQUIRED, **extra}.items():
        monkeypatch.setenv(key, value)
    # end for
# end def


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch)
    settings = TestImapSettings()
    assert settings.imap_port == 993
    assert settings.imap_ssl is True
    assert settings.imap_page_size == 50
    assert settings.imap_account_name is None
    assert settings.rules_path == Path("rules/example.yml")
    assert settings.imap_password.get_secret_value() == "hunter2"
# end def


def test_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, TEST_IMAP_PORT="143", TEST_IMAP_SSL="false", TEST_IMAP_POLL_INTERVAL="2.5", TEST_RULES_PATH="x.yml")
    settings = TestImapSettings()
    assert (settings.imap_port, settings.imap_ssl, settings.imap_poll_interval) == (143, False, 2.5)
    assert settings.rules_path == Path("x.yml")
# end def


@pytest.mark.parametrize("missing", sorted(REQUIRED))
def test_required(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    set_env(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(ValidationError):
        TestImapSettings()
    # end with
# end def


def test_account_id_must_be_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch, TEST_IMAP_ACCOUNT_ID="my-account")
    with pytest.raises(ValidationError):
        TestImapSettings()
    # end with
# end def


def test_secret_not_leaked(monkeypatch: pytest.MonkeyPatch) -> None:
    set_env(monkeypatch)
    settings = TestImapSettings()
    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings.model_dump())
    assert isinstance(settings.imap_password, SecretStr)
# end def


def test_unprefixed_vars_ignored_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAP_HOST", "real.example.com")
    set_env(monkeypatch)
    assert TestImapSettings().imap_host == "imap.example.com"
# end def


def test_empty_variables_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Coolify compose file passes optional variables as empty strings."""
    for name in ("IMAP_ACCOUNT_ID", "IMAP_HOST", "IMAP_USERNAME", "IMAP_PASSWORD"):
        monkeypatch.setenv(name, "")
    # end for
    monkeypatch.setenv("IMAP_PORT", "")
    with pytest.raises(ValidationError):
        ImapSettings(_env_file=None)  # type: ignore[call-arg]
    # end with
    monkeypatch.setenv("IMAP_ACCOUNT_ID", "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11")
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USERNAME", "me")
    monkeypatch.setenv("IMAP_PASSWORD", "pw")
    assert ImapSettings(_env_file=None).imap_port == 993  # type: ignore[call-arg]
# end def
