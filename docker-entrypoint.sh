#!/bin/bash
set -e

# Initialize database if it doesn't exist
if [ ! -f /app/data/auth_helper.db ]; then
    echo "Initializing database..."
    python -c "from src.database import init_db, Database; db = Database('/app/data/auth_helper.db'); init_db(db); db.close()"
fi

# Run the main command
exec "$@"