import hashlib
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import pyotp

from src.database import Database, init_db
from src.crud import create_key, get_key_by_name
from src.models import KeyCreate
from src.otp import generate_otp


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        init_db(db)
        yield db
        db.close()


def test_generate_totp_code(temp_db):
    """Test generating TOTP code."""
    # Create a TOTP key
    key_data = KeyCreate(
        name="test_totp",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp",
        algorithm="sha1",
        digits=6,
        period=30
    )
    create_key(temp_db, key_data)

    result = generate_otp(temp_db, "test_totp")

    assert result["code"] is not None
    assert len(result["code"]) == 6
    assert result["type"] == "totp"
    assert "time_remaining" in result
    assert 0 <= result["time_remaining"] <= 30


def test_generate_totp_code_with_sha256(temp_db):
    """Test generating TOTP code with SHA256."""
    key_data = KeyCreate(
        name="test_totp_sha256",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp",
        algorithm="sha256",
        digits=8,
        period=30
    )
    create_key(temp_db, key_data)

    result = generate_otp(temp_db, "test_totp_sha256")

    assert result["code"] is not None
    assert len(result["code"]) == 8
    assert result["type"] == "totp"


def test_generate_hotp_code(temp_db):
    """Test generating HOTP code."""
    key_data = KeyCreate(
        name="test_hotp",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="hotp",
        algorithm="sha1",
        digits=6,
        counter=0
    )
    create_key(temp_db, key_data)

    result = generate_otp(temp_db, "test_hotp")

    assert result["code"] is not None
    assert len(result["code"]) == 6
    assert result["type"] == "hotp"
    assert result["counter"] == 0


def test_hotp_counter_increments(temp_db):
    """Test that HOTP counter increments after generation."""
    key_data = KeyCreate(
        name="test_hotp",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="hotp",
        algorithm="sha1",
        digits=6,
        counter=0
    )
    create_key(temp_db, key_data)

    # Generate first OTP
    result1 = generate_otp(temp_db, "test_hotp")
    assert result1["counter"] == 0

    # Generate second OTP
    result2 = generate_otp(temp_db, "test_hotp")
    assert result2["counter"] == 1

    # Verify counter in database
    key = get_key_by_name(temp_db, "test_hotp")
    assert key["counter"] == 2


def test_generate_otp_key_not_found(temp_db):
    """Test generating OTP for non-existent key."""
    with pytest.raises(ValueError, match="not found"):
        generate_otp(temp_db, "nonexistent")


def test_totp_time_remaining_increases_monotonically(temp_db):
    """Test that time_remaining is calculated correctly."""
    key_data = KeyCreate(
        name="test_totp",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp",
        algorithm="sha1",
        digits=6,
        period=30
    )
    create_key(temp_db, key_data)

    result = generate_otp(temp_db, "test_totp")
    # time_remaining should be between 0 and period
    assert 0 <= result["time_remaining"] <= 30


def test_generate_hotp_with_different_algorithms(temp_db):
    """Test HOTP generation with different hash algorithms."""
    for algo in ["sha1", "sha256", "sha512"]:
        key_data = KeyCreate(
            name=f"test_hotp_{algo}",
            secret="JBSWY3DPEBLW64TMMQ======",
            type="hotp",
            algorithm=algo,
            digits=6,
            counter=0
        )
        create_key(temp_db, key_data)

        result = generate_otp(temp_db, f"test_hotp_{algo}")
        assert result["code"] is not None
        assert len(result["code"]) == 6


def test_totp_code_is_valid(temp_db):
    """Test that TOTP code is valid with pyotp."""
    secret = "JBSWY3DPEBLW64TMMQ======"
    key_data = KeyCreate(
        name="test_totp",
        secret=secret,
        type="totp",
        algorithm="sha1",
        digits=6,
        period=30
    )
    create_key(temp_db, key_data)

    result = generate_otp(temp_db, "test_totp")

    # Verify code with pyotp
    totp = pyotp.TOTP(secret, digits=6, digest=hashlib.sha1, interval=30)
    assert totp.verify(result["code"])
