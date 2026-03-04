"""
Database migration runner Lambda.

Executes SQL migrations against Aurora PostgreSQL in order,
tracking completed migrations to avoid re-running.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import asyncpg
import boto3


async def _get_db_credentials() -> dict:
    """Fetch database credentials from Secrets Manager."""
    secret_arn = os.environ["DATABASE_SECRET_ARN"]
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])


async def _db_connect() -> asyncpg.Connection:
    """Connect to Aurora PostgreSQL."""
    creds = await _get_db_credentials()

    host = os.getenv("DB_HOST")
    port = int(os.getenv("DB_PORT", "5432"))
    database = os.getenv("DB_NAME", "platform_dev")

    return await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=creds["username"],
        password=creds["password"],
        timeout=30,
    )


async def _ensure_migrations_table(conn: asyncpg.Connection) -> None:
    """Create migrations tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(100) PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT NOW(),
            checksum VARCHAR(64)
        )
    """)


async def _get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    """Get set of already-applied migration versions."""
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {row["version"] for row in rows}


async def _apply_migration(
    conn: asyncpg.Connection,
    version: str,
    sql: str,
    checksum: str
) -> None:
    """Apply a single migration within a transaction."""
    async with conn.transaction():
        # Execute the migration SQL
        await conn.execute(sql)
        # Record the migration
        await conn.execute(
            "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
            version, checksum
        )


def _compute_checksum(content: str) -> str:
    """Compute SHA256 checksum of migration content."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _parse_migration_files(migrations_dir: str) -> list[tuple[str, str, str]]:
    """
    Parse migration files and return sorted list of (version, path, sql).

    Files should be named like: 001_description.sql, 002_description.sql
    """
    migrations = []
    migrations_path = Path(migrations_dir)

    if not migrations_path.exists():
        return []

    for sql_file in sorted(migrations_path.glob("*.sql")):
        version = sql_file.stem  # e.g., "001_bronze_layer"
        sql_content = sql_file.read_text()
        migrations.append((version, str(sql_file), sql_content))

    return migrations


async def run_migrations(migrations_dir: str) -> dict:
    """
    Run all pending migrations.

    Returns dict with applied migrations and any errors.
    """
    conn = await _db_connect()
    try:
        await _ensure_migrations_table(conn)
        applied = await _get_applied_migrations(conn)

        migrations = _parse_migration_files(migrations_dir)
        newly_applied = []
        skipped = []
        errors = []

        for version, path, sql in migrations:
            if version in applied:
                skipped.append(version)
                continue

            try:
                checksum = _compute_checksum(sql)
                await _apply_migration(conn, version, sql, checksum)
                newly_applied.append(version)
                print(f"Applied migration: {version}")
            except Exception as e:
                error_msg = f"Failed to apply {version}: {str(e)}"
                print(error_msg)
                errors.append(error_msg)
                # Stop on first error to maintain consistency
                break

        return {
            "status": "success" if not errors else "failed",
            "applied": newly_applied,
            "skipped": skipped,
            "errors": errors,
            "total_migrations": len(migrations),
        }
    finally:
        await conn.close()


def handler(event, context):
    """Lambda handler for running migrations."""
    # Migrations are bundled with the Lambda code
    # They should be at /var/task/database/migrations/
    migrations_dir = os.getenv(
        "MIGRATIONS_DIR",
        "/var/task/database/migrations"
    )

    print(f"Running migrations from: {migrations_dir}")
    result = asyncio.run(run_migrations(migrations_dir))
    print(f"Migration result: {json.dumps(result, indent=2)}")

    if result["status"] == "failed":
        raise Exception(f"Migration failed: {result['errors']}")

    return result
