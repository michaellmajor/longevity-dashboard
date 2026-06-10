#!/usr/bin/env python3
"""Save a daily brief to both the local SQLite DB and the Turso cloud DB.

Inputs:
  - last_garmin.json   (in this script's directory) -> stored in garmin_json
  - /tmp/last_brief.txt                              -> stored in brief

The first non-empty line of the brief is stored as `verdict`; the full text
is stored as `brief`. The date comes from the garmin JSON ("date") and falls
back to today.

The local save must always succeed. The cloud save is best-effort: if Turso
fails (or the credentials are not set) a warning is printed to stderr and the
script keeps going.

Prints a JSON confirmation object to stdout.
"""

import json
import os
import sys
from datetime import date

import db

HERE = os.path.dirname(os.path.abspath(__file__))
GARMIN_JSON_PATH = os.path.join(HERE, "last_garmin.json")
BRIEF_PATH = "/tmp/last_brief.txt"

UPSERT_SQL = """
INSERT INTO daily_briefs (date, verdict, brief, garmin_json)
VALUES (?, ?, ?, ?)
ON CONFLICT(date) DO UPDATE SET
    verdict = excluded.verdict,
    brief = excluded.brief,
    garmin_json = excluded.garmin_json
"""


def load_inputs():
    with open(GARMIN_JSON_PATH, "r") as f:
        garmin_raw = f.read()
    try:
        garmin = json.loads(garmin_raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: {GARMIN_JSON_PATH} is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(BRIEF_PATH, "r") as f:
            brief = f.read().strip()
    except FileNotFoundError:
        brief = ""

    brief_date = garmin.get("date") or date.today().isoformat()
    verdict = next((line.strip() for line in brief.splitlines() if line.strip()), "")
    return brief_date, verdict, brief, garmin_raw


def save_local(row):
    conn = db.get_local_db()
    db.init_db(conn)
    conn.execute(UPSERT_SQL, row)
    conn.commit()
    conn.close()


def save_cloud(row):
    """Best-effort cloud save. Returns the status string for the confirmation."""
    if not (os.environ.get("TURSO_DB_URL") and os.environ.get("TURSO_AUTH_TOKEN")):
        print("WARNING: TURSO_DB_URL/TURSO_AUTH_TOKEN not set; skipping cloud save.",
              file=sys.stderr)
        return "skipped"
    try:
        conn = db.get_cloud_db()
        db.init_db(conn)
        conn.execute(UPSERT_SQL, row)
        conn.commit()
        return "ok"
    except Exception as e:  # noqa: BLE001 - cloud must never crash the local save
        print(f"WARNING: cloud save to Turso failed: {e}", file=sys.stderr)
        return "error"


def main():
    brief_date, verdict, brief, garmin_raw = load_inputs()
    row = (brief_date, verdict, brief, garmin_raw)

    save_local(row)          # must succeed (exceptions here are fatal, by design)
    cloud_status = save_cloud(row)

    print(json.dumps({
        "date": brief_date,
        "verdict": verdict,
        "local": "ok",
        "cloud": cloud_status,
    }))


if __name__ == "__main__":
    main()
