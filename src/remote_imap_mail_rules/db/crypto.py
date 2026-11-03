"""Fernet encryption of the account passwords."""

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class CryptoError(Exception):
    """The key is missing or invalid, or the stored value cannot be decrypted with it."""
# end class


def make_fernet(secret_key: SecretStr | None) -> Fernet:
    if secret_key is None:
        raise CryptoError("SECRET_KEY is not set.")
    # end if
    try:
        return Fernet(secret_key.get_secret_value().encode())
    except ValueError as e:
        raise CryptoError("SECRET_KEY is not a valid Fernet key.") from e
    # end try
# end def


def encrypt(secret_key: SecretStr | None, plain: str) -> str:
    return make_fernet(secret_key).encrypt(plain.encode()).decode()
# end def


def decrypt(secret_key: SecretStr | None, token: str) -> str:
    try:
        return make_fernet(secret_key).decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise CryptoError("The stored password cannot be decrypted with this SECRET_KEY.") from e
    # end try
# end def
