from datetime import datetime
from typing import Optional, Dict, Any, List

from src.database import Database
from src.models import KeyCreate, KeyOutput


def create_key(db: Database, key_data: KeyCreate) -> Dict[str, Any]:
    """Create a new key in the database.

    Args:
        db: Database instance.
        key_data: KeyCreate model with key details.

    Returns:
        Dictionary with created key details (excluding secret).

    Raises:
        ValueError: If name already exists.
    """
    connection = db.get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO keys (name, secret, type, algorithm, digits, period, counter, issuer, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                key_data.name,
                key_data.secret,
                key_data.type,
                key_data.algorithm,
                key_data.digits,
                key_data.period if key_data.type == "totp" else None,
                key_data.counter if key_data.type == "hotp" else 0,
                key_data.issuer,
            ),
        )
        connection.commit()
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise ValueError(f"Key with name '{key_data.name}' already exists")
        raise

    # Fetch the created key
    return get_key_by_name(db, key_data.name)


def get_key_by_name(db: Database, name: str) -> Optional[Dict[str, Any]]:
    """Get a key by name.

    Args:
        db: Database instance.
        name: Key name to retrieve.

    Returns:
        Dictionary with key details (excluding secret) or None if not found.
    """
    connection = db.get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, name, type, algorithm, digits, period, counter, issuer, created_at
        FROM keys WHERE name = ?
        """,
        (name,),
    )
    row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "type": row[2],
        "algorithm": row[3],
        "digits": row[4],
        "period": row[5],
        "counter": row[6],
        "issuer": row[7],
        "created_at": row[8],
    }


def list_keys(db: Database) -> List[Dict[str, Any]]:
    """List all keys.

    Args:
        db: Database instance.

    Returns:
        List of dictionaries with key details (excluding secrets).
    """
    connection = db.get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, name, type, algorithm, digits, period, counter, issuer, created_at
        FROM keys ORDER BY created_at DESC
        """
    )
    rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "type": row[2],
            "algorithm": row[3],
            "digits": row[4],
            "period": row[5],
            "counter": row[6],
            "issuer": row[7],
            "created_at": row[8],
        }
        for row in rows
    ]


def delete_key(db: Database, name: str) -> None:
    """Delete a key by name.

    Args:
        db: Database instance.
        name: Key name to delete.

    Raises:
        ValueError: If key not found.
    """
    connection = db.get_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM keys WHERE name = ?", (name,))
    connection.commit()

    if cursor.rowcount == 0:
        raise ValueError(f"Key '{name}' not found")


def update_counter(db: Database, name: str, new_counter: int) -> None:
    """Update counter for an HOTP key.

    Args:
        db: Database instance.
        name: Key name.
        new_counter: New counter value.

    Raises:
        ValueError: If key not found.
    """
    connection = db.get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "UPDATE keys SET counter = ? WHERE name = ?",
        (new_counter, name),
    )
    connection.commit()

    if cursor.rowcount == 0:
        raise ValueError(f"Key '{name}' not found")
