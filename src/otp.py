import hashlib
import time
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


def verify_otp(db: Database, name: str, code: str) -> Dict[str, Any]:
    """Verify an OTP code against a stored key (Party A verification).

    Args:
        db: Database instance.
        name: Key name.
        code: OTP code to verify.

    Returns:
        Dictionary with valid (bool).

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
        return _verify_totp(secret, digits, key["period"], digest, code)
    else:  # hotp
        return _verify_hotp(db, name, secret, digits, key["counter"], digest, code)


def _verify_totp(
    secret: str,
    digits: int,
    period: int,
    digest,
    code: str,
) -> Dict[str, Any]:
    """Verify a TOTP code.

    Args:
        secret: Base32-encoded secret.
        digits: Number of digits.
        period: Time period in seconds.
        digest: Digest algorithm function.
        code: OTP code to verify.

    Returns:
        Dictionary with valid (bool).
    """
    totp = pyotp.TOTP(secret, digits=digits, digest=digest, interval=period)
    # valid_window=1 allows for 1 period drift (previous or next code)
    valid = totp.verify(code, valid_window=1)

    return {"valid": valid}


def _verify_hotp(
    db: Database,
    name: str,
    secret: str,
    digits: int,
    counter: int,
    digest,
    code: str,
) -> Dict[str, Any]:
    """Verify an HOTP code with look-ahead window.

    Args:
        db: Database instance.
        name: Key name (for updating counter).
        secret: Base32-encoded secret.
        digits: Number of digits.
        counter: Current counter value.
        digest: Digest algorithm function.
        code: OTP code to verify.

    Returns:
        Dictionary with valid (bool).
    """
    hotp = pyotp.HOTP(secret, digits=digits, digest=digest)

    # Look-ahead window of 10 to handle desync
    look_ahead = 10
    for i in range(look_ahead):
        if hotp.verify(code, counter + i):
            # Update counter to next value after the matched one
            update_counter(db, name, counter + i + 1)
            return {"valid": True}

    return {"valid": False}
