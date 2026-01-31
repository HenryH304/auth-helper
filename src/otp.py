import hashlib
import time
import secrets
from typing import Any, Dict, Literal

import pyotp

from src.database import Database
from src.crud import get_key_with_secret, update_counter


def _get_digest_algorithm(algorithm: str):
    """Get the hash algorithm for pyotp.

    Args:
        algorithm: Algorithm name (sha1, sha256, sha512).

    Returns:
        Hash algorithm function from hashlib.
    """
    if algorithm == "sha1":
        return hashlib.sha1
    elif algorithm == "sha256":
        return hashlib.sha256
    elif algorithm == "sha512":
        return hashlib.sha512
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def generate_otp(db: Database, name: str) -> Dict[str, Any]:
    """Generate OTP code for a key.

    Args:
        db: Database instance.
        name: Key name.

    Returns:
        Dictionary with code, type, and metadata (time_remaining for TOTP, counter for HOTP).

    Raises:
        ValueError: If key not found.
    """
    key = get_key_with_secret(db, name)
    if key is None:
        raise ValueError(f"Key '{name}' not found")

    secret = key["secret"]
    key_type = key["type"]
    algorithm = key["algorithm"]
    digits = key["digits"]

    digest = _get_digest_algorithm(algorithm)

    if key_type == "totp":
        return _generate_totp(secret, algorithm, digits, key["period"], digest)
    else:  # hotp
        return _generate_hotp(db, name, secret, algorithm, digits, key["counter"], digest)


def _generate_totp(
    secret: str,
    algorithm: str,
    digits: int,
    period: int,
    digest,
) -> Dict[str, Any]:
    """Generate TOTP code.

    Args:
        secret: Base32-encoded secret.
        algorithm: Hash algorithm.
        digits: Number of digits.
        period: Time period in seconds.
        digest: Digest algorithm function.

    Returns:
        Dictionary with code, type, and time_remaining.
    """
    totp = pyotp.TOTP(secret, digits=digits, digest=digest, interval=period)
    code = totp.now()

    # Calculate time remaining
    current_time = int(time.time())
    time_remaining = period - (current_time % period)

    return {
        "code": code,
        "type": "totp",
        "time_remaining": time_remaining,
    }


def _generate_hotp(
    db: Database,
    name: str,
    secret: str,
    algorithm: str,
    digits: int,
    counter: int,
    digest,
) -> Dict[str, Any]:
    """Generate HOTP code and increment counter.

    Args:
        db: Database instance.
        name: Key name (for updating counter).
        secret: Base32-encoded secret.
        algorithm: Hash algorithm.
        digits: Number of digits.
        counter: Current counter value.
        digest: Digest algorithm function.

    Returns:
        Dictionary with code, type, and counter.
    """
    hotp = pyotp.HOTP(secret, digits=digits, digest=digest)
    code = hotp.at(counter)

    # Increment counter in database
    update_counter(db, name, counter + 1)

    return {
        "code": code,
        "type": "hotp",
        "counter": counter,
    }


def generate_secret(length: int = 32) -> str:
    """Generate a cryptographically secure random secret.

    Args:
        length: Length of the secret in bytes (will be base32 encoded).

    Returns:
        Base32-encoded secret string.
    """
    random_bytes = secrets.token_bytes(length)
    return pyotp.random_base32(length=length)


def generate_otpauth_uri(
    secret: str,
    name: str,
    type_: str,
    algorithm: str,
    digits: int,
    issuer: str = None,
    period: int = None,
    counter: int = None,
) -> str:
    """Generate an otpauth:// URI for the given parameters.

    Args:
        secret: Base32-encoded secret.
        name: Account name/label.
        type_: Type of OTP (totp or hotp).
        algorithm: HMAC algorithm (sha1, sha256, sha512).
        digits: Number of digits.
        issuer: Optional issuer name.
        period: Period for TOTP (in seconds).
        counter: Counter for HOTP.

    Returns:
        otpauth:// URI string.
    """
    if type_ == "totp":
        totp = pyotp.TOTP(secret, digits=digits, interval=period or 30)
        uri = totp.provisioning_uri(name=name, issuer_name=issuer)
        # Update the algorithm in the URI if not sha1
        if algorithm != "sha1":
            uri = uri.replace("algorithm=SHA1", f"algorithm=SHA{algorithm.upper()}")
        return uri
    else:  # hotp
        hotp = pyotp.HOTP(secret, digits=digits)
        uri = hotp.provisioning_uri(name=name, issuer_name=issuer, initial_count=counter or 0)
        # Update the algorithm in the URI if not sha1
        if algorithm != "sha1":
            uri = uri.replace("algorithm=SHA1", f"algorithm=SHA{algorithm.upper()}")
        return uri
