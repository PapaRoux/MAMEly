# MAMEly — Agent Handoff Notes

**Project**: MAMEly — Python/Pygame arcade cabinet frontend (MAME, SNES, N64, Atari2600, …)  
**Repo**: `/home/laptop/MAMEly` · GitHub `PapaRoux/MAMEly`  
**Last updated**: 2026-07-26  
**Git**: `main` clean and synced with `origin/main` (latest: `d76e841` randomizer)

Use this document to resume work without prior chat context.

---

## Project Overview

Fullscreen Pygame 2 frontend for arcade cabinets. Loads per-platform `MAMEly.xml`, shows a scrollable ROM list with snaps/video, launches emulators via configurable command lines.

### Key Files

| File | Purpose |
|------|---------|
| `MAMEly.py` | Entry point (`--config=`, `--wizard`, `--check`) |
| `main.py` | `MAMElyApp` — input, draw loop, attract mode, randomizer, launch |
| `config.py` | Config load/save; expands `~` paths (portable across machines) |
| `input.py` | `InputManager` — keyboard + joystick actions |
| `ui.py` | Drawing, video snaps, search bar, **slot-machine overlay** |
| `roms.py` | XML / favorites / ignore / skip lists |
| `wizard.py` | Graphical setup wizard (F2 / `--wizard`) |
| `diagnostics.py` | `--check` + F1 OSD |
| `platforms/*/` | Per-platform `.txt`, `.skin`, `MAMEly.xml` |
| `skin_editor.html` | **NEW** — standalone browser-based visual skin editor |

### Machines / paths

- **Dev**: `/home/laptop/MAMEly`
- **Cabinet**: `/home/mame/MAMEly`
- Configs use `~` paths only — **never** hardcode `/home/laptop/` or `/home/mame/`
- Launch: `python3 MAMEly.py --config=config.xml`

### Runtime deps (this laptop)

- Python 3.13.5, Pygame 2.6.1, OpenCV (`cv2`)
- `ffplay` at `/usr/bin/ffplay` (audio for attract)
- User is **not** in the `input` group → raw `/dev/input/event*` is permission-denied (relevant if someone retries that approach)

---

## Features Already In Place

### Search (`/`)
Realtime filter; Esc clears; Enter locks. `ACTION_SEARCH`, `ui.draw_search_bar`.

### Favorite / Ignore confirmations
`F` / `I` (and mapped buttons) open a confirm modal before toggling.

### Video snaps
- Path: `romVideoDirectory` + `videoExtension` (default under `~/.mame/video/`)
- OpenCV decode → BGR→RGB → `transpose` → `pygame.surfarray.make_surface`
- Space pauses preview (`ACTION_PAUSE`)

### Idle / attract timing (`main.py` `draw()`)

| Idle | Behavior |
|------|----------|
| < 5s | Static PNG snap |
| 5–65s | Looping video in snap box |
| ≥ 65s | `run_attract_mode(video_path)` |

On return from attract: `last_interaction_time = time.time() - 5.0` so the inline video resumes immediately.

### Attract mode (rewritten — important)

**Do not** use `ffplay -fs`. Fullscreen ffplay steals focus; Pygame never sees keys/joystick.

**Current design** (`run_attract_mode` in `main.py`):

1. Blit video frames fullscreen with OpenCV inside the **existing Pygame window**
2. Audio via headless `ffplay -nodisp -autoexit -loglevel quiet`
3. Interrupt on any `KEYDOWN`, `JOYBUTTONDOWN`, or `MOUSEBUTTONDOWN`
4. Esc/q no longer required

A/V sync is approximate (separate video + audio processes). Acceptable for attract.

### Lucky Dip randomizer (slot machine)

**Triggers** (`input.py`, edge-triggered):

| Input | Notes |
|-------|--------|
| Joystick buttons **1, 5, 9** (either stick) | `JOYBUTTONDOWN` |
| Keyboard **1** or **5** | Classic cabinet start / coin |

**Behavior** (`run_randomizer` + `ui.draw_slot_machine`):

- Fullscreen "LUCKY DIP" overlay (chrome frame, lights, payline, motion-blur ghosts)
- **Timed** ~3.6s ease-out reel (fixed ~42–64 row scroll) — **not** one step per ROM
- Lands on random ROM in the **current filtered list**, ~1.25s "WINNER!" flash, then `run_rom()`
- Esc cancels **during spin only** (after land, launch proceeds)

**Why the first version failed**: stepping once per ROM on a large MAME list never finished, so it never launched. Do not regress to `spins * len(rom_list)` step loops.

**Side effect**: joystick button **1** no longer cycles genre (was Genre). Genre remains on **Tab**. Button 0 = Run, 2 = Platform, 3 = Favorite.

---

## Skin Editor (`skin_editor.html`)

**New this session.** A standalone browser-based visual editor for `.skin` files. No server needed — open with `xdg-open skin_editor.html` or double-click.

### What it does (MVP — working)

- Load any existing `.skin` file via file picker → all zones + colors + toggles populated
- Load a background PNG → displayed behind the zone overlays
- 6 coloured zone overlays on the canvas, each representing a UI region:
  - 🔵 ROM List · 🟢 Genre/Message · 🟡 File Name Box · 🟣 Genre Set Bar · 🔴 ROM Snap · 🟡 ROM Count
- **Drag to move** any zone
- **8-handle resize** (corners + edges) on selected zone
- Left panel: zone visibility toggles, shadow/stroke toggles, 17 color pickers
- Right panel: X1/Y1/X2/Y2 coordinate inputs, W/H derived display, font/size/truncate props per zone
- Resolution switcher (1920×1080, 1080×1920, or custom)
- **Export** → downloads a valid `.skin` file with correct format and comments
- Status bar: live cursor coordinates in skin-space, scale factor

### Round 2 features — ALL IMPLEMENTED AND VERIFIED IN BROWSER

Undo/redo, arrow-key nudge, snap-to-grid, and text preview mode are **done**. Text
alignment (below) was added on top. Descriptions kept as as-built reference.

#### 1. Undo / Redo (Ctrl+Z / Ctrl+Y)
- Maintain `HIST` array of `JSON.parse(JSON.stringify(S.skin))` snapshots
- `HIST_IDX` pointer, max 60 entries
- `commitHistory()` called AFTER each meaningful change (drag end, coord input blur, toggle, color change)
- `undo()` decrements index and calls `fullRebuild()`; `redo()` increments
- Clear `HIST` on skin load or New (start fresh baseline)
- Header buttons: `↩ Undo` and `↪ Redo`, disabled when at stack bounds
- Keyboard: Ctrl+Z = undo, Ctrl+Y or Ctrl+Shift+Z = redo

#### 2. Arrow key nudge
- `keydown` handler on `document`; skip if `activeElement` is INPUT/TEXTAREA
- Arrow keys: move selected zone 1px; Shift+Arrow: 10px
- Calls `nudgeZone(zid, dx, dy)` → clamps, updates skin, `renderCanvas()`, `patchCoordInputs()`
- Debounced `commitHistory()` 300ms after last nudge (so holding arrow doesn't flood history)

#### 3. Snap to grid
- State: `S.snap = false`, `S.snapGrid = 10`
- `snapV(v)` → `Math.round(v / S.snapGrid) * S.snapGrid` (no-op when snap off)
- Applied in `onDocMove()` to final coordinates before writing to `S.skin`
- Visual: CSS grid pattern on `#zones-layer` via `backgroundImage` linear-gradients, updated by `updateGridOverlay()`
- UI: `⊞ Snap` toggle button (`.active` class when on) + small number input for grid size
- Keyboard shortcut: `G` to toggle
- Also apply snap in `nudgeZone()`

#### 4. Text preview mode
- State: `S.preview = false`
- Toggle button `🔤` in header (`.active` class when on); keyboard `P`
- `PREVIEW` constant maps zone id → `{ type, text/items, sizeKey, spacingKey, truncKey, colorKey }`
  - `romListDisplayArea` → type `'list'`, 15 fake game names, highlight index 3
  - all others → type `'center'` with sample text, or `'snap'` for ROM Snap zone
- `addPreviewContent(div, z)` called from `renderCanvas()` when `S.preview` is true
  - Hides the `.zo-lbl` label
  - Renders text at `S.skin[sizeKey] * S.scale` px, font-family monospace (actual TTF not loadable from file://)
  - List type: renders lines spaced by `romListDisplaySpacing * S.scale` px
  - Colors pulled from S.skin color keys (converted: `'#' + S.skin[colorKey]`)
  - Truncation: slice text to `S.skin[truncKey]` chars + '…'

Deviation from the plan: the ROM list preview does **not** render a fixed 15 lines.
It computes `ceil(zoneHeight / spacing) + 1` lines so the list always fills the zone
regardless of font size / spacing — the user specifically asked to be able to see
where the list starts and stops at small font sizes.

#### Other keyboard shortcuts (implemented)
- `Ctrl+S` → export (works even from input focus)
- `Esc` → deselect zone
- `G` → toggle snap
- `P` → toggle preview

#### 5. Text alignment (per text zone) — IMPLEMENTED

Every text zone gained a left/center/right alignment key. Previously all text was
hard-centered on the zone's derived `XCenter`.

New skin keys (all default to `center`, all optional — missing/garbage reads as center):

| Key | Zone |
|---|---|
| `romListDisplayAlign` | ROM list rows |
| `genreSetAlign` | Genre set bar |
| `romGenreAlign` | Genre + Rating lines |
| `messageAlign` | Transient message (shares the romGenre zone) |
| `romFileNameDisplayBoxAlign` | ROM filename box |
| `romCountAlign` | "N of M" counter |

**App side.** `ui.draw_text()` takes a new `align=None` kwarg. With `centered=True`
(the default), `y` stays the vertical middle and `align` picks the horizontal anchor:
`left` → `rect.midleft`, `right` → `rect.midright`, `center`/`None` → `rect.center`.
Passing no `align` is byte-identical to the old behaviour, so the ~20 other
`draw_text` callers (wizard, modals, OSD) were untouched. The `centered=False`
top-left path is unchanged.

`main.py` has a helper `_text_anchor(prefix, align_key)` returning `(x, align)`:
`left` anchors on the zone's `X1`, `right` on `X2`, `center` on the derived
`XCenter`. Call sites resolve their anchor once, then pass both through.

No `config.py` change was needed — align values fall through to the plain-string
branch (they contain none of the `X1/Y1/X2/Y2/Size/Len/Offset/Time/Spacing`
substrings that force int coercion, and no `Color`).

**Editor side.** New prop `type:'align'` renders a 3-button segmented control
(⇤ ↔ ⇥) instead of a text input; `readAlign(key)` normalizes whatever is in the
skin. Alignment changes commit to undo history and re-render the preview live.

Preview fidelity note: preview text is anchored flush to the zone edges
(`left:0; right:0`, no padding) so it matches the app, which anchors exactly on
`X1`/`X2` with no inset. If you ever add padding in the app, mirror it here.

Verified headless with `SDL_VIDEODRIVER=dummy` (mask bounding box of rendered text):
left edge lands on `X1`, midpoint on `XCenter`, right edge on `X2`, vertical center
preserved in all three cases, and `align=None` matches `align='center'` exactly.

### .skin file format (reference)

Plain `key = value` text file. Parsed by `SkinConfig` in `config.py`.

- **Colors**: plain 6-char hex e.g. `FFFFFF` (no `#` or `0x` prefix in output)
- **Booleans**: `True` / `False`
- **Integers**: plain decimal
- **Strings**: plain text (font filenames)
- Comments: lines starting with `#` (stripped on re-export — that's intentional per the format)

Skin files live in `platforms/<PLATFORM>/` alongside the background PNG and font TTF.

---

## Known Caveats / Watchouts

1. **Genre on stick**: button 1 → randomizer. Remap if cabinet layout needs Genre on a face button.
2. **Attract A/V drift**: OpenCV video + separate ffplay audio can drift on long clips.
3. **Randomizer has no sound**: visual-only ticks; mixer is available if you want coin/reel SFX.
4. **`__pycache__` in git history**: recent commits included `.pyc` files — prefer not adding more.
5. **skin_editor.html still not committed to git** — it is complete and working; commit it.
6. **Alignment is horizontal only.** Vertical placement still comes from the zone's
   `YCenter` (or `romListDisplaySpacing` for the list). No top/middle/bottom option.

---

## Suggested Next Work

### Skin editor
Feature-complete for now (undo/redo, nudge, snap, preview, alignment). Possible polish:
per-zone vertical alignment, live TTF loading so preview uses the real font instead of
a monospace stand-in, and a padding/inset property to go with left/right alignment.

### MAMEly app
1. **Randomizer SFX** — coin drop + reel tick + win sting via `pygame.mixer`
2. **Restore Genre on a stick button** — e.g. button 4 or 6, if hardware has it
3. **Play history / "Recently Played"** genre
4. **CRT scanline overlay** (F3 toggle)
5. **Controller mapper** in the setup wizard
6. Attract polish — slightly tighter A/V sync, or fade back to UI

---

## Quick Test Plan

```bash
cd /home/laptop/MAMEly
python3 MAMEly.py --config=config.xml
```

1. Idle 65s with a game that has a video snap → attract plays; press any key/button → returns to UI with video snap.
2. Press `1`, `5`, or stick button 1/5/9 → Lucky Dip overlay spins → lands → game launches.
3. Esc mid-spin → cancelled, no launch.
4. Tab still cycles genre.

5. Set `romListDisplayAlign = left` in the skin → list rows sit flush on the list zone's
   `X1`. Set `right` → flush on `X2`. Remove the key entirely → centered as before.

**Skin editor:**

`xdg-open` on a `file://` URL gets blocked by browser security for the file picker,
so serve it instead:

```bash
cd /home/laptop/MAMEly && python3 -m http.server 8765
# then open http://localhost:8765/skin_editor.html
# Load platforms/MAME/config_retrocade_MAME_1920x1080.skin
# Load platforms/MAME/background_retrocade_MAME_1920x1080.png
```

Press `P` for preview, then click a text zone and use the ⇤ ↔ ⇥ control to confirm
text moves within the zone. Ctrl+Z should revert it.

---

## Resume Prompt (for next agent)

> Read `HANDOFF.md`. The skin editor (`skin_editor.html`) is feature-complete: undo/redo, arrow nudge, snap-to-grid, text preview, and per-zone text alignment all work and were verified in a browser. It is still untracked in git. Do not reintroduce `ffplay -fs` for attract mode. Do not make the randomizer step once per ROM. When adding new text zones, give them an `...Align` key and route them through `main.py::_text_anchor` + `ui.draw_text(align=...)` rather than hard-centering on `XCenter`.
