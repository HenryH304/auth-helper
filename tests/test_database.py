import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.database import Database, init_db


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        init_db(db)
        yield db
        # Cleanup
        if db_path.exists():
            db_path.unlink()


def test_database_creates_file(temp_db):
    """Test that database file is created."""
    assert temp_db.db_path.exists()


def test_database_creates_keys_table(temp_db):
    """Test that keys table is created with correct schema."""
    cursor = temp_db.get_connection().cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='keys'"
    )
    result = cursor.fetchone()
    assert result is not None


def test_keys_table_has_correct_columns(temp_db):
    """Test that keys table has all required columns."""
    cursor = temp_db.get_connection().cursor()
    cursor.execute("PRAGMA table_info(keys)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    required_columns = {
        'id': 'INTEGER',
        'name': 'TEXT',
        'secret': 'TEXT',
        'type': 'TEXT',
        'algorithm': 'TEXT',
        'digits': 'INTEGER',
        'period': 'INTEGER',
        'counter': 'INTEGER',
        'issuer': 'TEXT',
        'created_at': 'TIMESTAMP',
    }

    for col, col_type in required_columns.items():
        assert col in columns, f"Column {col} not found in keys table"
        assert columns[col] == col_type, f"Column {col} has type {columns[col]}, expected {col_type}"


def test_name_column_is_unique(temp_db):
    """Test that name column has unique constraint."""
    cursor = temp_db.get_connection().cursor()

    # Insert a key
    cursor.execute(
        """
        INSERT INTO keys (name, secret, type, algorithm, digits, period, counter, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        ("test_key", "JBSWY3DPEBLW64TMMQ======", "totp", "sha1", 6, 30, 0)
    )
    temp_db.get_connection().commit()

    # Try to insert another key with same name
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO keys (name, secret, type, algorithm, digits, period, counter, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("test_key", "DIFFERENT_SECRET", "totp", "sha1", 6, 30, 0)
        )
        temp_db.get_connection().commit()


def test_database_init_is_idempotent(temp_db):
    """Test that calling init_db multiple times doesn't fail."""
    # Call init_db again
    init_db(temp_db)

    # Should not raise an error and table should still exist
    cursor = temp_db.get_connection().cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='keys'")
    result = cursor.fetchone()
    assert result is not None
