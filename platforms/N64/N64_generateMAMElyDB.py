#!/usr/bin/env python3
import os
import sys
import sqlite3

def generate_n64_db(platform_dir=None):
    if platform_dir is None:
        platform_dir = os.path.dirname(os.path.abspath(__file__))

    romlist_path = os.path.join(platform_dir, "romlist.txt")
    db_path = os.path.join(platform_dir, "MAMEly.db")

    print(f"Generating N64 database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            genre TEXT DEFAULT 'General',
            rating TEXT DEFAULT 'General',
            favorite INTEGER DEFAULT 0,
            ignore INTEGER DEFAULT 0,
            play_count INTEGER DEFAULT 0,
            last_played TIMESTAMP,
            custom_flags TEXT DEFAULT ''
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_genre ON games(genre)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_favorite ON games(favorite)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_ignore ON games(ignore)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_games_description ON games(description)")

    existing_meta = {}
    try:
        cur.execute("SELECT name, favorite, ignore, play_count, last_played, custom_flags FROM games")
        for row in cur.fetchall():
            existing_meta[row[0]] = (row[1], row[2], row[3], row[4], row[5])
    except Exception:
        pass

    rows = []
    if os.path.exists(romlist_path):
        with open(romlist_path, "r", encoding="utf-8", errors="ignore") as f_in:
            for textline in f_in:
                textline = textline.strip()
                if not textline:
                    continue
                # Support .z64, .v64, .n64
                matched_ext = None
                for ext in (".z64", ".v64", ".n64", ".zip"):
                    if ext in textline.lower():
                        matched_ext = ext
                        break
                
                raw_title = textline
                if matched_ext:
                    raw_title = textline.replace(matched_ext, "")
                raw_title = raw_title.replace("&", "and").replace("*", "-").strip()
                rom_name = textline
                desc = raw_title.replace("_", " ").title()

                if rom_name in existing_meta:
                    fav, ign, pc, lp, flags = existing_meta[rom_name]
                else:
                    fav, ign, pc, lp, flags = 0, 0, 0, None, ""

                rows.append((rom_name, desc, "General", "Rating: General", fav, ign, pc, lp, flags))

    if rows:
        cur.executemany("""
            INSERT OR REPLACE INTO games (name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        conn.commit()

    total_count = cur.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    conn.close()
    print(f"Successfully compiled {total_count} N64 games into {db_path}!\n")

if __name__ == "__main__":
    generate_n64_db()
