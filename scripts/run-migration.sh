#!/bin/bash
# Run a specific migration file against the database
# Usage: ./scripts/run-migration.sh migrations/010_viewer_views.sql

set -e

PROJECT_DIR="/home/cooneycw/Projects/nhl-api"
MIGRATION_FILE="${1:-migrations/010_viewer_views.sql}"

if [ ! -f "$PROJECT_DIR/$MIGRATION_FILE" ]; then
    echo "Error: Migration file not found: $MIGRATION_FILE"
    exit 1
fi

cd "$PROJECT_DIR"

python3 << PYEOF
import asyncio
import sys
sys.path.insert(0, '$PROJECT_DIR/src')

from nhl_api.services.db import DatabaseService

async def run_migration():
    db = DatabaseService()
    await db.connect()

    with open('$MIGRATION_FILE', 'r') as f:
        sql = f.read()

    try:
        await db.execute(sql)
        print(f'Migration {repr("$MIGRATION_FILE")} completed successfully!')
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)
    finally:
        await db.disconnect()

asyncio.run(run_migration())
PYEOF
