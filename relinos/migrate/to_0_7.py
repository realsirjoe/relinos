import sqlite3
from contextlib import closing

from relinos.config import cacheDBPath

if __name__ == "__main__":
    with closing(sqlite3.connect(cacheDBPath)) as conn, conn:
        columns = conn.execute("PRAGMA table_info(cache)").fetchall()
        if not any(col[1] == "sessionSignature" for col in columns):
            conn.execute("ALTER TABLE cache ADD COLUMN sessionSignature TEXT;")
