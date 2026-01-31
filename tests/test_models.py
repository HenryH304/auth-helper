import pytest
from pydantic import ValidationError

from src.models import KeyCreate, KeyResponse, KeyOutput


def test_key_create_totp_minimal():
    """Test creating a TOTP key with minimal fields."""
    key = KeyCreate(
        name="test",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp"
    )
    assert key.name == "test"
    assert key.secret == "JBSWY3DPEBLW64TMMQ======"
    assert key.type == "totp"
    assert key.algorithm == "sha1"
    assert key.digits == 6
    assert key.period == 30
    assert key.counter is None


def test_key_create_hotp_minimal():
    """Test creating an HOTP key with minimal fields."""
    key = KeyCreate(
        name="test",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="hotp"
    )
    assert key.type == "hotp"
    assert key.counter == 0  # Default counter for HOTP


def test_key_create_with_all_fields():
    """Test creating a key with all fields."""
    key = KeyCreate(
        name="test",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp",
        algorithm="sha256",
        digits=8,
        period=60,
        issuer="TestIssuer"
    )
    assert key.algorithm == "sha256"
    assert key.digits == 8
    assert key.period == 60
    assert key.issuer == "TestIssuer"


def test_key_create_invalid_type():
    """Test that invalid type raises validation error."""
    with pytest.raises(ValidationError):
        KeyCreate(
            name="test",
            secret="JBSWY3DPEBLW64TMMQ======",
            type="invalid"
        )


def test_key_create_invalid_algorithm():
    """Test that invalid algorithm raises validation error."""
    with pytest.raises(ValidationError):
        KeyCreate(
            name="test",
            secret="JBSWY3DPEBLW64TMMQ======",
            type="totp",
            algorithm="sha999"
        )


def test_key_create_invalid_digits():
    """Test that invalid digits raises validation error."""
    with pytest.raises(ValidationError):
        KeyCreate(
            name="test",
            secret="JBSWY3DPEBLW64TMMQ======",
            type="totp",
            digits=7
        )


def test_key_response_excludes_secret():
    """Test that KeyResponse doesn't include secret."""
    response = KeyResponse(
        name="test",
        type="totp",
        algorithm="sha1",
        digits=6,
        period=30,
        issuer=None,
        created_at="2024-01-31T12:00:00"
    )
    assert not hasattr(response, 'secret') or response.secret is None


def test_key_output_totp():
    """Test KeyOutput for TOTP."""
    output = KeyOutput(
        name="test",
        type="totp",
        algorithm="sha1",
        digits=6,
        period=30,
        issuer=None,
        created_at="2024-01-31T12:00:00"
    )
    assert output.type == "totp"
    assert output.period == 30


def test_key_output_hotp():
    """Test KeyOutput for HOTP."""
    output = KeyOutput(
        name="test",
        type="hotp",
        algorithm="sha1",
        digits=6,
        counter=42,
        issuer=None,
        created_at="2024-01-31T12:00:00"
    )
    assert output.type == "hotp"
    assert output.counter == 42
    # For HOTP output, period should be None
    assert not hasattr(output, 'period') or output.period is None
