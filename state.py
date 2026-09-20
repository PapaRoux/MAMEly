"""App-level SQLite state: settings, per-platform cursor, play sessions.

Game catalogs stay in platforms/<P>/MAMEly.db. This file is the cabinet's
memory: F3 settings, where you left off, and what you actually played.
"""
import os
import sqlite3
from mamely_log import get_logger

log = get_logger("state")

STATE_FILENAME = "mamely-state.db"

SETTING_KEYS = (
    "remember_emulator",
    "remember_game",
    "play_demo_video",
    "attract_mode",
)


def _connect(path):
    conn = sqlite3.connect(path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


class MamelyState:
    def __init__(self, base_path):
        self.base_path = base_path
        self.path = os.path.join(base_path, STATE_FILENAME)
        self._ensure()

    def _ensure(self):
        with _connect(self.path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS last_position (
                    platform TEXT PRIMARY KEY,
                    genre TEXT DEFAULT '',
                    rom TEXT DEFAULT '',
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS play_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    rom TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_sec REAL,
                    exit_code INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_play_sessions_started
                    ON play_sessions(started_at);
                """
            )

    def get_setting(self, key, default=True):
        with _connect(self.path) as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        return row[0] in ("1", "true", "True", "yes", "on")

    def set_setting(self, key, value):
        with _connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, "1" if value else "0"),
            )
        log.debug("state setting %s=%s", key, value)

    def settings_empty(self):
        with _connect(self.path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM settings").fetchone()
        return not row or row[0] == 0

    def pull_into_config(self, config):
        """Overlay settings from the state DB. Migrate from XML on first run."""
        if self.settings_empty():
            self.push_from_config(config)
            log.info("migrated settings into %s", self.path)
            return
        config.remember_emulator = self.get_setting("remember_emulator", True)
        config.remember_game = self.get_setting("remember_game", True)
        config.play_demo_video = self.get_setting("play_demo_video", True)
        config.attract_mode = self.get_setting("attract_mode", True)

    def push_from_config(self, config):
        for key in SETTING_KEYS:
            self.set_setting(key, bool(getattr(config, key, True)))

    def save_position(self, platform, genre, rom):
        if not platform:
            return
        with _connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO last_position (platform, genre, rom, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (platform, genre or "", rom or ""),
            )
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_platform', ?)",
                (platform,),
            )

    def get_position(self, platform):
        with _connect(self.path) as conn:
            row = conn.execute(
                "SELECT genre, rom FROM last_position WHERE platform = ?",
                (platform,),
            ).fetchone()
        if not row:
            return "", ""
        return row[0] or "", row[1] or ""

    def get_last_platform(self):
        with _connect(self.path) as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'last_platform'"
            ).fetchone()
        return (row[0] if row else "") or ""

    def start_play(self, platform, rom):
        with _connect(self.path) as conn:
            cur = conn.execute(
                """
                INSERT INTO play_sessions (platform, rom, started_at)
                VALUES (?, ?, datetime('now'))
                """,
                (platform, rom),
            )
            session_id = cur.lastrowid
        log.debug("play session start id=%s platform=%s rom=%s", session_id, platform, rom)
        return session_id

    def end_play(self, session_id, exit_code, duration_sec):
        if not session_id:
            return
        with _connect(self.path) as conn:
            conn.execute(
                """
                UPDATE play_sessions
                   SET ended_at = datetime('now'),
                       duration_sec = ?,
                       exit_code = ?
                 WHERE id = ?
                """,
                (duration_sec, exit_code, session_id),
            )
        log.debug(
            "play session end id=%s rc=%s duration=%.1fs",
            session_id, exit_code, duration_sec or 0,
        )
