import sys
import os
import time
import pygame
from config import Config, PlatformConfig, SkinConfig
from roms import RomManager
from ui import UIManager
from input import InputManager
from version import __version__

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
        if len(sys.argv) > 1:
             for arg in sys.argv:
                 if arg.startswith("-config="):
                     self.config_file = arg.split("=")[1]

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
        
        # Confirmation Logic
        self.confirm_action = None
        self.confirm_message = ""

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

    def update_view_lists(self, reset_selection=True):
        self.genre_list = self.rom_manager.get_genre_list()
        
        # Validate genre index
        if self.current_genre_idx >= len(self.genre_list):
            self.current_genre_idx = 0
            
        current_genre = self.genre_list[self.current_genre_idx]
        self.rom_list = self.rom_manager.get_roms_by_genre(current_genre)
        
        if reset_selection:
            self.selected_rom_idx = 0
            
        # Validate rom index
        if self.selected_rom_idx >= len(self.rom_list):
             self.selected_rom_idx = max(0, len(self.rom_list) - 1)

    def set_message(self, msg):
        self.message = msg
        self.message_start_time = time.time()

    def run_rom(self):
        if not self.rom_list: return
        
        rom = self.rom_list[self.selected_rom_idx]
        rom_file = rom.name + self.rom_manager.config.rom_extension
        # Flag logic
        flags = self.rom_manager.get_rom_flags(rom.name)
        
        full_rom_path = os.path.join(self.rom_manager.config.rom_directory, rom_file)
        full_rom_path = f'"{full_rom_path}"' # Quote path
        
        exe = self.rom_manager.config.emulator_executable
        
        cmd = f"{exe} {flags} {full_rom_path}"
        print(f"Executing: {cmd}")
        os.system(cmd)
        
        # Clear input queue after return
        pygame.event.clear()

    def handle_input(self):
        action = self.input.get_action()
        
        # Confirmation Overlay Logic
        if self.confirm_action:
            if action == self.input.ACTION_RUN:
                self.confirm_action()
                self.confirm_action = None
                self.confirm_message = ""
                # Prevent repeat action immediately
                pygame.event.clear()
            elif action in [self.input.ACTION_EXIT, self.input.ACTION_GENRE, self.input.ACTION_PLATFORM, self.input.ACTION_FAVORITE]:
                # Cancel
                self.confirm_action = None
                self.confirm_message = ""
            return
        
        if action == self.input.ACTION_EXIT:
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
                is_ign = self.rom_manager.toggle_ignore(rom.name)
                state = "added to" if is_ign else "removed from"
                self.set_message(f"{rom.name} {state} Ignore List")
                # Reload list if we are in Ignore view
                if self.genre_list[self.current_genre_idx] == "Ignore":
                    self.update_view_lists(reset_selection=False)

        elif action == self.input.ACTION_RUN:
            self.run_rom()

    def draw(self):
        self.ui.begin_frame()
        
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
                          self.skin.get("defaultGameSetBarColor"),
                          self.skin.get("defaultGameSetBarShadowColor"),
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
                    
                    # Snap path
                    # Try base path + rom name + ext, then rom directory + rom name + /0000 + ext
                    snap_dir = self.rom_manager.config.rom_snap_directory
                    rom_name = rom.name
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
                        if time.time() - self.message_start_time > self.message_duration:
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
                                      shadow=self.skin.get("romFileNameShadow"))


        if self.confirm_action:
            self.ui.draw_modal(self.confirm_message)
            
        self.ui.end_frame()

    def run(self):
        self.load_platform()
        
        while self.running:
            self.handle_input()
            self.draw()
        
        pygame.quit()

if __name__ == "__main__":
    app = MAMElyApp()
    app.run()
