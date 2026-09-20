#!/usr/bin/env python3
"""Tests for Settings OSD config defaults, parsing, and round-trip."""
import os
import tempfile

from config import Config, _as_bool


def test_as_bool_defaults_on():
    assert _as_bool(None) is True
    assert _as_bool("true") is True
    assert _as_bool("FALSE") is False
    assert _as_bool("off") is False
    assert _as_bool("nope", default=True) is True


def _write_cfg(path, body):
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def test_settings_default_on_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.xml")
        _write_cfg(path, """<?xml version="1.0"?>
<platforms>
    <screensize screenX="1920" screenY="1080"/>
    <platform name="MAME">
        <folder>MAME</folder>
        <config>platform_MAME.txt</config>
        <skin>none</skin>
    </platform>
</platforms>
""")
        cfg = Config(tmp, "config.xml")
        assert cfg.remember_emulator is True
        assert cfg.remember_game is True
        assert cfg.play_demo_video is True
        assert cfg.attract_mode is True
        assert cfg.session_platform == ""


def test_settings_and_session_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "config.xml")
        _write_cfg(path, """<?xml version="1.0"?>
<platforms>
    <screensize screenX="800" screenY="600"/>
    <settings rememberEmulator="false" rememberGame="true" playDemoVideo="false" attractMode="true"/>
    <session platform="Super Nintendo" rom="smw.zip" genre="Favorites"/>
    <platform name="Super Nintendo">
        <folder>SNES</folder>
        <config>platform_SNES.txt</config>
        <skin>none</skin>
    </platform>
</platforms>
""")
        cfg = Config(tmp, "config.xml")
        assert cfg.remember_emulator is False
        assert cfg.remember_game is True
        assert cfg.play_demo_video is False
        assert cfg.attract_mode is True
        assert cfg.session_platform == "Super Nintendo"
        assert cfg.session_rom == "smw.zip"
        assert cfg.session_genre == "Favorites"

        cfg.remember_emulator = True
        cfg.play_demo_video = True
        cfg.attract_mode = False
        cfg.session_rom = "zelda.zip"
        cfg.save_main_config()

        cfg2 = Config(tmp, "config.xml")
        assert cfg2.remember_emulator is True
        assert cfg2.remember_game is True
        assert cfg2.play_demo_video is True
        assert cfg2.attract_mode is False
        assert cfg2.session_rom == "zelda.zip"
        assert cfg2.session_platform == "Super Nintendo"
        assert cfg2.screen_width == 800
        assert len(cfg2.platforms) == 1
        assert cfg2.platforms[0].folder == "SNES"


if __name__ == "__main__":
    test_as_bool_defaults_on()
    test_settings_default_on_when_missing()
    test_settings_and_session_roundtrip()
    print("All settings tests passed.")
