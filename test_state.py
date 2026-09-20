#!/usr/bin/env python3
"""Tests for mamely-state.db settings, last position, and play sessions."""
import os
import sqlite3
import tempfile

from config import Config
from state import MamelyState, STATE_FILENAME


class _Cfg:
    remember_emulator = False
    remember_game = True
    play_demo_video = False
    attract_mode = True


def test_settings_migrate_from_config_then_overlay():
    with tempfile.TemporaryDirectory() as tmp:
        state = MamelyState(tmp)
        cfg = _Cfg()
        state.pull_into_config(cfg)
        assert cfg.remember_emulator is False
        assert os.path.exists(os.path.join(tmp, STATE_FILENAME))

        state.set_setting("remember_emulator", True)
        cfg2 = _Cfg()
        MamelyState(tmp).pull_into_config(cfg2)
        assert cfg2.remember_emulator is True
        assert cfg2.remember_game is True
        assert cfg2.play_demo_video is False
        assert cfg2.attract_mode is True


def test_xml_settings_seed_state_on_first_run():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0"?>
<platforms>
    <screensize screenX="800" screenY="600"/>
    <settings rememberEmulator="false" rememberGame="false" playDemoVideo="true" attractMode="false"/>
</platforms>
""")
        cfg = Config(tmp, "config.xml")
        state = MamelyState(tmp)
        state.pull_into_config(cfg)
        assert cfg.remember_emulator is False
        assert cfg.attract_mode is False

        cfg.remember_emulator = True
        state.set_setting("remember_emulator", True)
        cfg3 = Config(tmp, "config.xml")
        MamelyState(tmp).pull_into_config(cfg3)
        assert cfg3.remember_emulator is True
        assert cfg3.attract_mode is False


def test_last_position_and_play_session():
    with tempfile.TemporaryDirectory() as tmp:
        state = MamelyState(tmp)
        state.save_position("Super Nintendo", "Favorites", "smw.zip")
        genre, rom = state.get_position("Super Nintendo")
        assert genre == "Favorites"
        assert rom == "smw.zip"
        assert state.get_last_platform() == "Super Nintendo"
        assert state.get_position("MAME") == ("", "")

        sid = state.start_play("Super Nintendo", "smw.zip")
        assert sid
        state.end_play(sid, 0, 12.5)
        with sqlite3.connect(os.path.join(tmp, STATE_FILENAME)) as conn:
            row = conn.execute(
                "SELECT platform, rom, duration_sec, exit_code FROM play_sessions WHERE id = ?",
                (sid,),
            ).fetchone()
        assert row == ("Super Nintendo", "smw.zip", 12.5, 0)


if __name__ == "__main__":
    test_settings_migrate_from_config_then_overlay()
    test_xml_settings_seed_state_on_first_run()
    test_last_position_and_play_session()
    print("All state tests passed.")
