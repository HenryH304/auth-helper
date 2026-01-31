import sqlite3
from pathlib import Path
from typing import Optional


class Database:
    """SQLite database connection manager."""

    def __init__(self, db_path: str = "auth_helper.db"):
        """Initialize database with given path.

        Args:
            db_path: Path to SQLite database file. Defaults to 'auth_helper.db' in project root.
        """
        self.db_path = Path(db_path)
        self._connection: Optional[sqlite3.Connection] = None

    def get_connection(self) -> sqlite3.Connection:
        """Get or create database connection.

        Returns:
            SQLite connection object.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            # Enable foreign keys
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def init_db(db: Database) -> None:
    """Initialize database schema.

    Creates the keys table if it doesn't exist. Safe to call multiple times.

    Args:
        db: Database instance to initialize.
    """
    connection = db.get_connection()
    cursor = connection.cursor()

    # Create keys table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            secret TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('totp', 'hotp')),
            algorithm TEXT NOT NULL CHECK(algorithm IN ('sha1', 'sha256', 'sha512')),
            digits INTEGER NOT NULL CHECK(digits IN (6, 8)),
            period INTEGER,
            counter INTEGER DEFAULT 0,
            issuer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
