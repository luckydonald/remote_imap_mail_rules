import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from remote_imap_mail_rules.db.crypto import CryptoError, decrypt, encrypt

KEY = SecretStr(Fernet.generate_key().decode())


def test_round_trip_and_not_plain() -> None:
    token = encrypt(KEY, "hunter2")
    assert "hunter2" not in token
    assert decrypt(KEY, token) == "hunter2"
# end def


def test_missing_or_bad_key() -> None:
    with pytest.raises(CryptoError):
        encrypt(None, "x")
    # end with
    with pytest.raises(CryptoError):
        encrypt(SecretStr("not a key"), "x")
    # end with
# end def


def test_wrong_key_cannot_decrypt() -> None:
    token = encrypt(KEY, "x")
    with pytest.raises(CryptoError):
        decrypt(SecretStr(Fernet.generate_key().decode()), token)
    # end with
# end def
