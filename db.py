"""Shared database helpers for the longevity dashboard.

- get_cloud_db()  -> connects to Turso (libSQL) via TURSO_DB_URL / TURSO_AUTH_TOKEN
- get_local_db()  -> connects to the local SQLite file
- init_db(conn)   -> creates the daily_briefs table if it does not exist
"""

import os
import sqlite3

LOCAL_DB_PATH = os.path.expanduser("~/Documents/longevity-dashboard/longevity.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_briefs (
    date TEXT PRIMARY KEY,
    verdict TEXT,
    brief TEXT,
    garmin_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def get_cloud_db():
    """Return a connection to the Turso cloud database.

    Reads TURSO_DB_URL and TURSO_AUTH_TOKEN from the environment.
    Raises RuntimeError if either is missing.
    """
    import libsql_experimental as libsql

    url = os.environ.get("TURSO_DB_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if not url or not token:
        raise RuntimeError(
            "TURSO_DB_URL and TURSO_AUTH_TOKEN must both be set to use the cloud database."
        )
    return libsql.connect(database=url, auth_token=token)


def get_local_db():
    """Return a connection to the local SQLite database."""
    return sqlite3.connect(LOCAL_DB_PATH)


def init_db(conn):
    """Create the daily_briefs table if it does not already exist."""
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn
