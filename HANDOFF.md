# MAMEly — Agent Handoff Notes

**Project**: MAMEly — Python/Pygame arcade cabinet frontend (MAME, SNES, NES, N64, Atari2600, C64, Sega Master System)  
**Repo**: `/home/laptop/MAMEly` · GitHub `PapaRoux/MAMEly`  
**Last updated**: 2026-09-19  
**Git**: `main` with **uncommitted local work** (`proceduralShow` overlay on any background, sprite-only `-b` skins). Latest origin: `b7b888f` extracted retrocade sprites

Use this document to resume work without prior chat context.

---

## Project Overview

Fullscreen Pygame 2 frontend for arcade cabinets. Loads per-platform `MAMEly.db` (SQLite), shows a scrollable ROM list with snaps/video, launches emulators via configurable command lines.

### Key Files

| File | Purpose |
|------|---------|
| `MAMEly.py` | Entry point (`--config=`, `--wizard`, `--check`, `--config-map`) |
| `main.py` | `MAMElyApp` — input, draw loop, attract mode, randomizer, skin switcher modal, launch |
| `config.py` | Config load/save; expands `~` paths (portable); default fallback retrocade layouts |
| `input.py` | `InputManager` — keyboard + joystick actions |
| `ui.py` | Drawing, video snaps, search bar, slot-machine overlay, **in-engine procedural Retrocade generator** |
| `roms.py` | SQLite database engine (`MAMEly.db`), playlists, favorites, ignores, play stats |
| `wizard.py` | Graphical setup wizard (F2 / `--wizard`) with database generation |
| `diagnostics.py` | `--check` + F1 OSD |
| `platforms/*/` | Per-platform `.txt`, `.skin`, `MAMEly.db`, `sprites/`, generator scripts |
| `skin_editor.html` | Standalone browser-based visual skin editor |

### Machines / Paths

- **Dev**: `/home/laptop/MAMEly`
- **Cabinet**: `/home/mame/MAMEly`
- Configs use `~` paths only — **never** hardcode `/home/laptop/` or `/home/mame/`
- Launch: `python3 MAMEly.py --config=config.xml`

### Runtime Dependencies (System)

- Python 3.13.5, Pygame 2.6.1, OpenCV (`cv2`)
- `ffplay` at `/usr/bin/ffplay` (audio for attract mode)
- Flatpaks installed & configured:
  - `com.snes9x.Snes9x` (Super Nintendo)
  - `net.sf.VICE` (Commodore 64 — `x64sc`)
  - `org.libretro.RetroArch` / Stella (Atari 2600)

---

## Configured Platforms & Emulators (Verified Working)

| Platform | Emulator Launch Config | Exit Behavior | Notes |
|---|---|---|---|
| **MAME** | Native `mame` binary | `ESC` | Direct ROM launch from `~/.mame/roms/` |
| **NES** | Native `mame nes -cart` or Flatpak | `ESC` | Fullscreen, mapped buttons |
| **SNES** | Flatpak `com.snes9x.Snes9x` | `ESC` | Custom fullscreen override config loaded; Esc returns cleanly to MAMEly |
| **SEGAMASTER** | Native `mame sms -cart` | `ESC` | MAME Sega Master System driver |
| **C64** | Flatpak `net.sf.VICE` (`x64sc`) | `Alt+ESC` | Runs fullscreen; uses `Alt+ESC` as hotkey exit so in-game Commodore `ESC` key is preserved |
| **ATARI2600** | Stella Flatpak | `ESC` | Fullscreen mode, Esc returns to frontend |

---

## Features In Place

### 1. Procedural chrome overlay (`proceduralShow`) & `"none"` CRT fill
- **`backgroundImage`**: PNG file, or `"none"` / missing file → dark CRT fill + scanlines (`generate_procedural_retrocade()`). Independent of frames.
- **`proceduralShow`**: neon frames only (list/snap/info boxes).
- **`proceduralDecorShow`**: platform title, pixel ghosts/invader, and the nav-keys card. Independent of frames. Editor toggle **Header & nav art**.
- Missing `proceduralShow`: PNG skins stay off (painted art unchanged); `backgroundImage = none` stays on (classic full procedural). The `"none"` platform fallback sets it True in `DEFAULT_RETROCADE_*`.
- **Nav card**: drawn when `navKeysShow` and `proceduralShow` (unless nav sprites `up` / `scroll_up` / `mamely` / `pasted_layer` are visible). Hidden: black cover rect, those sprites skipped.
- **Sprite-only `-b` skins**: `backgroundImage = none` and `proceduralShow = False` so extracted sprites sit on CRT fill without doubled neon boxes.

### 2. Extracted Retrocade Sprites (`platforms/MAME/sprites/`)
- All 20 layers from `background_retrocade_MAME_1920x1080.xcf` were extracted with full alpha transparency and tightly cropped:
  - `retrocade_frame_game_list.png`
  - `retrocade_frame_game_set.png`
  - `retrocade_frame_rom_name.png`
  - `retrocade_frame_snap_frame.png`
  - `retrocade_frame_space_invader.png`
  - `retrocade_frame_comets.png`
  - `retrocade_frame_galaga.png`
  - `retrocade_frame_shoot_fireball.png` / `shoot_fireball_1.png`
  - `retrocade_frame_ms_pacman.png` / `pacman.png`
  - `retrocade_frame_mamely.png`
  - `retrocade_frame_up.png` / `scroll_up.png`
  - `retrocade_frame_turtle_shell.png`
  - `retrocade_frame_mario.png`
  - `retrocade_frame_ghosts.png`
  - `retrocade_frame_mame.png`

### 3. Sprite overlays (skin-configured)
`.skin` files can place PNGs from `platforms/<PLATFORM>/sprites/` (fallback: repo `sprites/`):

```
sprite.ghosts.file = retrocade_frame_ghosts.png
sprite.ghosts.x = 1000
sprite.ghosts.y = 40
sprite.ghosts.w = 240
sprite.ghosts.h = 80
sprite.ghosts.show = True
```

- Parsed in `config.parse_sprite_defs` / `SkinConfig.sprites`
- Rendered in `UIManager.begin_frame()` after the background (`load_sprites` / `draw_sprites`)
- `w`/`h` optional (native size if omitted); `x2`/`y2` also accepted
- Skin editor: **Sprites** panel, **+ Add**, drag/resize overlay boxes, **drag list to reorder layers** (top = front); export writes `sprite.<id>.*` keys
- **MAME retrocade 1920×1080** (`config_retrocade_MAME_1920x1080.skin`) has 18 sprites positioned by template-matching the cropped XCF layers against `background_retrocade_MAME_1920x1080.png`. Omitted: 1×1 `background` layer, `turtle_shell` (not in the flattened PNG).
- **Sprite-only variant** (`config_retrocade_*_1920x1080-b.skin`): same sprite layout with `backgroundImage = none` and `proceduralShow = False`. Missing platform sprites fall back to `platforms/MAME/sprites/`.

### 4. Search (`/`)
Realtime filter; Esc clears; Enter locks. `ACTION_SEARCH`, `ui.draw_search_bar`.

### 5. Lucky Dip Randomizer (Slot Machine)
Triggered by keyboard `1` / `5` or stick buttons `1, 5, 9`. Timed ~3.6s ease-out reel over filtered list, landing with winner flash and automatic launch.

### 6. Attract Mode
Fullscreen in-engine video playback via OpenCV + headless audio via `ffplay -nodisp -autoexit -loglevel quiet`. Wakes up on any button press.

---

## Skin Editor (`skin_editor.html`)

A standalone browser-based visual layout editor for `.skin` files.
- Open via browser or local server: `python3 -m http.server 8765` → `http://localhost:8765/skin_editor.html`
- **Procedural frames** (`proceduralShow`): neon boxes only.
- **Header & nav art** (`proceduralDecorShow`): platform title, pixel ghosts/invader, and the nav-keys card.
- **`[none]`**: `backgroundImage = none` — CRT fill, sprites stay.
- **No image**: `backgroundImage = off` — no PNG and no CRT (checkerboard in the editor, flat black in MAMEly). Sprites stay; transparent holes show the empty backdrop.
- **Sprites** panel: add / drag / resize PNG overlays; drag the list to reorder layers (top = front); export writes `sprite.<id>.*` keys.
- Workflow for a sprite-only skin: **Load .skin** → **No image** (empty) or **[none]** (CRT) → leave Procedural frames **off** → **Export**.
- Workflow for PNG + procedural frames: **Load BG** → turn **Procedural frames** **on** → **Export** (`proceduralShow = True`).
- **Nav Keys** zone: drag/resize the help-card rect; Show toggle writes `navKeysShow` and redraws/covers the card.
- Interactive 8-handle drag & resize for UI regions (including Nav Keys).
- Left/center/right text alignment controls (`romListDisplayAlign`, `genreSetAlign`, etc.).
- Undo/Redo (`Ctrl+Z` / `Ctrl+Y`), Arrow-key nudge (`1px` / `Shift+Arrow 10px`), Snap-to-grid (`G`), Text Preview mode (`P`).

---

## Next Steps to Implement

### 1. Portrait zone defaults when switching `[none]` + 1080×1920
- Editor zone boxes currently keep landscape coordinates when the canvas is switched to portrait; apply `DEFAULT_RETROCADE_1080x1920` (or a confirm dialog) so text regions line up with the procedural portrait boxes.

---

## Quick Test Plan

```bash
cd /home/laptop/MAMEly
python3 test_sprites.py
python3 MAMEly.py --check
python3 MAMEly.py --config=config.xml
# In app: S / F4 → select 'none'
# Skin editor:
python3 -m http.server 8765
# open http://localhost:8765/skin_editor.html
# Load config_retrocade_MAME_1920x1080.skin, then Remove BG / [none]
# or load config_retrocade_MAME_1920x1080-b.skin (already none + sprites)
```

---

## Resume Prompt (for next agent)

> Read `HANDOFF.md`. All platforms are configured and working. `proceduralShow` overlays neon frames on PNG or CRT fill (`[none]`). Sprite-only `-b` skins use `backgroundImage = none` and `proceduralShow = False`. Work is **uncommitted**. Optional next: portrait zone defaults when the editor switches to 1080×1920.
