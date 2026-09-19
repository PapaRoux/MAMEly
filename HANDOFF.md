# MAMEly — Agent Handoff Notes

**Project**: MAMEly — Python/Pygame arcade cabinet frontend (MAME, SNES, NES, N64, Atari2600, C64, Sega Master System)  
**Repo**: `/home/laptop/MAMEly` · GitHub `PapaRoux/MAMEly`  
**Last updated**: 2026-09-19  
**Git**: `main` clean and synced with `origin/main` (latest: `b7b888f` extracted retrocade sprites)

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

### 1. Procedural In-Engine Retrocade Skin & `"none"` Fallback
- When a platform's skin is set to `"none"`, `""`, or if a background image file is missing, `UIManager.generate_procedural_retrocade()` (`ui.py`) dynamically renders a pixel-perfect Retrocade skin:
  - **Exact Bounding Boxes**: Automatically positions Favorites/Genre bar, ROM List, Rating/Info bar, ROM Count, Snapshot/Video, and ROM Filename boxes for both **1920×1080 Landscape** and **1080×1920 Portrait**.
  - **Neon Glow Framing**: Rounded crimson-red glow borders (`#F52044`), soft diffusion glow, and dark panel backing.
  - **In-Game Navigation Keys Card**: Built-in 2-column reference card with `MAMEly` yellow header displaying all keybindings (`UP/DN`, `LEFT/RIGHT`, `ENTER/B1`, `TAB/B2`, `E/B3`, `F/B4`, `S/F4`, `D/F1`, `ESC/B9+B10`).
  - **3D Marquee Title & Sprites**: Layered platform title header with arcade drop-shadows and retro 8-bit sprites (Space Invader, Pac-Man ghosts).
  - **Scanlines**: Subtle CRT raster scanlines.
- **In-App Skin Switcher (`S` / `F4`)**:
  - Lists `"none"` at the top as `[none] Procedural Retrocade (Fallback)`.
  - Supports live previewing and switching between `.skin` files and the procedural fallback.

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

### 3. Search (`/`)
Realtime filter; Esc clears; Enter locks. `ACTION_SEARCH`, `ui.draw_search_bar`.

### 4. Lucky Dip Randomizer (Slot Machine)
Triggered by keyboard `1` / `5` or stick buttons `1, 5, 9`. Timed ~3.6s ease-out reel over filtered list, landing with winner flash and automatic launch.

### 5. Attract Mode
Fullscreen in-engine video playback via OpenCV + headless audio via `ffplay -nodisp -autoexit -loglevel quiet`. Wakes up on any button press.

---

## Skin Editor (`skin_editor.html`)

A standalone browser-based visual layout editor for `.skin` files.
- Open via browser or local server: `python3 -m http.server 8765` → `http://localhost:8765/skin_editor.html`
- Interactive 8-handle drag & resize for all 6 UI regions.
- Left/center/right text alignment controls (`romListDisplayAlign`, `genreSetAlign`, etc.).
- Undo/Redo (`Ctrl+Z` / `Ctrl+Y`), Arrow-key nudge (`1px` / `Shift+Arrow 10px`), Snap-to-grid (`G`), Text Preview mode (`P`).

---

## Next Steps to Implement

### 1. Add Background Graphic `"none"` in Skin Editor (`skin_editor.html`)
- **Goal**: Allow users in `skin_editor.html` to choose `"none"` as the background image.
- **In-Editor Drawing for `"none"`**:
  - When background is set to `"none"` (or procedural toggle active), draw the procedural in-game Retrocade skin directly on the HTML canvas context.
  - Draw the neon red bounding boxes, dark panel backings, MAMEly navigation keys card, 3D marquee title banner, and CRT scanlines in JavaScript matching the Python `ui.py` dimensions.
  - This allows skin designers to visually position text elements and boxes against the procedural background without needing an external image file.

### 2. Add Sprite Loading & Rendering from `sprites/` Subfolder
- **Goal**: Enable MAMEly frontend and skins to load and place custom sprites from `platforms/<PLATFORM>/sprites/` (or common `sprites/`).
- **Engine Support (`ui.py` / `main.py` / `config.py`)**:
  - Support sprite definitions in `.skin` files or skin config (e.g. `sprite.<id>.file = retrocade_frame_ghosts.png`, `sprite.<id>.x = 1000`, `sprite.<id>.y = 40`, `sprite.<id>.show = True`).
  - Render active platform sprites during `ui.begin_frame()` / background composition.
  - Support sprite caching and transparency scaling in `UIManager`.
- **Editor Support (`skin_editor.html`)**:
  - Allow adding / positioning sprite overlay boxes in the visual editor.

---

## Quick Test Plan

```bash
cd /home/laptop/MAMEly
# 1. Run diagnostic checks
python3 MAMEly.py --check

# 2. Run frontend with procedural fallback skin
python3 MAMEly.py --config=config.xml

# 3. Test skin switcher (Press S or F4 in app, select 'none')
# 4. Open Skin Editor in browser
python3 -m http.server 8765 &
xdg-open http://localhost:8765/skin_editor.html
```

---

## Resume Prompt (for next agent)

> Read `HANDOFF.md`. All platforms (MAME, NES, SNES, C64, Atari 2600, Sega Master System) are configured and working. Procedural Retrocade fallback skin is implemented in `ui.py` and `config.py` for `"none"` mode. 20 cropped sprite layers are in `platforms/MAME/sprites/`. The next tasks are:
> 1. In `skin_editor.html`, add a background graphic option for `"none"` that procedurally renders the in-game Retrocade layout (neon boxes, nav card, marquee title) onto the editor canvas.
> 2. Implement the sprite loader system in `config.py`, `ui.py`, and `main.py` to support placing and rendering sprites from the `sprites/` subfolder via skin config.
