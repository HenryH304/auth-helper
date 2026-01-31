import tempfile
from pathlib import Path

import pytest

from src.crud import create_key, get_key_by_name, list_keys, delete_key, update_counter
from src.database import Database, init_db
from src.models import KeyCreate


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        init_db(db)
        yield db
        db.close()


def test_create_key(temp_db):
    """Test creating a key."""
    key_data = KeyCreate(
        name="github",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp",
        issuer="GitHub"
    )
    result = create_key(temp_db, key_data)

    assert result["name"] == "github"
    assert result["type"] == "totp"
    assert result["issuer"] == "GitHub"
    assert "secret" not in result  # Secret should not be in response


def test_create_key_duplicate_name_raises_error(temp_db):
    """Test that creating a key with duplicate name raises error."""
    key_data = KeyCreate(
        name="github",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp"
    )
    create_key(temp_db, key_data)

    # Try to create another key with same name
    with pytest.raises(ValueError, match="already exists"):
        create_key(temp_db, key_data)


def test_get_key_by_name(temp_db):
    """Test getting a key by name."""
    key_data = KeyCreate(
        name="github",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp"
    )
    create_key(temp_db, key_data)

    result = get_key_by_name(temp_db, "github")
    assert result is not None
    assert result["name"] == "github"
    assert result["type"] == "totp"


def test_get_key_by_name_not_found(temp_db):
    """Test getting a non-existent key."""
    result = get_key_by_name(temp_db, "nonexistent")
    assert result is None


def test_list_keys_empty(temp_db):
    """Test listing keys when empty."""
    result = list_keys(temp_db)
    assert result == []


def test_list_keys(temp_db):
    """Test listing multiple keys."""
    key1 = KeyCreate(
        name="github",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp"
    )
    key2 = KeyCreate(
        name="aws",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="hotp",
        counter=5
    )
    create_key(temp_db, key1)
    create_key(temp_db, key2)

    result = list_keys(temp_db)
    assert len(result) == 2
    names = {key["name"] for key in result}
    assert names == {"github", "aws"}


def test_list_keys_excludes_secret(temp_db):
    """Test that list_keys doesn't return secrets."""
    key_data = KeyCreate(
        name="github",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp"
    )
    create_key(temp_db, key_data)

    result = list_keys(temp_db)
    assert len(result) == 1
    assert "secret" not in result[0]


def test_delete_key(temp_db):
    """Test deleting a key."""
    key_data = KeyCreate(
        name="github",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="totp"
    )
    create_key(temp_db, key_data)

    # Verify key exists
    assert get_key_by_name(temp_db, "github") is not None

    # Delete the key
    delete_key(temp_db, "github")

    # Verify key is deleted
    assert get_key_by_name(temp_db, "github") is None


def test_delete_key_not_found(temp_db):
    """Test deleting a non-existent key raises error."""
    with pytest.raises(ValueError, match="not found"):
        delete_key(temp_db, "nonexistent")


def test_update_counter(temp_db):
    """Test updating counter for HOTP key."""
    key_data = KeyCreate(
        name="aws",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="hotp",
        counter=0
    )
    create_key(temp_db, key_data)

    # Update counter
    update_counter(temp_db, "aws", 1)

    # Verify counter was updated
    key = get_key_by_name(temp_db, "aws")
    assert key["counter"] == 1


def test_update_counter_not_found(temp_db):
    """Test updating counter for non-existent key raises error."""
    with pytest.raises(ValueError, match="not found"):
        update_counter(temp_db, "nonexistent", 1)


def test_hotp_key_defaults_to_zero_counter(temp_db):
    """Test that HOTP keys default counter to 0."""
    key_data = KeyCreate(
        name="aws",
        secret="JBSWY3DPEBLW64TMMQ======",
        type="hotp"
    )
    result = create_key(temp_db, key_data)

    # Get the full key data from database
    key = get_key_by_name(temp_db, "aws")
    assert key["counter"] == 0
