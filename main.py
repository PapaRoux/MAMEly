import sys
import os
import time
import shlex
import subprocess
import pygame
from config import Config, PlatformConfig, SkinConfig
from roms import RomManager
from ui import UIManager
from input import InputManager
from version import __version__
from diagnostics import build_osd_lines, check_platform, startup_message, check_all, has_errors

class MAMElyApp:
    def __init__(self):
        # Initialize Pygame
        pygame.init()
        pygame.font.init()
        
        print(f"MAMEly v{__version__} Starting...")

        # Base Path
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(self.base_path)
        
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

    def load_platform(self):
        if not self.config.platforms:
            print("No platforms definitions found.")
            self.running = False
            return

        p_def = self.config.platforms[self.platform_idx]
        platform_path = os.path.join(self.base_path, "platforms", p_def.folder)
        
        print(f"Loading platform: {p_def.name}")
        
        # Load Configs
        p_conf = PlatformConfig(platform_path, p_def.config_file)
        self.skin = SkinConfig(platform_path, p_def.skin_file)
        self.message_duration = self.skin.get("messageTime", 2)
        
        # Initialize UI (re-init for potentially different background/res)
        # Note: In real scenarios we might want to keep the window open, 
        # but here we follow original flow closest regarding skin loading.
        if self.ui is None:
             self.ui = UIManager(self.config, self.skin)
        else:
             self.ui.close_video()
             self.ui.skin = self.skin
             self.ui.load_background()

        # Load ROMs
        self.ui.begin_frame()
        self.ui.show_message("Reading MAMEly.xml", self.skin.get("defaultMessageColor"))
        self.ui.end_frame()
        
        self.rom_manager = RomManager(platform_path, p_conf)
        self.rom_manager.load_skips_and_flags()
        self.rom_manager.load_roms() # Synchronous for now, could add progress callback
        
        # Default to Favorites if available
        self.genre_list = self.rom_manager.get_genre_list()
        if "Favorites" in self.genre_list:
             try:
                 self.current_genre_idx = self.genre_list.index("Favorites")
             except ValueError:
                 self.current_genre_idx = 0
        
        self.update_view_lists()
        self._report_platform_diagnostics(p_def)

    def _current_platform_def(self):
        return self.config.platforms[self.platform_idx]

    def _refresh_info_osd(self):
        p_def = self._current_platform_def()
        rom_count = len(self.rom_list) if self.rom_list else 0
        self.info_osd_lines = build_osd_lines(
            self.base_path, p_def, self.rom_manager.config, rom_count, self.platform_issues,
        )

    def _toggle_info_osd(self):
        self.show_info_osd = not self.show_info_osd
        if self.show_info_osd:
            self.info_osd_scroll = 0
            self._refresh_info_osd()

    def _report_platform_diagnostics(self, platform_def):
        issues = check_platform(self.base_path, platform_def)
        self.platform_issues = issues
        for issue in issues:
            if issue.level in ("error", "warn"):
                print(issue.format())

        msg = startup_message(issues)
        if msg:
            extra = ""
            problem_count = sum(1 for i in issues if i.level in ("error", "warn"))
            if problem_count > 1:
                extra = f" (+{problem_count - 1} more — run: python MAMEly.py --check)"
            diag_duration = self.skin.get("diagnosticMessageTime", 15)
            self.set_message(msg + extra + " (F1 for details)", duration=diag_duration)

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
            if arg.startswith("com.") and i > 0 and cmd[i - 1] != "--env":
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

    def run_rom(self):
        if not self.rom_list: return
        
        rom = self.rom_list[self.selected_rom_idx]
        rom_file = rom.name
        ext = self.rom_manager.config.rom_extension
        if ext and not rom_file.endswith(ext):
            rom_file = rom_file + ext

        full_rom_path = os.path.join(self.rom_manager.config.rom_directory, rom_file)
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
            config_home = os.path.join(self.rom_manager.platform_path, "mamely-snes9x-config")
            if os.path.isdir(config_home):
                self._inject_flatpak_env(cmd, {"XDG_CONFIG_HOME": os.path.abspath(config_home)})

        print(f"Executing: {' '.join(shlex.quote(arg) for arg in cmd)}")
        self._release_joysticks()
        try:
            subprocess.run(cmd, env=env)
        finally:
            self._init_joysticks()
            pygame.event.clear()

    def handle_input(self):
        if self.search_active:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.last_interaction_time = time.time()  # Reset idle timer!
                    if event.key == pygame.K_ESCAPE:
                        self.search_active = False
                        self.search_query = ""
                        self.update_view_lists()
                    elif event.key == pygame.K_RETURN:
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
        if action != self.input.ACTION_NONE:
            self.last_interaction_time = time.time()  # Reset idle timer!
            if action != self.input.ACTION_PAUSE:
                self.video_paused = False

        if self.show_info_osd:
            if action == self.input.ACTION_HELP:
                self.show_info_osd = False
                pygame.event.clear()
                return
            if action == self.input.ACTION_EXIT:
                self.show_info_osd = False
                pygame.event.clear()
                return
            if action == self.input.ACTION_UP:
                self.info_osd_scroll = max(0, self.info_osd_scroll - 1)
                return
            if action == self.input.ACTION_DOWN:
                max_scroll = max(0, len(self.info_osd_lines) - 1)
                self.info_osd_scroll = min(self.info_osd_scroll + 1, max_scroll)
                return
            return
        
        # Confirmation Overlay Logic
        if self.confirm_action:
            if action == self.input.ACTION_RUN:
                self.confirm_action()
                self.confirm_action = None
                self.confirm_message = ""
                # Prevent repeat action immediately
                pygame.event.clear()
            elif action in [
                self.input.ACTION_EXIT, 
                self.input.ACTION_GENRE, 
                self.input.ACTION_PLATFORM, 
                self.input.ACTION_FAVORITE,
                self.input.ACTION_IGNORE
            ]:
                # Cancel
                self.confirm_action = None
                self.confirm_message = ""
            return
        
        if action == self.input.ACTION_EXIT:
            if self.search_query:
                self.search_query = ""
                self.update_view_lists()
            else:
                self.running = False
            
        elif action == self.input.ACTION_PLATFORM:
            self.platform_idx = (self.platform_idx + 1) % len(self.config.platforms)
            self.load_platform()
            
        elif action == self.input.ACTION_GENRE:
            self.current_genre_idx = (self.current_genre_idx + 1) % len(self.genre_list)
            self.update_view_lists()
            
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
                    self.set_message(f"{rom.name} {state} Favorites")
                    if self.genre_list[self.current_genre_idx] == "Favorites":
                        self.update_view_lists(reset_selection=False)
                
                self.confirm_action = do_fav
                self.confirm_message = confirm_str

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
                    self.set_message(f"{rom.name} {state} Ignore List")
                    # Reload list if we are in Ignore view
                    if self.genre_list[self.current_genre_idx] == "Ignore":
                        self.update_view_lists(reset_selection=False)
                        
                self.confirm_action = do_ignore
                self.confirm_message = confirm_str

        elif action == self.input.ACTION_RUN:
            self.run_rom()

        elif action == self.input.ACTION_HELP:
            self._toggle_info_osd()

        elif action == self.input.ACTION_SEARCH:
            self.search_active = True
            self.search_query = ""
            self.update_view_lists()

        elif action == self.input.ACTION_WIZARD:
            self.run_setup_wizard()

        elif action == self.input.ACTION_PAUSE:
            if self.ui.video_cap:
                self.video_paused = not self.video_paused
                self.set_message("Video Paused" if self.video_paused else "Video Playing", duration=1)

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
             
        self.ui.draw_text(text,
                          self.skin.get("genreSetXCenter"),
                          self.skin.get("genreSetYCenter"),
                          self.skin.get("genreSetFont"),
                          self.skin.get("genreSetFontSize", 20),
                          self.skin.get("defaultGameSetBarColor", (255, 255, 255)),
                          self.skin.get("defaultGameSetBarShadowColor", (0, 0, 0)),
                          self.skin.get("genreSetShadow"),
                          self.skin.get("genreSetTruncateLen"))

        # 2. Draw ROM List
        # Calculate list geometry based on skin
        y1 = self.skin.get("romListDisplayAreaY1", 100)
        y2 = self.skin.get("romListDisplayAreaY2", 500)
        spacing = self.skin.get("romListDisplaySpacing", 20)
        x_center = self.skin.get("romListDisplayAreaXCenter", 400)
        
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
                                  x_center,
                                  display_y,
                                  self.skin.get("romListDisplayFont"),
                                  self.skin.get("romListDisplayFontSize", 20),
                                  color,
                                  shadow_color,
                                  shadow,
                                  self.skin.get("romListDisplayTruncateLen"))
                                  
                if is_selected:
                    # Draw Details for selected ROM
                    self.max_snap_w = self.skin.get("romSnapX2") - self.skin.get("romSnapX1")
                    self.max_snap_h = self.skin.get("romSnapY2") - self.skin.get("romSnapY1")
                    
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
                    
                    # Attract Mode check: Idle for 60 seconds triggers fullscreen playback with sound
                    if elapsed >= 60.0 and video_path:
                        self.run_attract_mode(video_path)
                        return
                    
                    video_rendered = False
                    if elapsed >= 5.0 and video_path:
                        self.ui.set_active_video(video_path)
                        video_rendered = self.ui.draw_video_frame(
                            self.skin.get("romSnapX1"), self.skin.get("romSnapY1"),
                            self.skin.get("romSnapX2"), self.skin.get("romSnapY2"),
                            paused=self.video_paused
                        )
                    else:
                        self.ui.set_active_video(None)
                        
                    if not video_rendered:
                        snap_dir = self.rom_manager.config.rom_snap_directory
                        ext = self.rom_manager.config.snap_extension
                        
                        path1 = os.path.join(snap_dir, rom_name + ext)
                        path2 = os.path.join(snap_dir, rom_name, "0000" + ext)
                        
                        self.ui.draw_image(path1, 
                                           self.skin.get("romSnapX1"), self.skin.get("romSnapY1"),
                                           self.skin.get("romSnapX2"), self.skin.get("romSnapY2"),
                                           fallback_path=path2)
                                       
                    # Draw Genre/Rating or Message
                    msg = self.message
                    if msg:
                        if time.time() - self.message_start_time > self._current_message_duration:
                            self.message = ""
                    
                    gx = self.skin.get("romGenreXCenter")
                    gy = self.skin.get("romGenreYCenter")
                    offset = self.skin.get("genreRatingOffset", 20)
                    
                    if msg:
                        self.ui.draw_text(msg, gx, gy, 
                                          self.skin.get("messageFont"),
                                          self.skin.get("messageFontSize"),
                                          self.skin.get("defaultMessageColor"),
                                          shadow=True,
                                          truncate_len=self.skin.get("messageTruncateLen"))
                    else:
                        g_txt = f"Genre: {rom.genre}"
                        r_txt = f"Rating: {rom.rating}"
                        self.ui.draw_text(g_txt, gx, gy - offset, 
                                          self.skin.get("romGenreFont"),
                                          self.skin.get("romGenreFontSize"),
                                          self.skin.get("defaultRomNameDisplayBoxColor"),
                                          shadow=self.skin.get("romGenreShadow"),
                                          truncate_len=self.skin.get("romGenreTruncateLen"))
                        self.ui.draw_text(r_txt, gx, gy + offset, 
                                          self.skin.get("romGenreFont"),
                                          self.skin.get("romGenreFontSize"),
                                          self.skin.get("defaultRomNameDisplayBoxColor"),
                                          shadow=self.skin.get("romGenreShadow"),
                                          truncate_len=self.skin.get("romGenreTruncateLen"))
                                          
                    # Draw Count
                    count_txt = f"{self.selected_rom_idx + 1} of {len(self.rom_list)}"
                    self.ui.draw_text(count_txt,
                                      self.skin.get("romCountXCenter"),
                                      self.skin.get("romCountYCenter"),
                                      self.skin.get("romCountFont"),
                                      self.skin.get("romCountFontSize"),
                                      self.skin.get("defaultRomCountColor"),
                                      shadow=self.skin.get("romCountShadow"))
                                      
                    # Draw Filename
                    self.ui.draw_text(rom.name,
                                      self.skin.get("romFileNameDisplayBoxXCenter"),
                                      self.skin.get("romFileNameDisplayBoxYCenter"),
                                      self.skin.get("romFileNameDisplayBoxFont"),
                                      self.skin.get("romFileNameDisplayBoxFontSize"),
                                      self.skin.get("defaultRomFileNameColor"),
                                      shadow=self.skin.get("romFileNameShadow"),
                                      truncate_len=self.skin.get("romFileNameDisplayBoxTruncateLen"))


        if self.show_info_osd:
            self.ui.draw_info_panel(self.info_osd_lines, self.info_osd_scroll)
        elif self.confirm_action:
            self.ui.draw_modal(self.confirm_message)
            
        if self.search_active or self.search_query:
            self.ui.draw_search_bar(self.search_query, self.search_active)
            
        self.ui.end_frame()

    def run_attract_mode(self, video_path):
        import subprocess
        print(f"Starting attract mode for: {video_path}")
        
        # Release the preview video capture
        self.ui.close_video()
        
        # Launch cvlc fullscreen with audio and exit on end
        try:
            proc = subprocess.Popen(["cvlc", "--fullscreen", "--no-video-title-show", "--play-and-exit", video_path])
        except Exception as e:
            print(f"Failed to launch cvlc: {e}")
            self.last_interaction_time = time.time()
            return
            
        running_attract = True
        while running_attract and proc.poll() is None:
            # Poll pygame events to catch user interactions
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    self.running = False
                    running_attract = False
                elif event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.MOUSEBUTTONDOWN):
                    # Interrupted by user!
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    running_attract = False
            pygame.time.wait(50)
            
        # Clean up process
        try:
            proc.wait(timeout=1.0)
        except Exception:
            pass
            
        # Reset interaction time and clear input queues to prevent double-triggering menus
        self.last_interaction_time = time.time()
        self.video_paused = False
        pygame.event.clear()
        print("Attract mode ended.")

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
            self.run_setup_wizard()
        else:
            self.load_platform()
        
        while self.running:
            self.handle_input()
            self.draw()
        
        if self.ui:
            self.ui.close_video()
        pygame.quit()

if __name__ == "__main__":
    app = MAMElyApp()
    app.run()
