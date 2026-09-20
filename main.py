import sys
import os

# Ensure GLX compatibility with Mesa fallback for systems with problematic NV-GLX drivers
os.environ["__GLX_VENDOR_LIBRARY_NAME"] = "mesa"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"

import time
import random
import shlex
import subprocess
import pygame
from config import Config, PlatformConfig, SkinConfig, is_none_token
from roms import RomManager
from ui import UIManager
from input import InputManager
from version import __version__
from diagnostics import build_osd_lines, check_platform, startup_message, check_all, has_errors
from mamely_log import setup_logging, get_logger

log = get_logger("main")

SETTINGS_ROWS = [
    {"section": "Startup"},
    {
        "key": "remember_emulator",
        "label": "Remember emulator",
        "hint": "On boot, return to the last platform",
    },
    {
        "key": "remember_game",
        "label": "Remember game",
        "hint": "On boot, return to the last selected game",
    },
    {"section": "Browser"},
    {
        "key": "play_demo_video",
        "label": "Play small demo video",
        "hint": "Play the preview clip after a few seconds idle",
    },
    {
        "key": "attract_mode",
        "label": "Attract mode",
        "hint": "Fullscreen attract video after a long idle",
    },
]
MOUSE_CURSOR_TIMEOUT = 2.0
SETTINGS_TOGGLE_KEYS = [row["key"] for row in SETTINGS_ROWS if row.get("key")]

class MAMElyApp:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(self.base_path)
        setup_logging(self.base_path)
        self._started_at = time.time()

        pygame.init()
        pygame.font.init()

        log.info("MAMEly v%s starting pid=%s", __version__, os.getpid())

        # Parse Args
        self.config_file = "config.xml"
        self.launch_wizard = False
        for i, arg in enumerate(sys.argv):
            if arg.startswith("--config="):
                self.config_file = arg.split("=", 1)[1]
            elif arg == "--config" and i + 1 < len(sys.argv):
                self.config_file = sys.argv[i + 1]
            elif arg == "--wizard":
                self.launch_wizard = True

        log.info("config file=%s wizard=%s", self.config_file, self.launch_wizard)

        # Load Main Config
        self.config = Config(self.base_path, self.config_file)
        
        # State
        self.running = True
        self.platform_idx = 0
        self.current_platform = None
        self.skin = None
        self.rom_manager = None
        self.ui = None
        self.input = InputManager()
        
        # View State
        self.genre_list = []
        self.current_genre_idx = 0
        self.rom_list = []
        self.selected_rom_idx = 0
        
        # Messages
        self.message = ""
        self.message_start_time = 0
        self.message_duration = 2 # default
        self._current_message_duration = 2
        
        # Confirmation Logic
        self.confirm_action = None
        self.confirm_message = ""

        # F1 config / help OSD
        self.show_info_osd = False
        self.info_osd_lines = []
        self.info_osd_scroll = 0
        self.platform_issues = []

        # Search states
        self.search_active = False
        self.search_query = ""

        # Video snaps controls
        self.last_interaction_time = time.time()
        self.video_paused = False
        self.randomizing = False

        # Skin Switcher state
        self.skin_picker_active = False
        self.skin_picker_items = []
        self.skin_picker_idx = 0
        self.skin_picker_initial_skin = None

        # Settings OSD
        self.show_settings_osd = False
        self.settings_idx = 0
        self.settings_hit_rects = []
        self._mouse_cursor_visible = False

    def load_platform(self, restore_session=False):
        if not self.config.platforms:
            log.error("no platform definitions found")
            self.running = False
            return

        p_def = self.config.platforms[self.platform_idx]
        platform_path = os.path.join(self.base_path, "platforms", p_def.folder)

        log.info("platform load name=%s folder=%s skin=%s", p_def.name, p_def.folder, p_def.skin_file)
        
        # Load Configs
        p_conf = PlatformConfig(platform_path, p_def.config_file)
        self.skin = SkinConfig(platform_path, p_def.skin_file, self.config.screen_width, self.config.screen_height)
        self.message_duration = self.skin.get("messageTime", 2)
        
        # Initialize UI (re-init for potentially different background/res)
        # Note: In real scenarios we might want to keep the window open, 
        # but here we follow original flow closest regarding skin loading.
        if self.ui is None:
             self.ui = UIManager(self.config, self.skin, platform_name=p_def.name)
        else:
             self.ui.close_video()
             self.ui.skin = self.skin
             self.ui.load_background(platform_name=p_def.name)
             self.ui.load_sprites()

        # Load ROMs
        self.ui.begin_frame()
        self.ui.show_message("Reading database...", self.skin.get("defaultMessageColor"))
        self.ui.end_frame()
        
        self.rom_manager = RomManager(platform_path, p_conf)
        self.rom_manager.load_skips_and_flags()
        self.rom_manager.load_roms() # Synchronous for now, could add progress callback
        
        self.genre_list = self.rom_manager.get_genre_list()
        restored = False
        if restore_session:
            restored = self._restore_session_selection()
        if not restored:
            # Default to Favorites if available
            if "Favorites" in self.genre_list:
                try:
                    self.current_genre_idx = self.genre_list.index("Favorites")
                except ValueError:
                    self.current_genre_idx = 0
            else:
                self.current_genre_idx = 0
            self.update_view_lists()
        genre = self.genre_list[self.current_genre_idx] if self.genre_list else "-"
        favs = sum(1 for r in self.rom_manager.roms.values() if r.favorite)
        ignored = sum(1 for r in self.rom_manager.roms.values() if r.ignore)
        log.info(
            "platform ready name=%s roms=%d favorites=%d ignored=%d genre=%s listed=%d",
            p_def.name, len(self.rom_manager.roms), favs, ignored, genre, len(self.rom_list),
        )
        self._report_platform_diagnostics(p_def)

    def _current_platform_def(self):
        return self.config.platforms[self.platform_idx]

    def switch_skin(self, skin_filename, save=True):
        """Dynamically reload skin and background, and optionally persist to config.xml."""
        p_def = self._current_platform_def()
        platform_path = os.path.join(self.base_path, "platforms", p_def.folder)
        is_none = is_none_token(skin_filename)
        if not is_none:
            full_path = os.path.join(platform_path, skin_filename)
            if not os.path.exists(full_path):
                log.warning("skin file not found path=%s", full_path)
                return False

        p_def.skin_file = skin_filename
        self.skin = SkinConfig(platform_path, skin_filename, self.config.screen_width, self.config.screen_height)
        self.message_duration = self.skin.get("messageTime", 2)
        if self.ui:
            self.ui.close_video()
            self.ui.skin = self.skin
            self.ui.load_background(platform_name=p_def.name)
            self.ui.load_sprites()
        
        if save:
            self.config.save_main_config()
        log.info("skin switch file=%s save=%s", skin_filename, save)
        return True

    def open_skin_picker(self):
        """Open the in-app retro skin switcher picker."""
        p_def = self._current_platform_def()
        platform_dir = os.path.join(self.base_path, "platforms", p_def.folder)
        
        skins = ["none"]
        if os.path.exists(platform_dir):
            found_skins = sorted([f for f in os.listdir(platform_dir) if f.endswith(".skin") and f != "none"])
            skins.extend(found_skins)
            
        self.skin_picker_items = skins
        self.skin_picker_initial_skin = p_def.skin_file
        if p_def.skin_file in skins:
            self.skin_picker_idx = skins.index(p_def.skin_file)
        elif is_none_token(p_def.skin_file):
            self.skin_picker_idx = 0
        else:
            self.skin_picker_idx = 0
            
        self.skin_picker_active = True
        log.info("skin picker open current=%s count=%d", self.skin_picker_initial_skin, len(self.skin_picker_items))
        self.confirm_action = None
        self.confirm_message = ""
        self.search_active = False
        self.show_info_osd = False
        self.show_settings_osd = False

    def _refresh_info_osd(self):
        p_def = self._current_platform_def()
        rom_count = len(self.rom_list) if self.rom_list else 0
        self.info_osd_lines = build_osd_lines(
            self.base_path, p_def, self.rom_manager.config, rom_count, self.platform_issues,
        )

    def _toggle_info_osd(self):
        self.show_settings_osd = False
        self.show_info_osd = not self.show_info_osd
        if self.show_info_osd:
            self.info_osd_scroll = 0
            self._refresh_info_osd()

    def _report_platform_diagnostics(self, platform_def):
        issues = check_platform(self.base_path, platform_def)
        self.platform_issues = issues
        for issue in issues:
            if issue.level == "error":
                log.error("%s", issue.format())
            elif issue.level == "warn":
                log.warning("%s", issue.format())
            else:
                log.debug("%s", issue.format())

        msg = startup_message(issues)
        if msg:
            extra = ""
            problem_count = sum(1 for i in issues if i.level in ("error", "warn"))
            if problem_count > 1:
                extra = f" (+{problem_count - 1} more — run: python MAMEly.py --check)"
            diag_duration = self.skin.get("diagnosticMessageTime", 15)
            self.set_message(msg + extra + " (F1 for details)", duration=diag_duration)
        else:
            self.message = ""

    def update_view_lists(self, reset_selection=True):
        self.genre_list = self.rom_manager.get_genre_list()
        
        # Validate genre index
        if self.current_genre_idx >= len(self.genre_list):
            self.current_genre_idx = 0
            
        current_genre = self.genre_list[self.current_genre_idx]
        self.rom_list = self.rom_manager.get_roms_by_genre(current_genre)
        
        # Real-time search filtering
        if self.search_query:
            query = self.search_query.lower()
            self.rom_list = [
                rom for rom in self.rom_list 
                if query in rom.description.lower() or query in rom.name.lower()
            ]
        
        if reset_selection:
            self.selected_rom_idx = 0
            
        # Validate rom index
        if self.selected_rom_idx >= len(self.rom_list):
             self.selected_rom_idx = max(0, len(self.rom_list) - 1)

    def set_message(self, msg, duration=None):
        self.message = msg
        self.message_start_time = time.time()
        self._current_message_duration = (
            duration if duration is not None else self.message_duration
        )

    def _selected_rom(self):
        if self.rom_list and 0 <= self.selected_rom_idx < len(self.rom_list):
            return self.rom_list[self.selected_rom_idx]
        return None

    def _save_session(self):
        if not self.config.platforms:
            return
        p_def = self._current_platform_def()
        rom = self._selected_rom()
        genre = self.genre_list[self.current_genre_idx] if self.genre_list else ""
        self.config.session_platform = p_def.name
        self.config.session_rom = rom.name if rom else ""
        self.config.session_genre = genre
        self.config.save_main_config()
        log.debug(
            "session saved platform=%s genre=%s rom=%s",
            self.config.session_platform, self.config.session_genre, self.config.session_rom,
        )

    def _restore_startup_platform(self):
        if not self.config.remember_emulator or not self.config.session_platform:
            return
        wanted = self.config.session_platform
        for i, p_def in enumerate(self.config.platforms):
            if p_def.name == wanted or p_def.folder == wanted:
                self.platform_idx = i
                log.info("session restore platform=%s", p_def.name)
                return

    def _restore_session_selection(self):
        if not self.config.remember_game:
            return False
        genre = self.config.session_genre
        rom_name = self.config.session_rom
        if not genre and not rom_name:
            return False

        if genre and genre in self.genre_list:
            self.current_genre_idx = self.genre_list.index(genre)
        elif "Favorites" in self.genre_list:
            self.current_genre_idx = self.genre_list.index("Favorites")
        else:
            self.current_genre_idx = 0
        self.update_view_lists()

        if rom_name:
            for i, rom in enumerate(self.rom_list):
                if rom.name == rom_name:
                    self.selected_rom_idx = i
                    log.info("session restore genre=%s rom=%s", self.genre_list[self.current_genre_idx], rom_name)
                    return True
            if "All Games" in self.genre_list:
                self.current_genre_idx = self.genre_list.index("All Games")
                self.update_view_lists()
                for i, rom in enumerate(self.rom_list):
                    if rom.name == rom_name:
                        self.selected_rom_idx = i
                        log.info("session restore via All Games rom=%s", rom_name)
                        return True
            log.info("session restore missed rom=%s on this platform", rom_name)
        return True

    def _settings_rows(self):
        values = {
            "remember_emulator": self.config.remember_emulator,
            "remember_game": self.config.remember_game,
            "play_demo_video": self.config.play_demo_video,
            "attract_mode": self.config.attract_mode,
        }
        rows = []
        for row in SETTINGS_ROWS:
            if row.get("section"):
                rows.append(row)
            else:
                item = dict(row)
                item["value"] = values.get(row["key"], True)
                rows.append(item)
        return rows

    def _open_settings_osd(self):
        if self.skin_picker_active:
            self.switch_skin(self.skin_picker_initial_skin, save=False)
            self.skin_picker_active = False
        self.show_info_osd = False
        self.search_active = False
        self.confirm_action = None
        self.confirm_message = ""
        self.show_settings_osd = True
        self.settings_idx = 0
        pygame.mouse.set_visible(True)
        self._mouse_cursor_visible = True
        log.info("settings open")

    def _close_settings_osd(self):
        if self.show_settings_osd:
            log.info("settings close")
        self.show_settings_osd = False

    def _toggle_setting(self, key):
        if key == "remember_emulator":
            self.config.remember_emulator = not self.config.remember_emulator
        elif key == "remember_game":
            self.config.remember_game = not self.config.remember_game
        elif key == "play_demo_video":
            self.config.play_demo_video = not self.config.play_demo_video
            if not self.config.play_demo_video and self.ui:
                self.ui.close_video()
        elif key == "attract_mode":
            self.config.attract_mode = not self.config.attract_mode
        else:
            return
        self.config.save_main_config()
        value = getattr(self.config, key)
        log.info("setting %s=%s", key, value)

    def _update_mouse_chrome(self):
        if not self.ui:
            return
        now = time.time()
        moving = (now - self.input.last_mouse_move_time) < MOUSE_CURSOR_TIMEOUT
        overlays = (
            self.show_settings_osd or self.show_info_osd or self.skin_picker_active
            or self.confirm_action or self.search_active or self.randomizing
        )
        show_cursor = moving or self.show_settings_osd
        if show_cursor != self._mouse_cursor_visible:
            pygame.mouse.set_visible(show_cursor)
            self._mouse_cursor_visible = show_cursor

        in_corner = self.ui.settings_gear_rect().collidepoint(self.input.mouse_pos)
        show_gear = moving and in_corner and not overlays
        return show_gear

    def _handle_mouse_click(self, pos):
        if not pos or not self.ui:
            return False
        self.last_interaction_time = time.time()
        if self.show_settings_osd:
            for key, rect in self.settings_hit_rects:
                if rect.collidepoint(pos):
                    self._toggle_setting(key)
                    return True
            return True
        overlays = (
            self.show_info_osd or self.skin_picker_active
            or self.confirm_action or self.search_active or self.randomizing
        )
        if not overlays and self.ui.settings_gear_rect().collidepoint(pos):
            self._open_settings_osd()
            return True
        return False

    def _resolve_emulator_flags(self, flags_str):
        if not flags_str:
            return []

        parts = shlex.split(flags_str)
        resolved = []
        i = 0
        while i < len(parts):
            if parts[i] == "-conf" and i + 1 < len(parts):
                conf_path = parts[i + 1]
                if not os.path.isabs(conf_path):
                    conf_path = os.path.join(self.rom_manager.platform_path, conf_path)
                resolved.extend(["-conf", conf_path])
                i += 2
            else:
                resolved.append(parts[i])
                i += 1
        return resolved

    def _inject_flatpak_env(self, cmd, env_vars):
        for i, arg in enumerate(cmd):
            if any(arg.startswith(prefix) for prefix in ("com.", "net.", "org.", "io.")) and i > 0 and cmd[i - 1] != "--env":
                for key, value in reversed(list(env_vars.items())):
                    cmd.insert(i, f"--env={key}={value}")
                break

    def _release_joysticks(self):
        self.input.joysticks = []
        pygame.joystick.quit()

    def _init_joysticks(self):
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i)
            j.init()
            self.input.joysticks.append(j)
        log.debug("joysticks re-init count=%d", len(self.input.joysticks))

    def run_rom(self):
        if not self.rom_list:
            return

        rom = self.rom_list[self.selected_rom_idx]
        self.rom_manager.record_play(rom.name)
        rom_file = rom.name
        ext = self.rom_manager.config.rom_extension
        if ext and not rom_file.endswith(ext):
            rom_file = rom_file + ext

        full_rom_path = os.path.join(self.rom_manager.config.emulator_base_path, self.rom_manager.config.rom_directory, rom_file)
        flags = self.rom_manager.get_rom_flags(rom.name)
        exe = self.rom_manager.config.emulator_executable

        cmd = shlex.split(exe)
        cmd.extend(self._resolve_emulator_flags(self.rom_manager.config.emulator_default_flags))
        if flags:
            cmd.extend(shlex.split(flags))
        if "--file-forwarding" in exe:
            cmd.extend(["@@", full_rom_path, "@@"])
        elif exe == "mame" or exe.endswith("/mame"):
            if "-rompath" not in cmd and self.rom_manager.config.rom_directory:
                cmd.extend(["-rompath", self.rom_manager.config.rom_directory])
            cmd.append(rom.name)
        else:
            cmd.append(full_rom_path)

        env = os.environ.copy()
        if "flatpak" in exe:
            for entry in os.listdir(self.rom_manager.platform_path):
                if entry.startswith("mamely-") and entry.endswith("-config"):
                    config_home = os.path.join(self.rom_manager.platform_path, entry)
                    if os.path.isdir(config_home):
                        self._inject_flatpak_env(cmd, {"XDG_CONFIG_HOME": os.path.abspath(config_home)})
                        break

        quoted = " ".join(shlex.quote(arg) for arg in cmd)
        platform_name = self._current_platform_def().name
        self._save_session()
        log.info(
            "launch start platform=%s rom=%s desc=%r plays=%s cmd=%s",
            platform_name, rom.name, rom.description, rom.play_count, quoted,
        )
        self._release_joysticks()
        rc = None
        t0 = time.time()
        try:
            with open("debug.log", "a") as f:
                f.write(f"Executing: {cmd}\n")
                result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT)
                rc = result.returncode
        except Exception:
            log.exception("launch failed rom=%s cmd=%s", rom.name, quoted)
        else:
            elapsed = time.time() - t0
            if rc:
                log.warning("launch end rom=%s rc=%s elapsed=%.1fs", rom.name, rc, elapsed)
            else:
                log.info("launch end rom=%s rc=%s elapsed=%.1fs", rom.name, rc, elapsed)
        finally:
            self._init_joysticks()
            pygame.event.clear()

    def handle_input(self):
        if self.search_active:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    log.info("quit during search")
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.last_interaction_time = time.time()  # Reset idle timer!
                    if event.key == pygame.K_ESCAPE:
                        log.info("search cancel query=%r matches=%d", self.search_query, len(self.rom_list))
                        self.search_active = False
                        self.search_query = ""
                        self.update_view_lists()
                    elif event.key in (pygame.K_F3, pygame.K_ASTERISK, pygame.K_KP_MULTIPLY):
                        self.search_active = False
                        self._open_settings_osd()
                    elif event.key == pygame.K_RETURN:
                        rom = self._selected_rom()
                        log.info(
                            "search apply query=%r matches=%d selected=%s",
                            self.search_query, len(self.rom_list), rom.name if rom else "-",
                        )
                        self.search_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.search_query = self.search_query[:-1]
                        self.update_view_lists()
                    elif event.key == pygame.K_UP:
                        if self.rom_list:
                            self.selected_rom_idx = (self.selected_rom_idx - 1) % len(self.rom_list)
                    elif event.key == pygame.K_DOWN:
                        if self.rom_list:
                            self.selected_rom_idx = (self.selected_rom_idx + 1) % len(self.rom_list)
                    else:
                        if event.unicode and ord(event.unicode) >= 32:
                            self.search_query += event.unicode
                            self.update_view_lists()
            return

        action = self.input.get_action()
        click = self.input.consume_mouse_click()
        if click and self._handle_mouse_click(click):
            return
        if action != self.input.ACTION_NONE:
            self.last_interaction_time = time.time()  # Reset idle timer!
            if action != self.input.ACTION_PAUSE:
                self.video_paused = False

        if self.show_settings_osd:
            if action in (self.input.ACTION_SETTINGS, self.input.ACTION_EXIT):
                self._close_settings_osd()
                pygame.event.clear()
                return
            if action == self.input.ACTION_HELP:
                self._close_settings_osd()
                self._toggle_info_osd()
                return
            if action == self.input.ACTION_UP:
                self.settings_idx = (self.settings_idx - 1) % len(SETTINGS_TOGGLE_KEYS)
                return
            if action == self.input.ACTION_DOWN:
                self.settings_idx = (self.settings_idx + 1) % len(SETTINGS_TOGGLE_KEYS)
                return
            if action in (
                self.input.ACTION_RUN,
                self.input.ACTION_LEFT,
                self.input.ACTION_RIGHT,
                self.input.ACTION_PAGE_UP,
                self.input.ACTION_PAGE_DOWN,
                self.input.ACTION_PAUSE,
            ):
                self._toggle_setting(SETTINGS_TOGGLE_KEYS[self.settings_idx])
                return
            return

        if self.show_info_osd:
            if action == self.input.ACTION_SETTINGS:
                self.show_info_osd = False
                self._open_settings_osd()
                return
            if action == self.input.ACTION_HELP:
                log.info("osd close")
                self.show_info_osd = False
                pygame.event.clear()
                return
            if action == self.input.ACTION_EXIT:
                log.info("osd close")
                self.show_info_osd = False
                pygame.event.clear()
                return
            if action == self.input.ACTION_UP:
                self.info_osd_scroll = max(0, self.info_osd_scroll - 1)
                return
            if action == self.input.ACTION_DOWN:
                page = self.ui.info_panel_page_size() if self.ui else 1
                max_scroll = max(0, len(self.info_osd_lines) - page)
                self.info_osd_scroll = min(self.info_osd_scroll + 1, max_scroll)
                return
            return

        if self.skin_picker_active:
            if action == self.input.ACTION_SETTINGS:
                self.switch_skin(self.skin_picker_initial_skin, save=False)
                self.skin_picker_active = False
                self._open_settings_osd()
                pygame.event.clear()
                return
            if action in (self.input.ACTION_SKIN, self.input.ACTION_EXIT):
                log.info("skin picker cancel restored=%s", self.skin_picker_initial_skin)
                self.switch_skin(self.skin_picker_initial_skin, save=False)
                self.skin_picker_active = False
                pygame.event.clear()
                return
            elif action == self.input.ACTION_RUN:
                if self.skin_picker_items:
                    chosen = self.skin_picker_items[self.skin_picker_idx]
                    self.switch_skin(chosen, save=True)
                    self.set_message(f"Skin set to: {chosen}", duration=3)
                self.skin_picker_active = False
                pygame.event.clear()
                return
            elif action == self.input.ACTION_UP:
                if self.skin_picker_items:
                    self.skin_picker_idx = (self.skin_picker_idx - 1) % len(self.skin_picker_items)
                    self.switch_skin(self.skin_picker_items[self.skin_picker_idx], save=False)
                return
            elif action == self.input.ACTION_DOWN:
                if self.skin_picker_items:
                    self.skin_picker_idx = (self.skin_picker_idx + 1) % len(self.skin_picker_items)
                    self.switch_skin(self.skin_picker_items[self.skin_picker_idx], save=False)
                return
            return
        
        # Confirmation Overlay Logic
        if self.confirm_action:
            if action == self.input.ACTION_SETTINGS:
                log.info("confirm cancelled for settings message=%r", self.confirm_message)
                self.confirm_action = None
                self.confirm_message = ""
                self._open_settings_osd()
                return
            if action == self.input.ACTION_RUN:
                log.info("confirm yes message=%r", self.confirm_message)
                self.confirm_action()
                self.confirm_action = None
                self.confirm_message = ""
                # Prevent repeat action immediately
                pygame.event.clear()
            elif action == self.input.ACTION_RANDOMIZE:
                log.info("confirm redirected to randomizer message=%r", self.confirm_message)
                self.confirm_action = None
                self.confirm_message = ""
                self.run_randomizer()
            elif action in [
                self.input.ACTION_EXIT, 
                self.input.ACTION_GENRE, 
                self.input.ACTION_PLATFORM, 
                self.input.ACTION_FAVORITE,
                self.input.ACTION_IGNORE
            ]:
                log.info("confirm cancel message=%r", self.confirm_message)
                self.confirm_action = None
                self.confirm_message = ""
            return
        
        if action == self.input.ACTION_EXIT:
            if self.search_query:
                log.info("search clear query=%r", self.search_query)
                self.search_query = ""
                self.update_view_lists()
            else:
                log.info("quit requested")
                self.running = False
            
        elif action == self.input.ACTION_PLATFORM:
            self.platform_idx = (self.platform_idx + 1) % len(self.config.platforms)
            self.load_platform()
            self._save_session()
            
        elif action == self.input.ACTION_GENRE:
            self.current_genre_idx = (self.current_genre_idx + 1) % len(self.genre_list)
            self.update_view_lists()
            genre = self.genre_list[self.current_genre_idx] if self.genre_list else "-"
            log.info("genre %s listed=%d", genre, len(self.rom_list))
            
        elif action == self.input.ACTION_UP:
            if self.rom_list:
                self.selected_rom_idx = (self.selected_rom_idx - 1) % len(self.rom_list)
                
        elif action == self.input.ACTION_DOWN:
            if self.rom_list:
                self.selected_rom_idx = (self.selected_rom_idx + 1) % len(self.rom_list)
        
        elif action == self.input.ACTION_PAGE_UP or action == self.input.ACTION_LEFT:
            lines = self.skin.get("romListDisplayNumLines", 10) 
            if self.rom_list:
                self.selected_rom_idx = max(0, self.selected_rom_idx - lines)
                
        elif action == self.input.ACTION_PAGE_DOWN or action == self.input.ACTION_RIGHT:
            lines = self.skin.get("romListDisplayNumLines", 10)
            if self.rom_list:
                self.selected_rom_idx = min(len(self.rom_list) - 1, self.selected_rom_idx + lines)

        elif action == self.input.ACTION_FAVORITE:
            if self.rom_list:
                rom = self.rom_list[self.selected_rom_idx]
                
                # Check status to form message
                is_currently_fav = (rom.favorite == 1)
                action_str = "Removing" if is_currently_fav else "Adding"
                confirm_str = f"{action_str} {rom.name} to Favorites?"
                
                def do_fav():
                    is_fav = self.rom_manager.toggle_favorite(rom.name)
                    state = "added to" if is_fav else "removed from"
                    log.info("favorite rom=%s %s favorites", rom.name, state)
                    self.set_message(f"{rom.name} {state} Favorites")
                    if self.genre_list[self.current_genre_idx] == "Favorites":
                        self.update_view_lists(reset_selection=False)
                
                self.confirm_action = do_fav
                self.confirm_message = confirm_str
                log.info("confirm ask %s", confirm_str)

        elif action == self.input.ACTION_IGNORE:
            if self.rom_list:
                rom = self.rom_list[self.selected_rom_idx]
                
                # Check status to form message
                is_currently_ign = (rom.ignore == 1)
                action_str = "Removing" if is_currently_ign else "Adding"
                confirm_str = f"{action_str} {rom.name} to Ignore List?"
                
                def do_ignore():
                    is_ign = self.rom_manager.toggle_ignore(rom.name)
                    state = "added to" if is_ign else "removed from"
                    log.info("ignore rom=%s %s ignore list", rom.name, state)
                    self.set_message(f"{rom.name} {state} Ignore List")
                    # Reload list if we are in Ignore view
                    if self.genre_list[self.current_genre_idx] == "Ignore":
                        self.update_view_lists(reset_selection=False)
                        
                self.confirm_action = do_ignore
                self.confirm_message = confirm_str
                log.info("confirm ask %s", confirm_str)

        elif action == self.input.ACTION_RUN:
            self.run_rom()

        elif action == self.input.ACTION_RANDOMIZE:
            self.run_randomizer()

        elif action == self.input.ACTION_HELP:
            self._toggle_info_osd()
            log.info("osd %s", "open" if self.show_info_osd else "close")

        elif action == self.input.ACTION_SKIN:
            self.open_skin_picker()

        elif action == self.input.ACTION_SETTINGS:
            self._open_settings_osd()

        elif action == self.input.ACTION_SEARCH:
            log.info("search start")
            self.search_active = True
            self.search_query = ""
            self.update_view_lists()

        elif action == self.input.ACTION_WIZARD:
            log.info("wizard requested")
            self.run_setup_wizard()

        elif action == self.input.ACTION_PAUSE:
            if self.ui.video_cap:
                self.video_paused = not self.video_paused
                log.info("video %s rom=%s", "paused" if self.video_paused else "playing", self._selected_rom().name if self._selected_rom() else "-")
                self.set_message("Video Paused" if self.video_paused else "Video Playing", duration=1)

    def run_randomizer(self):
        """Slot-machine reel: timed spin, land on a random ROM, then launch it."""
        if self.randomizing or not self.rom_list:
            return

        self.randomizing = True
        self.confirm_action = None
        self.confirm_message = ""
        self.search_active = False
        self.show_info_osd = False
        self.show_settings_osd = False
        self.ui.close_video()
        self.video_paused = False
        self.message = ""

        n = len(self.rom_list)
        start_idx = self.selected_rom_idx % n
        target_idx = random.randrange(n)
        labels = [rom.description or rom.name for rom in self.rom_list]
        font_name = self.skin.get("romListDisplayFont")

        # Fixed-length spin (NOT one step per ROM — that never finished on big lists)
        total_rows = random.randint(42, 64)
        total_rows += (target_idx - (start_idx + total_rows) % n) % n
        start_pos = float(start_idx)
        end_pos = start_pos + float(total_rows)

        duration = 3.6  # seconds of spinning
        t0 = time.time()
        cancelled = False
        last_tick_idx = start_idx

        log.info(
            "randomizer start listed=%d from=%s target=%s steps=%d",
            n, self.rom_list[start_idx].name, self.rom_list[target_idx].name, total_rows,
        )

        def ease_out_quint(t):
            u = 1.0 - t
            return 1.0 - u * u * u * u * u

        # --- SPIN ---
        while True:
            now = time.time()
            elapsed = now - t0
            t = min(1.0, elapsed / duration)
            reel_pos = start_pos + total_rows * ease_out_quint(t)
            current_idx = int(reel_pos) % n

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    cancelled = True
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    cancelled = True

            if cancelled or not self.running:
                break

            # Soft click feel when the payline crosses a new title
            if current_idx != last_tick_idx:
                last_tick_idx = current_idx
                self.selected_rom_idx = current_idx

            self.ui.begin_frame()
            self.ui.draw_slot_machine(labels, reel_pos, font_name=font_name, phase="spin")
            self.ui.end_frame()

            if t >= 1.0:
                break

        if cancelled or not self.running:
            self.randomizing = False
            log.info("randomizer cancelled")
            self.set_message("Randomizer cancelled", duration=1)
            pygame.event.clear()
            self.input.current_action = self.input.ACTION_NONE
            return

        # Snap exactly onto the winner
        self.selected_rom_idx = target_idx
        winner = self.rom_list[target_idx]
        log.info("randomizer land rom=%s desc=%r launching", winner.name, winner.description)

        # --- WIN CELEBRATION ---
        win_t0 = time.time()
        while time.time() - win_t0 < 1.25 and self.running:
            flash = time.time() - win_t0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
            self.ui.begin_frame()
            self.ui.draw_slot_machine(
                labels, float(target_idx), font_name=font_name, phase="win", flash=flash
            )
            self.ui.end_frame()

        self.randomizing = False
        self.last_interaction_time = time.time()
        pygame.event.clear()
        self.input.current_action = self.input.ACTION_NONE

        if self.running:
            self.run_rom()

    def _text_anchor(self, prefix, align_key):
        """Resolve (x, align) for a text zone from its skin alignment key.

        'left' anchors on the zone's X1, 'right' on X2, 'center' on the
        derived XCenter. Unknown/missing values fall back to center.
        """
        align = self.skin.get(align_key, "center")
        align = str(align).strip().lower() if align else "center"
        if align not in ("left", "center", "right"):
            align = "center"

        if align == "left":
            x = self.skin.get(prefix + "X1")
        elif align == "right":
            x = self.skin.get(prefix + "X2")
        else:
            x = self.skin.get(prefix + "XCenter")
        return x, align

    def draw(self):
        self.ui.begin_frame()
        if not self.rom_list:
            self.ui.close_video()
        
        # 1. Draw Genre Set
        cur_genre = self.genre_list[self.current_genre_idx] if self.genre_list else ""
        if cur_genre not in ["All Games", "Favorites", "Ignore"]:
             text = "Genre: " + cur_genre
        else:
             text = cur_genre

        gs_x, gs_align = self._text_anchor("genreSet", "genreSetAlign")
        self.ui.draw_text(text,
                          gs_x,
                          self.skin.get("genreSetYCenter"),
                          self.skin.get("genreSetFont"),
                          self.skin.get("genreSetFontSize", 20),
                          self.skin.get("defaultGameSetBarColor", (255, 255, 255)),
                          self.skin.get("defaultGameSetBarShadowColor", (0, 0, 0)),
                          self.skin.get("genreSetShadow"),
                          self.skin.get("genreSetTruncateLen"),
                          align=gs_align)

        # 2. Draw ROM List
        # Calculate list geometry based on skin
        y1 = self.skin.get("romListDisplayAreaY1", 100)
        y2 = self.skin.get("romListDisplayAreaY2", 500)
        spacing = self.skin.get("romListDisplaySpacing", 20)
        list_x, list_align = self._text_anchor("romListDisplayArea", "romListDisplayAlign")
        if list_x is None:
            list_x = 400
        
        num_lines = int((y2 - y1) / spacing)
        mid_line = num_lines // 2
        
        start_idx = self.selected_rom_idx - mid_line
        
        for i in range(num_lines):
            rom_idx = start_idx + i
            # Check bounds logic? Original wrapped around in a weird way or just showed blank?
            # Original: insert blanks at top/bottom of genreSet (lines 993-997 MAMEly.py)
            # Impl: Check bounds, draw nothing if out of bounds
            
            # Original used offset of 1 * spacing
            display_y = y1 + (i + 1) * spacing
            
            if 0 <= rom_idx < len(self.rom_list):
                rom = self.rom_list[rom_idx]
                is_selected = (rom_idx == self.selected_rom_idx)
                
                color = self.skin.get("defaultHighlightFontForegroundColor") if is_selected else self.skin.get("defaultFontForegroundColor")
                shadow_color = self.skin.get("defaultRomNameDisplayLineHighlightShadowColor") if is_selected else self.skin.get("defaultRomNameDisplayLineShadowColor")
                shadow = self.skin.get("romListDisplayHighlightShadow") if is_selected else self.skin.get("romListDisplayShadow")
                
                self.ui.draw_text(rom.description,
                                  list_x,
                                  display_y,
                                  self.skin.get("romListDisplayFont"),
                                  self.skin.get("romListDisplayFontSize", 20),
                                  color,
                                  shadow_color,
                                  shadow,
                                  self.skin.get("romListDisplayTruncateLen"),
                                  align=list_align)
                                  
                if is_selected:
                    # Draw Details for selected ROM
                    snap_x1 = self.skin.get("romSnapX1", 0) or 0
                    snap_x2 = self.skin.get("romSnapX2", 0) or 0
                    snap_y1 = self.skin.get("romSnapY1", 0) or 0
                    snap_y2 = self.skin.get("romSnapY2", 0) or 0
                    self.max_snap_w = snap_x2 - snap_x1
                    self.max_snap_h = snap_y2 - snap_y1
                    
                    # During slot spin, skip snaps/video for speed and to avoid attract mode
                    if self.randomizing:
                        pass
                    else:
                        # Video Snap path check
                        video_dir = self.rom_manager.config.rom_video_directory
                        video_ext = self.rom_manager.config.video_extension
                        rom_name = rom.name
                        
                        video_path = None
                        if video_dir:
                            vp1 = os.path.join(video_dir, rom_name + video_ext)
                            vp2 = os.path.join(video_dir, rom_name, "0000" + video_ext)
                            if os.path.exists(vp1):
                                video_path = vp1
                            elif os.path.exists(vp2):
                                video_path = vp2
                                
                        # Render Video (if idle for 5s) or Fallback to Static Snap
                        elapsed = time.time() - self.last_interaction_time
                        
                        # Attract Mode check: Idle for 65 seconds (5s image snap + 60s video snap) triggers fullscreen playback
                        overlays = (
                            self.show_settings_osd or self.show_info_osd
                            or self.skin_picker_active or self.confirm_action
                            or self.search_active
                        )
                        if elapsed >= 65.0 and video_path and self.config.attract_mode and not overlays:
                            self.run_attract_mode(video_path)
                            return
                        
                        video_rendered = False
                        if elapsed >= 5.0 and video_path and self.config.play_demo_video and not overlays:
                            self.ui.set_active_video(video_path)
                            video_rendered = self.ui.draw_video_frame(
                                snap_x1, snap_y1, snap_x2, snap_y2,
                                paused=self.video_paused
                            )
                        else:
                            self.ui.set_active_video(None)
                            
                        if not video_rendered:
                            snap_dir = self.rom_manager.config.rom_snap_directory
                            ext = self.rom_manager.config.snap_extension
                            
                            path1 = os.path.join(snap_dir, rom_name + ext)
                            path2 = os.path.join(snap_dir, rom_name, "0000" + ext)
                            
                            self.ui.draw_image(path1, snap_x1, snap_y1, snap_x2, snap_y2, fallback_path=path2)
                                       
                    # Draw Genre and Rating
                    gy = self.skin.get("romGenreYCenter_effective", self.skin.get("romGenreYCenter"))
                    ry = self.skin.get("romRatingYCenter")
                    
                    gx, g_align = self._text_anchor("romGenre", "romGenreAlign")
                    rx, r_align = self._text_anchor("romRating", "romRatingAlign")
                    if self.skin.get("romRatingAlign") is None:
                        r_align = g_align

                    g_txt = f"Genre: {rom.genre}"
                    r_txt = f"Rating: {rom.rating}"

                    self.ui.draw_text(g_txt, gx, gy, 
                                      self.skin.get("romGenreFont"),
                                      self.skin.get("romGenreFontSize"),
                                      self.skin.get("defaultRomGenreColor", self.skin.get("defaultRomNameDisplayBoxColor")),
                                      shadow_color=self.skin.get("defaultRomGenreShadowColor"),
                                      shadow=self.skin.get("romGenreShadow"),
                                      truncate_len=self.skin.get("romGenreTruncateLen"),
                                      align=g_align)

                    self.ui.draw_text(r_txt, rx, ry, 
                                      self.skin.get("romRatingFont", self.skin.get("romGenreFont")),
                                      self.skin.get("romRatingFontSize", self.skin.get("romGenreFontSize")),
                                      self.skin.get("defaultRomRatingColor", self.skin.get("defaultRomGenreColor", self.skin.get("defaultRomNameDisplayBoxColor"))),
                                      shadow_color=self.skin.get("defaultRomRatingShadowColor"),
                                      shadow=self.skin.get("romRatingShadow", self.skin.get("romGenreShadow")),
                                      truncate_len=self.skin.get("romRatingTruncateLen", self.skin.get("romGenreTruncateLen")),
                                      align=r_align)
                                          
                    # Draw Count
                    count_txt = f"{self.selected_rom_idx + 1} of {len(self.rom_list)}"
                    cx, c_align = self._text_anchor("romCount", "romCountAlign")
                    self.ui.draw_text(count_txt,
                                      cx,
                                      self.skin.get("romCountYCenter"),
                                      self.skin.get("romCountFont"),
                                      self.skin.get("romCountFontSize"),
                                      self.skin.get("defaultRomCountColor"),
                                      shadow=self.skin.get("romCountShadow"),
                                      align=c_align)
                                      
                    # Draw Filename
                    fx, f_align = self._text_anchor("romFileNameDisplayBox", "romFileNameDisplayBoxAlign")
                    self.ui.draw_text(rom.name,
                                      fx,
                                      self.skin.get("romFileNameDisplayBoxYCenter"),
                                      self.skin.get("romFileNameDisplayBoxFont"),
                                      self.skin.get("romFileNameDisplayBoxFontSize"),
                                      self.skin.get("defaultRomFileNameColor"),
                                      shadow=self.skin.get("romFileNameShadow"),
                                      truncate_len=self.skin.get("romFileNameDisplayBoxTruncateLen"),
                                      align=f_align)


        if self.show_settings_osd:
            self.settings_hit_rects = self.ui.draw_settings_panel(
                self._settings_rows(), self.settings_idx,
            )
        elif self.show_info_osd:
            self.ui.draw_info_panel(self.info_osd_lines, self.info_osd_scroll)
        elif self.skin_picker_active:
            p_def = self._current_platform_def()
            self.ui.draw_skin_picker(
                self.skin_picker_items,
                self.skin_picker_idx,
                p_def.skin_file,
                p_def.name,
            )
        elif self.confirm_action:
            self.ui.draw_modal(self.confirm_message)
            
        if self.message:
            if time.time() - self.message_start_time > self._current_message_duration:
                self.message = ""
            else:
                self.ui.draw_toast_message(self.message)

        if self.search_active or self.search_query:
            self.ui.draw_search_bar(self.search_query, self.search_active)

        show_gear = self._update_mouse_chrome()
        if show_gear:
            highlighted = self.ui.settings_gear_rect().collidepoint(self.input.mouse_pos)
            self.ui.draw_settings_gear(highlighted=highlighted)
            
        self.ui.end_frame()

    def run_attract_mode(self, video_path):
        """Fullscreen attract playback inside the Pygame window.

        External players (ffplay -fs) steal keyboard focus, so any-key interrupt
        fails. We blit frames with OpenCV/Pygame (keeps focus) and play audio
        with headless ffplay (-nodisp). Any key, joystick button, or mouse
        click ends attract mode.
        """
        import cv2
        log.info("attract start path=%s", video_path)

        self.ui.close_video()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log.warning("attract failed to open path=%s", video_path)
            self.last_interaction_time = time.time()
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if fps <= 1.0:
            fps = 30.0
        frame_delay = 1.0 / fps

        # Audio only — no video window, so Pygame keeps input focus
        audio_proc = None
        try:
            audio_proc = subprocess.Popen([
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel", "quiet",
                video_path,
            ])
        except Exception as e:
            log.warning("attract audio unavailable (ffplay): %s", e)

        screen_w = self.ui.screen_width
        screen_h = self.ui.screen_height
        next_frame_at = time.time()
        attract_t0 = time.time()
        reason = "ended"
        running_attract = True
        pygame.event.clear()  # Drop queued input so attract doesn't exit immediately

        while running_attract:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    running_attract = False
                    reason = "quit"
                    break
                if event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.MOUSEBUTTONDOWN):
                    running_attract = False
                    reason = "interrupt"
                    break

            if not running_attract:
                break

            now = time.time()
            if now < next_frame_at:
                pygame.time.wait(5)
                continue

            ret, frame = cap.read()
            if not ret:
                break

            try:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.transpose(frame)
                img = pygame.surfarray.make_surface(frame)
                img_w, img_h = img.get_size()
                scale = min(screen_w / float(img_w), screen_h / float(img_h))
                new_w, new_h = max(1, int(img_w * scale)), max(1, int(img_h * scale))
                scaled = pygame.transform.scale(img, (new_w, new_h))
                self.ui.screen.fill((0, 0, 0))
                self.ui.screen.blit(scaled, ((screen_w - new_w) // 2, (screen_h - new_h) // 2))
                pygame.display.flip()
            except Exception as e:
                log.warning("attract frame error: %s", e)
                reason = "error"
                break

            next_frame_at = now + frame_delay

        if audio_proc is not None and audio_proc.poll() is None:
            try:
                audio_proc.terminate()
                audio_proc.wait(timeout=1.0)
            except Exception:
                try:
                    audio_proc.kill()
                except Exception:
                    pass

        try:
            cap.release()
        except Exception:
            pass

        # Resume inline video snap immediately on return
        self.last_interaction_time = time.time() - 5.0
        self.video_paused = False
        pygame.event.clear()
        log.info("attract end reason=%s elapsed=%.1fs path=%s", reason, time.time() - attract_t0, video_path)

    def run_setup_wizard(self):
        from wizard import SetupWizard
        if self.ui is None:
            if self.config.platforms:
                p_def = self.config.platforms[self.platform_idx]
                platform_path = os.path.join(self.base_path, "platforms", p_def.folder)
                self.skin = SkinConfig(platform_path, p_def.skin_file)
                self.ui = UIManager(self.config, self.skin)
            else:
                # Wizard init will handle dummy ui
                pass
            
        wizard = SetupWizard(self)
        wizard.run()
        
        # Reload configuration
        self.config = Config(self.base_path, self.config_file)
        self.platform_idx = 0
        self.load_platform()

    def run(self):
        # Check diagnostics on startup.
        # We auto-launch the wizard if --wizard was passed, if no platforms are defined,
        # or if ALL platforms are broken (have critical errors).
        all_broken = True
        if self.config.platforms:
            for p_def in self.config.platforms:
                p_issues = check_platform(self.base_path, p_def)
                p_errors = [i for i in p_issues if i.level == "error"]
                if not p_errors:
                    all_broken = False
                    break
        else:
            all_broken = True

        if self.launch_wizard or all_broken:
            log.info(
                "startup wizard launch_wizard=%s all_broken=%s platforms=%d",
                self.launch_wizard, all_broken, len(self.config.platforms),
            )
            self.run_setup_wizard()
        else:
            self._restore_startup_platform()
            self.load_platform(restore_session=True)
        
        while self.running:
            self.handle_input()
            self.draw()
        
        self._save_session()
        log.info("shutdown elapsed=%.0fs", time.time() - self._started_at)
        if self.ui:
            self.ui.close_video()
        pygame.quit()

if __name__ == "__main__":
    app = MAMElyApp()
    app.run()
