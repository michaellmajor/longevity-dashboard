import sqlite3
import os

DB_PATH = os.path.expanduser("~/Documents/longevity-dashboard/longevity.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS daily_briefs (
    date TEXT PRIMARY KEY,
    verdict TEXT,
    brief TEXT,
    garmin_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
print(f"Database created at {DB_PATH}")
