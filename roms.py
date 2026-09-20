import os
import sqlite3
import datetime
from mamely_log import get_logger

log = get_logger("roms")

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
        self._disk_names = None  # None = no directory filter

        self._ensure_db()

    def _ensure_db(self):
        """Initializes SQLite schema and handles automatic migration if needed."""
        try:
            with self._connect() as conn:
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
        except Exception:
            log.exception("error initializing SQLite database path=%s", self.db_path)

    def _migrate_xml_to_sqlite(self, xml_path, conn):
        """Helper to migrate legacy XML file to SQLite database."""
        try:
            import xml.etree.ElementTree as ET
            log.info("auto-migrating legacy XML path=%s", xml_path)
            
            fav_set, ign_set, plays = read_user_backup(self.platform_path)

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
                play_count, last_played = 0, None
                if name in plays:
                    play_count, last_played = plays[name]
                flags = flags_dict.get(name, "")

                rows.append((name, desc, genre, rating, fav, ign, play_count, last_played, flags))
            
            cur = conn.cursor()
            cur.executemany("""
                INSERT OR REPLACE INTO games (name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            log.info("auto-migrated games=%d db=%s", len(rows), self.db_path)
        except Exception:
            log.exception("failed to auto-migrate XML path=%s", xml_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @staticmethod
    def _row_to_rom(row):
        name, desc, genre, rating, favorite, ignore, play_count, last_played, custom_flags = row
        return Rom(
            name=name,
            description=desc or "",
            genre=genre or "General",
            rating=rating or "General",
            favorite=favorite,
            ignore=ignore,
            play_count=play_count,
            last_played=last_played,
            custom_flags=custom_flags or "",
        )

    def _skip_sql(self):
        clauses = ["(genre IS NULL OR genre NOT LIKE 'Ttl -%')"]
        params = []
        if self.skip_genres:
            placeholders = ",".join("?" * len(self.skip_genres))
            clauses.append(f"(genre IS NULL OR genre NOT IN ({placeholders}))")
            params.extend(self.skip_genres)
        if self.skip_ratings:
            placeholders = ",".join("?" * len(self.skip_ratings))
            clauses.append(f"(rating IS NULL OR rating NOT IN ({placeholders}))")
            params.extend(self.skip_ratings)
        return " AND ".join(clauses), params

    def _on_disk(self, name):
        if self._disk_names is None:
            return True
        return name in self._disk_names

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
        """Open the catalog and optional on-disk filter. Playlists are queried live."""
        self.roms = {}
        self.genres.clear()
        self.ratings.clear()
        self._disk_names = None

        if not os.path.exists(self.db_path):
            self._ensure_db()

        if self.config.compare_xml_to_roms:
            names = set()
            rom_dir = self.config.rom_directory
            ext = self.config.rom_extension or ""
            if rom_dir and os.path.exists(rom_dir):
                with os.scandir(rom_dir) as it:
                    for entry in it:
                        if not entry.is_file():
                            continue
                        names.add(entry.name)
                        if ext and entry.name.endswith(ext):
                            names.add(entry.name[: -len(ext)] if ext.startswith(".") else entry.name.replace(ext, ""))
            self._disk_names = names
            log.info("roms directory filter names=%d dir=%s", len(names), rom_dir)

        try:
            total, favs, ignored = self.counts()
            log.debug("catalog ready db=%s count=%d favorites=%d ignored=%d", self.db_path, total, favs, ignored)
        except Exception:
            log.exception("error reading catalog path=%s", self.db_path)
        if callback_progress:
            callback_progress(100)

    def counts(self):
        """(total, favorites, ignored) from SQLite, honoring skip/disk filters in Python for disk."""
        skip_sql, skip_params = self._skip_sql()
        try:
            with self._connect() as conn:
                total = conn.execute(f"SELECT COUNT(*) FROM games WHERE {skip_sql}", skip_params).fetchone()[0]
                favs = conn.execute(
                    f"SELECT COUNT(*) FROM games WHERE favorite = 1 AND {skip_sql}", skip_params
                ).fetchone()[0]
                ignored = conn.execute(
                    f"SELECT COUNT(*) FROM games WHERE ignore = 1 AND {skip_sql}", skip_params
                ).fetchone()[0]
            return total, favs, ignored
        except Exception:
            log.exception("error counting games path=%s", self.db_path)
            return 0, 0, 0

    def toggle_favorite(self, rom_name):
        """Toggle favorite in SQLite and refresh the rebuild backup files."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE games SET favorite = 1 - favorite WHERE name = ?",
                    (rom_name,),
                )
                row = conn.execute(
                    "SELECT favorite FROM games WHERE name = ?", (rom_name,)
                ).fetchone()
            self._sync_user_backup()
            is_fav = bool(row and row[0] == 1)
            if rom_name in self.roms:
                self.roms[rom_name].favorite = 1 if is_fav else 0
            return is_fav
        except Exception:
            log.exception("error updating favorite rom=%s", rom_name)
            return False

    def toggle_ignore(self, rom_name):
        """Toggle ignore in SQLite and refresh the rebuild backup files."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE games SET ignore = 1 - ignore WHERE name = ?",
                    (rom_name,),
                )
                row = conn.execute(
                    "SELECT ignore FROM games WHERE name = ?", (rom_name,)
                ).fetchone()
            self._sync_user_backup()
            is_ign = bool(row and row[0] == 1)
            if rom_name in self.roms:
                self.roms[rom_name].ignore = 1 if is_ign else 0
            return is_ign
        except Exception:
            log.exception("error updating ignore rom=%s", rom_name)
            return False

    def record_play(self, rom_name):
        """Increment play count and update last played timestamp."""
        now = datetime.datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE games SET play_count = play_count + 1, last_played = ? WHERE name = ?",
                    (now, rom_name),
                )
                row = conn.execute(
                    "SELECT play_count, last_played FROM games WHERE name = ?",
                    (rom_name,),
                ).fetchone()
            if rom_name in self.roms and row:
                self.roms[rom_name].play_count = row[0]
                self.roms[rom_name].last_played = row[1]
            self._sync_user_backup()
            return row
        except Exception:
            log.exception("error recording play stats rom=%s", rom_name)
            return None

    def _sync_user_backup(self):
        """Write favorites/ignore/playstats text files so a DB rebuild can restore them."""
        try:
            skip_sql, skip_params = self._skip_sql()
            with self._connect() as conn:
                favs = [
                    r[0]
                    for r in conn.execute(
                        f"SELECT name FROM games WHERE favorite = 1 AND {skip_sql} ORDER BY name",
                        skip_params,
                    )
                ]
                igns = [
                    r[0]
                    for r in conn.execute(
                        f"SELECT name FROM games WHERE ignore = 1 AND {skip_sql} ORDER BY name",
                        skip_params,
                    )
                ]
                plays = conn.execute(
                    f"""SELECT name, play_count, last_played FROM games
                        WHERE play_count > 0 AND {skip_sql} ORDER BY name""",
                    skip_params,
                ).fetchall()
            write_user_backup(self.platform_path, favs, igns, plays)
        except Exception:
            log.exception("error syncing user backup lists")

    def get_genre_list(self):
        """Return sorted list of genres including dynamic playlist categories."""
        skip_sql, skip_params = self._skip_sql()
        genre_list = []
        has_played = False
        has_recent = False
        try:
            with self._connect() as conn:
                for (genre,) in conn.execute(
                    f"""SELECT DISTINCT genre FROM games
                        WHERE genre IS NOT NULL AND genre != '' AND genre != 'General'
                          AND {skip_sql}
                        ORDER BY genre COLLATE NOCASE""",
                    skip_params,
                ):
                    genre_list.append(genre)
                has_played = conn.execute(
                    f"SELECT 1 FROM games WHERE play_count > 0 AND ignore = 0 AND {skip_sql} LIMIT 1",
                    skip_params,
                ).fetchone() is not None
                has_recent = conn.execute(
                    f"SELECT 1 FROM games WHERE last_played IS NOT NULL AND last_played != '' AND ignore = 0 AND {skip_sql} LIMIT 1",
                    skip_params,
                ).fetchone() is not None
        except Exception:
            log.exception("error listing genres path=%s", self.db_path)

        full_list = ["All Games", "Favorites"]
        if has_played:
            full_list.append("Most Played")
        if has_recent:
            full_list.append("Recently Played")
        full_list.extend(genre_list)
        full_list.append("Ignore")
        return full_list

    def get_roms_by_genre(self, genre_name, search_query=""):
        """Return the current playlist from SQLite (not the whole catalog)."""
        skip_sql, params = self._skip_sql()
        where = [skip_sql]
        order = "description COLLATE NOCASE, name COLLATE NOCASE"

        if genre_name == "All Games":
            where.append("ignore = 0")
        elif genre_name == "Favorites":
            where.append("favorite = 1 AND ignore = 0")
        elif genre_name == "Most Played":
            where.append("play_count > 0 AND ignore = 0")
            order = "play_count DESC, description COLLATE NOCASE"
        elif genre_name == "Recently Played":
            where.append("last_played IS NOT NULL AND last_played != '' AND ignore = 0")
            order = "last_played DESC"
        elif genre_name == "Ignore":
            where.append("ignore = 1")
        else:
            where.append("genre = ? AND ignore = 0")
            params = list(params) + [genre_name]

        query = search_query.strip()
        if query:
            where.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{query}%"
            params = list(params) + [like, like]

        sql = f"""
            SELECT name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags
              FROM games
             WHERE {' AND '.join(where)}
             ORDER BY {order}
        """
        roms = []
        try:
            with self._connect() as conn:
                for row in conn.execute(sql, params):
                    if not self._on_disk(row[0]):
                        continue
                    roms.append(self._row_to_rom(row))
        except Exception:
            log.exception("error querying playlist genre=%s", genre_name)
        return roms

    def get_rom_flags(self, rom_name):
        """Return emulator run flags for the specified ROM."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT custom_flags FROM games WHERE name = ?", (rom_name,)
                ).fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            log.exception("error reading flags rom=%s", rom_name)
        return self.flag_options.get(rom_name, "")

    def find_snap(self, rom_name):
        return find_media_file(
            self.config.rom_snap_directory,
            rom_name,
            self.config.snap_extension,
            self.config.rom_extension,
        )

    def find_video(self, rom_name):
        return find_media_file(
            self.config.rom_video_directory,
            rom_name,
            self.config.video_extension,
            self.config.rom_extension,
        )


def _dot_ext(ext):
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def rom_media_stems(rom_name, rom_ext=""):
    """ROM key plus the same name with the ROM extension stripped.

    SNES/NES catalogs store `Act Raiser (U).smc`; snap files are `Act Raiser (U).png`.
    MAME catalogs store `pacman` with no extension, so the stem list is just that name.
    """
    names = []
    if not rom_name:
        return names
    names.append(rom_name)
    ext = _dot_ext(rom_ext)
    if ext and rom_name.lower().endswith(ext.lower()) and len(rom_name) > len(ext):
        stem = rom_name[: -len(ext)]
        if stem and stem not in names:
            names.append(stem)
    return names


def media_candidates(directory, rom_name, media_ext, rom_ext=""):
    if not directory or not media_ext:
        return []
    media_ext = _dot_ext(media_ext)
    paths = []
    seen = set()
    for name in rom_media_stems(rom_name, rom_ext):
        for path in (
            os.path.join(directory, name + media_ext),
            os.path.join(directory, name, "0000" + media_ext),
        ):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


def find_media_file(directory, rom_name, media_ext, rom_ext=""):
    for path in media_candidates(directory, rom_name, media_ext, rom_ext):
        if os.path.exists(path):
            return path
    return None


def read_user_backup(platform_path):
    """Load rebuild backups: favorites.txt, ignore.txt, playstats.txt."""
    fav, ign = set(), set()
    plays = {}
    fav_file = os.path.join(platform_path, "favorites.txt")
    if os.path.exists(fav_file):
        with open(fav_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    fav.add(line)
    ign_file = os.path.join(platform_path, "ignore.txt")
    if os.path.exists(ign_file):
        with open(ign_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ign.add(line)
    play_file = os.path.join(platform_path, "playstats.txt")
    if os.path.exists(play_file):
        with open(play_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    try:
                        count = int(parts[1])
                    except ValueError:
                        continue
                    last = parts[2] if len(parts) > 2 else None
                    plays[parts[0]] = (count, last or None)
    return fav, ign, plays


def write_user_backup(platform_path, fav_names, ign_names, play_rows):
    fav_path = os.path.join(platform_path, "favorites.txt")
    ign_path = os.path.join(platform_path, "ignore.txt")
    play_path = os.path.join(platform_path, "playstats.txt")
    with open(fav_path, "w", encoding="utf-8") as f_fav:
        for name in fav_names:
            f_fav.write(f"{name}\n")
    with open(ign_path, "w", encoding="utf-8") as f_ign:
        for name in ign_names:
            f_ign.write(f"{name}\n")
    with open(play_path, "w", encoding="utf-8") as f_play:
        f_play.write("# name, play_count, last_played — rebuild backup, not the live DB\n")
        for name, count, last in play_rows:
            f_play.write(f"{name}\t{count}\t{last or ''}\n")
