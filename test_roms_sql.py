#!/usr/bin/env python3
"""SQL playlist queries, toggles, and rebuild-backup files."""
import os
import sqlite3
import tempfile

from roms import RomManager, read_user_backup, write_user_backup


class FakeCfg:
    compare_xml_to_roms = False
    rom_directory = ""
    rom_extension = ".zip"
    emulator_base_path = ""


def _seed(db_path, rows):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS games (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                genre TEXT DEFAULT 'General',
                rating TEXT DEFAULT 'General',
                favorite INTEGER DEFAULT 0,
                ignore INTEGER DEFAULT 0,
                play_count INTEGER DEFAULT 0,
                last_played TIMESTAMP,
                custom_flags TEXT DEFAULT ''
            )"""
        )
        conn.executemany(
            """INSERT INTO games
               (name, description, genre, rating, favorite, ignore, play_count, last_played, custom_flags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )


def test_playlists_search_and_backup():
    with tempfile.TemporaryDirectory() as tmp:
        _seed(
            os.path.join(tmp, "MAMEly.db"),
            [
                ("smw.zip", "Super Mario World", "Platform", "E", 1, 0, 3, "2024-01-01", ""),
                ("zelda.zip", "The Legend Of Zelda", "Adventure", "E", 0, 0, 0, None, ""),
                ("hidden.zip", "Hidden Game", "Platform", "E", 0, 1, 0, None, ""),
                ("mario.zip", "Super Mario Bros", "Platform", "E", 0, 0, 1, "2024-02-01", ""),
            ],
        )
        mgr = RomManager(tmp, FakeCfg())
        mgr.load_roms()
        assert mgr.roms == {}

        total, favs, ignored = mgr.counts()
        assert total == 4
        assert favs == 1
        assert ignored == 1

        genres = mgr.get_genre_list()
        assert genres[0] == "All Games"
        assert "Favorites" in genres
        assert "Most Played" in genres
        assert "Recently Played" in genres
        assert "Platform" in genres
        assert "Ignore" in genres

        all_games = mgr.get_roms_by_genre("All Games")
        assert [r.name for r in all_games] == ["mario.zip", "smw.zip", "zelda.zip"]

        fav_list = mgr.get_roms_by_genre("Favorites")
        assert [r.name for r in fav_list] == ["smw.zip"]

        hits = mgr.get_roms_by_genre("All Games", "mario")
        assert [r.name for r in hits] == ["mario.zip", "smw.zip"]

        platform = mgr.get_roms_by_genre("Platform")
        assert [r.name for r in platform] == ["mario.zip", "smw.zip"]

        assert mgr.toggle_favorite("zelda.zip") is True
        favs2 = mgr.get_roms_by_genre("Favorites")
        assert {r.name for r in favs2} == {"smw.zip", "zelda.zip"}

        row = mgr.record_play("zelda.zip")
        assert row[0] == 1

        fav, ign, plays = read_user_backup(tmp)
        assert "zelda.zip" in fav
        assert "smw.zip" in fav
        assert "hidden.zip" in ign
        assert plays["zelda.zip"][0] == 1
        assert plays["smw.zip"][0] == 3


def test_backup_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        write_user_backup(
            tmp,
            ["a.zip"],
            ["b.zip"],
            [("a.zip", 4, "2024-03-01")],
        )
        fav, ign, plays = read_user_backup(tmp)
        assert fav == {"a.zip"}
        assert ign == {"b.zip"}
        assert plays["a.zip"] == (4, "2024-03-01")


if __name__ == "__main__":
    test_playlists_search_and_backup()
    test_backup_roundtrip()
    print("All roms SQL tests passed.")
