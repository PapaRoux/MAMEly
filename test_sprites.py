#!/usr/bin/env python3
"""Unit tests for sprite skin-key parsing and path resolution."""
import os
import tempfile

from config import parse_sprite_defs, resolve_sprite_path, is_none_token, is_off_token, is_procedural_show, is_procedural_decor_show, SkinConfig


def test_is_none_token():
    assert is_none_token(None)
    assert is_none_token("")
    assert is_none_token("none")
    assert is_none_token("NONE")
    assert is_none_token("none.skin")
    assert not is_none_token("retrocade.skin")
    assert not is_none_token("background.png")
    assert not is_none_token("off")
    assert is_off_token("off")
    assert is_off_token("BLANK")
    assert not is_off_token("none")
    assert not is_off_token(None)


def test_parse_sprite_defs():
    cfg = {
        "sprite.ghosts.file": "retrocade_frame_ghosts.png",
        "sprite.ghosts.x": 1000,
        "sprite.ghosts.y": 40,
        "sprite.ghosts.show": True,
        "sprite.invader.file": "retrocade_frame_space_invader.png",
        "sprite.invader.x1": 1180,
        "sprite.invader.y1": 310,
        "sprite.invader.x2": 1240,
        "sprite.invader.y2": 370,
        "sprite.invader.show": "False",
        "romListDisplayAreaX1": 50,
    }
    sprites = parse_sprite_defs(cfg)
    assert len(sprites) == 2
    ghosts = sprites[0]
    assert ghosts["id"] == "ghosts"
    assert ghosts["file"] == "retrocade_frame_ghosts.png"
    assert ghosts["x"] == 1000
    assert ghosts["y"] == 40
    assert ghosts["show"] is True
    invader = sprites[1]
    assert invader["id"] == "invader"
    assert invader["w"] == 60
    assert invader["h"] == 60
    assert invader["show"] is False


def test_resolve_sprite_path():
    repo = os.path.dirname(os.path.abspath(__file__))
    platform = os.path.join(repo, "platforms", "MAME")
    found = resolve_sprite_path("retrocade_frame_ghosts.png", platform, repo)
    assert found and os.path.isfile(found)
    assert found.endswith(os.path.join("sprites", "retrocade_frame_ghosts.png"))
    assert resolve_sprite_path("does_not_exist.png", platform, repo) is None
    assert resolve_sprite_path("none", platform, repo) is None
    nes = os.path.join(repo, "platforms", "NES")
    shared = resolve_sprite_path("retrocade_frame_ghosts.png", nes, repo)
    assert shared and os.path.isfile(shared)
    assert shared.endswith(os.path.join("MAME", "sprites", "retrocade_frame_ghosts.png"))


def test_skin_config_loads_sprites():
    repo = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        skin_path = os.path.join(tmp, "test.skin")
        with open(skin_path, "w") as f:
            f.write("backgroundImage = none\n")
            f.write("sprite.mario.file = retrocade_frame_mario.png\n")
            f.write("sprite.mario.x = 200\n")
            f.write("sprite.mario.y = 80\n")
            f.write("sprite.mario.w = 64\n")
            f.write("sprite.mario.h = 64\n")
            f.write("sprite.mario.show = True\n")
        skin = SkinConfig(tmp, "test.skin")
        assert is_none_token(skin.get("backgroundImage"))
        assert len(skin.sprites) == 1
        spr = skin.sprites[0]
        assert spr["id"] == "mario"
        assert spr["file"] == "retrocade_frame_mario.png"
        assert spr["x"] == 200
        assert spr["w"] == 64
        assert spr["show"] is True
        # Resolve against the real MAME sprites folder
        found = resolve_sprite_path(spr["file"], os.path.join(repo, "platforms", "MAME"), repo)
        assert found and os.path.isfile(found)


def test_nav_keys_skin_keys():
    repo = os.path.dirname(os.path.abspath(__file__))
    mame = os.path.join(repo, "platforms", "MAME")
    skin = SkinConfig(mame, "config_retrocade_MAME_1920x1080.skin", 1920, 1080)
    assert skin.get("navKeysShow") is True
    assert skin.get("navKeysX1") == 1065
    assert skin.get("navKeysY1") == 740
    assert skin.get("navKeysX2") == 1340
    assert skin.get("navKeysY2") == 1045
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "hidden.skin")
        with open(path, "w") as f:
            f.write("backgroundImage = none\n")
            f.write("navKeysShow = False\n")
            f.write("navKeysX1 = 10\n")
            f.write("navKeysY1 = 20\n")
            f.write("navKeysX2 = 30\n")
            f.write("navKeysY2 = 40\n")
        hidden = SkinConfig(tmp, "hidden.skin")
        assert hidden.get("navKeysShow") is False
        assert hidden.get("navKeysX1") == 10
        none_skin = SkinConfig(tmp, "none", 1920, 1080)
        assert none_skin.get("navKeysShow") is True
        assert none_skin.get("navKeysX1") == 1075
        assert none_skin.get("proceduralShow") is True
        assert is_procedural_show(none_skin) is True
        assert none_skin.get("proceduralDecorShow") is True
        assert is_procedural_decor_show(none_skin) is True


def test_procedural_show_defaults():
    repo = os.path.dirname(os.path.abspath(__file__))
    mame = os.path.join(repo, "platforms", "MAME")
    png_skin = SkinConfig(mame, "config_retrocade_MAME_1920x1080.skin", 1920, 1080)
    assert is_procedural_show(png_skin) is False
    b_skin = SkinConfig(mame, "retrocade_MAME_1920x1080.skin", 1920, 1080)
    assert b_skin.get("proceduralShow") is True
    assert is_procedural_show(b_skin) is True
    assert b_skin.get("proceduralDecorShow") is False
    assert is_procedural_decor_show(b_skin) is False
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "overlay.skin")
        with open(path, "w") as f:
            f.write("backgroundImage = background.png\n")
            f.write("proceduralShow = True\n")
        overlay = SkinConfig(tmp, "overlay.skin")
        assert overlay.get("proceduralShow") is True
        assert is_procedural_show(overlay) is True
        none_path = os.path.join(tmp, "oldnone.skin")
        with open(none_path, "w") as f:
            f.write("backgroundImage = none\n")
        oldnone = SkinConfig(tmp, "oldnone.skin")
        assert oldnone.get("proceduralShow") is None
        assert is_procedural_show(oldnone) is True
        off_path = os.path.join(tmp, "off.skin")
        with open(off_path, "w") as f:
            f.write("backgroundImage = off\n")
        off_skin = SkinConfig(tmp, "off.skin")
        assert is_off_token(off_skin.get("backgroundImage"))
        assert is_procedural_show(off_skin) is False


def test_snes_skin_sprites():
    repo = os.path.dirname(os.path.abspath(__file__))
    snes = os.path.join(repo, "platforms", "SNES")
    skin = SkinConfig(snes, "config_retrocade_SNES_1920x1080.skin", 1920, 1080)
    assert len(skin.sprites) >= 10
    snes_logo = next((s for s in skin.sprites if s["id"] == "snes_logo"), None)
    assert snes_logo and snes_logo["file"] == "retrocade_frame_snes_logo.png"
    assert snes_logo["x"] == 1125 and snes_logo["y"] == 38
    assert snes_logo["w"] == 748 and snes_logo["h"] == 186


def test_atari2600_skin_sprites():
    repo = os.path.dirname(os.path.abspath(__file__))
    atari = os.path.join(repo, "platforms", "ATARI2600")
    skin = SkinConfig(atari, "config_retrocade_ATARI2600_1920x1080.skin", 1920, 1080)
    assert len(skin.sprites) >= 10
    atari_logo = next((s for s in skin.sprites if s["id"] == "atari_logo"), None)
    assert atari_logo and atari_logo["file"] == "retrocade_frame_atari_logo.png"
    assert atari_logo["x"] == 1085 and atari_logo["y"] == 46


def test_n64_skin_sprites():
    repo = os.path.dirname(os.path.abspath(__file__))
    n64 = os.path.join(repo, "platforms", "N64")
    skin = SkinConfig(n64, "config_retrocade_N64_1920x1080.skin", 1920, 1080)
    assert len(skin.sprites) >= 5
    n64_logo = next((s for s in skin.sprites if s["id"] == "n64"), None)
    assert n64_logo and n64_logo["file"] == "retrocade_frame_n64.png"
    assert n64_logo["x"] == 1538 and n64_logo["y"] == 31


if __name__ == "__main__":
    test_is_none_token()
    test_parse_sprite_defs()
    test_resolve_sprite_path()
    test_skin_config_loads_sprites()
    test_nav_keys_skin_keys()
    test_procedural_show_defaults()
    test_snes_skin_sprites()
    test_atari2600_skin_sprites()
    test_n64_skin_sprites()
    print("All sprite tests passed.")
