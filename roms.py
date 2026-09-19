import os
import sqlite3
import datetime
import operator

class Rom:
    def __init__(self, name, description, genre="General", rating="General",
                 favorite=0, ignore=0, play_count=0, last_played=None, custom_flags=""):
        self.name = name
        self.description = description
        self.genre = genre
        self.rating = rating
        self.favorite = int(favorite)
        self.ignore = int(ignore)
        self.play_count = int(play_count)
        self.last_played = last_played
        self.custom_flags = custom_flags or ""

class RomManager:
    def __init__(self, platform_path, platform_config):
        self.platform_path = platform_path
        self.config = platform_config
        self.db_path = os.path.join(self.platform_path, "MAMEly.db")
        self.roms = {}  # Dictionary of name -> Rom object
        self.genres = set()
        self.ratings = set()
        
        # Lists for special filtering
        self.skip_genres = set()
        self.skip_ratings = set()
        self.flag_options = {}

        self._ensure_db()

    def _ensure_db(self):
        """Initializes SQLite schema and handles automatic migration if needed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
                
                # Check if empty
                cur.execute("SELECT COUNT(*) FROM games")
                count = cur.fetchone()[0]
                
                if count == 0:
                    # Look for XML to auto-migrate
                    xml_path = os.path.join(self.platform_path, "MAMEly.xml")
                    example_xml_path = os.path.join(self.platform_path, "MAMEly.example.xml")
                    src_xml = xml_path if os.path.exists(xml_path) else (example_xml_path if os.path.exists(example_xml_path) else None)
                    
                    if src_xml:
                        self._migrate_xml_to_sqlite(src_xml, conn)
        except Exception as e:
            print(f"Error initializing SQLite database {self.db_path}: {e}")

    def _migrate_xml_to_sqlite(self, xml_path, conn):
        """Helper to migrate legacy XML file to SQLite database."""
        try:
            import xml.etree.ElementTree as ET
            print(f"Auto-migrating legacy XML {xml_path} to SQLite...")
            
            # Check for companion txt files to ensure 100% data preservation
            fav_set = set()
            fav_file = os.path.join(self.platform_path, "favorites.txt")
            if os.path.exists(fav_file):
                with open(fav_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            fav_set.add(line)

            ign_set = set()
            ign_file = os.path.join(self.platform_path, "ignore.txt")
            if os.path.exists(ign_file):
                with open(ign_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            ign_set.add(line)

            flags_dict = {}
            flags_file = os.path.join(self.platform_path, "_flags.txt")
            if os.path.exists(flags_file):
                with open(flags_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "#" not in line and "=" in line:
                            parts = line.split("=", 1)
                            flags_dict[parts[0].strip()] = parts[1].strip()

            tree = ET.parse(xml_path)
            root = tree.getroot()
            rows = []
            for child in root.findall("game"):
                name = child.attrib.get("name")
                desc = child.findtext("description", "").title()
                genre = child.findtext("genre", "General").title()
                if "/" in genre:
                    genre = genre.split("/")[0].strip()
                rating = child.findtext("rating", "General")
                fav = int(child.findtext("favorite", "0") or "0")
                ign = int(child.findtext("ignore", "0") or "0")

                if name in fav_set:
                    fav = 1
                if name in ign_set:
                    ign = 1
                flags = flags_dict.get(name, "")

                rows.append((name, desc, genre, rating, fav, ign, 0, None, flags))
            
            cur = conn.cursor()
            cur.executemany("""
                INSERT OR REPLACE INTO games (name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            print(f"Auto-migrated {len(rows)} games into {self.db_path}")
        except Exception as e:
            print(f"Failed to auto-migrate XML to SQLite: {e}")

    def load_skips_and_flags(self):
        """Load skip lists and run flags from files."""
        # Flags
        try:
            flag_path = os.path.join(self.platform_path, "_flags.txt")
            if os.path.exists(flag_path):
                with open(flag_path, "r") as f:
                    for line in f:
                        if "#" not in line and "=" in line:
                            parts = line.split("=", 1)
                            self.flag_options[parts[0].strip()] = parts[1].strip()
        except Exception:
            pass

        # Skip Genre
        try:
            skip_gen_path = os.path.join(self.platform_path, "_skipGenre.txt")
            if os.path.exists(skip_gen_path):
                with open(skip_gen_path, "r") as f:
                    for line in f:
                        if "#" not in line:
                            self.skip_genres.add(line.strip())
        except Exception:
            pass

        # Skip Rating
        try:
            skip_rat_path = os.path.join(self.platform_path, "_skipRating.txt")
            if os.path.exists(skip_rat_path):
                with open(skip_rat_path, "r") as f:
                    for line in f:
                        if "#" not in line:
                            self.skip_ratings.add(line.strip())
        except Exception:
            pass

    def load_roms(self, callback_progress=None):
        """Load ROMs from SQLite database with optional directory comparison."""
        self.roms = {}
        self.genres.clear()
        self.ratings.clear()
        db_roms = {}

        if not os.path.exists(self.db_path):
            self._ensure_db()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags
                    FROM games
                """)
                rows = cur.fetchall()
                total_nodes = len(rows)

                for i, row in enumerate(rows):
                    name, desc, genre, rating, favorite, ignore, play_count, last_played, custom_flags = row
                    
                    if not genre:
                        genre = "General"
                    if not rating:
                        rating = "General"

                    # Filtering Logic
                    if genre in self.skip_genres:
                        continue
                    if "Ttl -" in genre:
                        continue
                    if rating in self.skip_ratings:
                        continue

                    rom_obj = Rom(
                        name=name,
                        description=desc,
                        genre=genre,
                        rating=rating,
                        favorite=favorite,
                        ignore=ignore,
                        play_count=play_count,
                        last_played=last_played,
                        custom_flags=custom_flags
                    )
                    db_roms[name] = rom_obj

                    if genre != "General":
                        self.genres.add(genre)
                    if rating != "General":
                        self.ratings.add(rating)

                    if callback_progress and total_nodes > 0:
                        callback_progress((i + 1) / total_nodes * 100)

        except Exception as e:
            print(f"Error loading ROMs from SQLite database {self.db_path}: {e}")

        # Directory Comparison Logic
        if self.config.compare_xml_to_roms:
            self.roms = {}
            if os.path.exists(self.config.rom_directory):
                with os.scandir(self.config.rom_directory) as it:
                    for entry in it:
                        if entry.is_file():
                            f = entry.name
                            base_name = f
                            if self.config.rom_extension and self.config.rom_extension in f:
                                base_name = f.replace(self.config.rom_extension, "")

                            if base_name in db_roms:
                                self.roms[base_name] = db_roms[base_name]
                            elif f in db_roms:
                                self.roms[f] = db_roms[f]
        else:
            self.roms = db_roms

    def toggle_favorite(self, rom_name):
        """Toggle favorite status in memory and persist immediately to SQLite."""
        if rom_name in self.roms:
            rom = self.roms[rom_name]
            rom.favorite = 1 - rom.favorite
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("UPDATE games SET favorite = ? WHERE name = ?", (rom.favorite, rom_name))
                # Sync text list for companion tooling
                self._sync_txt_lists()
            except Exception as e:
                print(f"Error updating favorite in database: {e}")
            return rom.favorite == 1
        return False

    def toggle_ignore(self, rom_name):
        """Toggle ignore status in memory and persist immediately to SQLite."""
        if rom_name in self.roms:
            rom = self.roms[rom_name]
            rom.ignore = 1 - rom.ignore
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("UPDATE games SET ignore = ? WHERE name = ?", (rom.ignore, rom_name))
                self._sync_txt_lists()
            except Exception as e:
                print(f"Error updating ignore in database: {e}")
            return rom.ignore == 1
        return False

    def record_play(self, rom_name):
        """Increment play count and update last played timestamp."""
        if rom_name in self.roms:
            rom = self.roms[rom_name]
            rom.play_count += 1
            now = datetime.datetime.now().isoformat()
            rom.last_played = now
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "UPDATE games SET play_count = play_count + 1, last_played = ? WHERE name = ?",
                        (now, rom_name)
                    )
            except Exception as e:
                print(f"Error recording play stats for {rom_name}: {e}")

    def _sync_txt_lists(self):
        """Write out companion favorites.txt and ignore.txt lists."""
        try:
            fav_path = os.path.join(self.platform_path, "favorites.txt")
            ign_path = os.path.join(self.platform_path, "ignore.txt")
            with open(fav_path, "w") as f_fav, open(ign_path, "w") as f_ign:
                for rom in self.roms.values():
                    if rom.favorite == 1:
                        f_fav.write(f"{rom.name}\n")
                    if rom.ignore == 1:
                        f_ign.write(f"{rom.name}\n")
        except Exception:
            pass

    def get_genre_list(self):
        """Return sorted list of genres including dynamic playlist categories."""
        genre_list = sorted(list(self.genres))
        has_played = any(r.play_count > 0 for r in self.roms.values())
        has_recent = any(r.last_played for r in self.roms.values())

        full_list = ["All Games", "Favorites"]
        if has_played:
            full_list.append("Most Played")
        if has_recent:
            full_list.append("Recently Played")
        full_list.extend(genre_list)
        full_list.append("Ignore")
        return full_list

    def get_roms_by_genre(self, genre_name):
        """Return filtered list of ROMs for a given playlist / genre category."""
        results = []
        sorted_roms = sorted(self.roms.values(), key=operator.attrgetter('description'))

        if genre_name == "All Games":
            return [rom for rom in sorted_roms if rom.ignore == 0]
        elif genre_name == "Favorites":
            return [rom for rom in sorted_roms if rom.favorite == 1 and rom.ignore == 0]
        elif genre_name == "Most Played":
            played_roms = [rom for rom in self.roms.values() if rom.play_count > 0 and rom.ignore == 0]
            return sorted(played_roms, key=operator.attrgetter('play_count'), reverse=True)
        elif genre_name == "Recently Played":
            recent_roms = [rom for rom in self.roms.values() if rom.last_played and rom.ignore == 0]
            return sorted(recent_roms, key=lambda r: str(r.last_played), reverse=True)
        elif genre_name == "Ignore":
            return [rom for rom in sorted_roms if rom.ignore == 1]
        else:
            return [rom for rom in sorted_roms if rom.genre == genre_name and rom.ignore == 0]

    def get_rom_flags(self, rom_name):
        """Return emulator run flags for the specified ROM."""
        if rom_name in self.roms and self.roms[rom_name].custom_flags:
            return self.roms[rom_name].custom_flags
        return self.flag_options.get(rom_name, "")
