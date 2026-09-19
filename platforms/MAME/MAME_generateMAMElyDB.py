#!/usr/bin/env python3
import os
import sys
import sqlite3
import subprocess
import tarfile
import xml.etree.ElementTree as ET

def extract_listxml_if_needed(platform_dir):
    listxml_path = os.path.join(platform_dir, "mame-listxml.xml")
    if os.path.exists(listxml_path) and os.path.getsize(listxml_path) > 1000000:
        return listxml_path

    archive_path = os.path.join(platform_dir, "mame-listxml.xml.tar.7z")
    if os.path.exists(archive_path):
        print("      Extracting mame-listxml.xml from archive...")
        try:
            cmd = ["7z", "e", archive_path, "-so"]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            with tarfile.open(fileobj=p.stdout, mode="r|*") as tar:
                tar.extractall(platform_dir)
            if os.path.exists(listxml_path):
                return listxml_path
        except Exception as e:
            print(f"      Extraction error: {e}")
    return listxml_path if os.path.exists(listxml_path) else None

def generate_mame_db(platform_dir=None):
    if platform_dir is None:
        platform_dir = os.path.dirname(os.path.abspath(__file__))

    catver_path = os.path.join(platform_dir, "catver.ini")
    db_path = os.path.join(platform_dir, "MAMEly.db")
    fav_path = os.path.join(platform_dir, "favorites.txt")
    ign_path = os.path.join(platform_dir, "ignore.txt")

    print(f"[1/4] Reading catver.ini from {catver_path}...")
    categories = {}
    mature_set = set()

    if os.path.exists(catver_path):
        with open(catver_path, "r", encoding="utf-8", errors="ignore") as f:
            in_categories = False
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_categories = (line == "[Category]")
                    continue
                if in_categories and "=" in line:
                    rom_name, genre_string = line.split("=", 1)
                    rom_name = rom_name.strip()
                    genre_string = genre_string.strip().replace("*", "-")
                    if "- Mature -" in genre_string:
                        mature_set.add(rom_name)
                    slash_pos = genre_string.find(" / ")
                    if slash_pos >= 0:
                        genre = genre_string[:slash_pos].replace("&", "and").strip()
                    else:
                        genre = genre_string.replace("&", "and").strip()
                    categories[rom_name] = genre
        print(f"      Parsed {len(categories)} categories ({len(mature_set)} mature titles)")
    else:
        print("      catver.ini not found! Skipping category mapping.")

    print(f"[2/4] Parsing MAME machine titles...")
    machines = {}
    listxml_path = extract_listxml_if_needed(platform_dir)

    if listxml_path and os.path.exists(listxml_path):
        print(f"      Reading {listxml_path}...")
        try:
            for event, elem in ET.iterparse(listxml_path, events=("end",)):
                if elem.tag == "machine":
                    rom_name = elem.attrib.get("name")
                    desc_elem = elem.find("description")
                    if desc_elem is not None and desc_elem.text:
                        desc = desc_elem.text.title().replace("&", "and").strip()
                        machines[rom_name] = desc
                    elem.clear()
            print(f"      Extracted {len(machines)} descriptions from XML.")
        except Exception as e:
            print(f"      Error reading mame-listxml.xml: {e}")

    # Fallback 1: Query mame executable if available
    if not machines:
        print("      Attempting extraction via 'mame -listfull'...")
        try:
            res = subprocess.run(["mame", "-listfull"], capture_output=True, text=True)
            if res.returncode == 0:
                for line in res.stdout.splitlines()[1:]:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        r_name, r_desc = parts[0], parts[1].strip('"')
                        machines[r_name] = r_desc.title().replace("&", "and").strip()
                print(f"      Extracted {len(machines)} descriptions from mame CLI.")
        except Exception:
            pass

    # Fallback 2: Check legacy example XML if present
    if not machines:
        example_xml = os.path.join(platform_dir, "MAMEly.example.xml")
        if os.path.exists(example_xml):
            print(f"      Reading titles from {example_xml}...")
            try:
                tree = ET.parse(example_xml)
                for child in tree.getroot().findall("game"):
                    r_name = child.attrib.get("name")
                    r_desc = child.findtext("description", "").title().replace("&", "and").strip()
                    if r_name and r_desc:
                        machines[r_name] = r_desc
                print(f"      Extracted {len(machines)} descriptions from example XML.")
            except Exception:
                pass

    # Fallback 3: Cleaned ROM names if everything else failed
    if not machines and categories:
        for rom_name in categories:
            machines[rom_name] = rom_name.replace("_", " ").title()

    print(f"[3/4] Reading favorites and ignore lists...")
    favorites_set = set()
    if os.path.exists(fav_path):
        with open(fav_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    favorites_set.add(line)
        print(f"      Loaded {len(favorites_set)} favorites from favorites.txt")

    ignore_set = set()
    if os.path.exists(ign_path):
        with open(ign_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ignore_set.add(line)
        print(f"      Loaded {len(ignore_set)} ignores from ignore.txt")

    print(f"[4/4] Compiling SQLite database at {db_path}...")
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

    # Preserve existing user stats if updating an existing DB
    existing_meta = {}
    try:
        cur.execute("SELECT name, favorite, ignore, play_count, last_played, custom_flags FROM games")
        for row in cur.fetchall():
            existing_meta[row[0]] = (row[1], row[2], row[3], row[4], row[5])
    except Exception:
        pass

    rows_to_insert = []
    # If machines is populated, use machines; else use categories
    keys = machines.keys() if machines else categories.keys()

    for rom_name in keys:
        description = machines.get(rom_name) or rom_name.replace("_", " ").title()
        genre = categories.get(rom_name, "General")
        is_mature = rom_name in mature_set
        rating = "Rating: Mature" if is_mature else "Rating: General"

        # Check existing metadata vs text files
        if rom_name in existing_meta:
            fav, ign, pc, lp, flags = existing_meta[rom_name]
        else:
            fav, ign, pc, lp, flags = 0, 0, 0, None, ""

        if rom_name in favorites_set:
            fav = 1
        if rom_name in ignore_set:
            ign = 1

        rows_to_insert.append((rom_name, description, genre, rating, fav, ign, pc, lp, flags))

    cur.executemany("""
        INSERT OR REPLACE INTO games (name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    conn.commit()
    total_count = cur.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    fav_count = cur.execute("SELECT COUNT(*) FROM games WHERE favorite = 1").fetchone()[0]
    conn.close()

    print(f"Successfully compiled {total_count} games ({fav_count} favorites) into {db_path}!\n")

if __name__ == "__main__":
    generate_mame_db()
