#!/usr/bin/env python3
import os
import sys
import sqlite3

def generate_c64_db(platform_dir=None):
    if platform_dir is None:
        platform_dir = os.path.dirname(os.path.abspath(__file__))

    romlist_path = os.path.join(platform_dir, "romlist.txt")
    db_path = os.path.join(platform_dir, "MAMEly.db")

    # If romlist.txt doesn't exist, populate it from /mnt/8TB/platforms/c64/roms
    rom_source_dir = "/mnt/8TB/platforms/c64/roms"
    if not os.path.exists(romlist_path) and os.path.isdir(rom_source_dir):
        print(f"Creating romlist.txt from {rom_source_dir}...")
        files = sorted(os.listdir(rom_source_dir))
        with open(romlist_path, "w", encoding="utf-8") as f_out:
            for f in files:
                if f.lower().endswith((".zip", ".d64", ".t64", ".prg", ".crt", ".tap")):
                    f_out.write(f + "\n")

    print(f"Generating Commodore 64 database at {db_path}...")
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

    # Preserve existing user favorites/ignores/stats
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
                matched_ext = None
                for ext in (".zip", ".d64", ".t64", ".prg", ".crt", ".tap"):
                    if textline.lower().endswith(ext):
                        matched_ext = ext
                        break
                
                raw_title = textline
                if matched_ext:
                    raw_title = textline[:-len(matched_ext)]
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
    print(f"Successfully compiled {total_count} Commodore 64 games into {db_path}!\n")

if __name__ == "__main__":
    generate_c64_db()
