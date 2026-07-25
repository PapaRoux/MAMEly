import os
import sys
import shutil
import datetime
import pygame
import xml.etree.ElementTree as ET
from config import PlatformConfig
from diagnostics import check_platform, check_all, has_errors

# Harmonious design color system
BG_COLOR = (24, 24, 37)       # Catppuccin Mocha Base
CARD_COLOR = (30, 30, 46)     # Catppuccin Mocha Mantle
TEXT_COLOR = (205, 214, 244)   # Soft text
MUTED_COLOR = (166, 173, 200)  # Muted text
ACCENT_COLOR = (137, 180, 250) # Light blue Accent
HIGHLIGHT_COLOR = (249, 226, 175) # Peach/Gold selection
ERROR_COLOR = (243, 139, 168)   # Red
SUCCESS_COLOR = (166, 227, 161) # Green
BORDER_COLOR = (88, 91, 112)   # Slate gray border

def make_description(filename, ext):
    name_without_ext = filename
    if ext and filename.endswith(ext):
        name_without_ext = filename[:-len(ext)]
    # Replace underscores/dashes with spaces
    name_spaced = name_without_ext.replace('_', ' ').replace('-', ' ')
    return name_spaced.title().strip()

class SetupWizard:
    def __init__(self, app):
        self.app = app
        self.ui = app.ui
        self.input = app.input
        self.base_path = app.base_path
        
        # Verify UI manager exists. If not (e.g. no platforms at all), initialize a dummy.
        if self.ui is None:
            # Create a minimal config if config has no platforms
            from config import SkinConfig
            dummy_skin = SkinConfig("", "")
            dummy_skin.config = {
                "romListDisplayAreaX1": 50,
                "romListDisplayAreaX2": app.config.screen_width - 50,
                "romListDisplayAreaY1": 100,
                "romListDisplayAreaY2": app.config.screen_height - 100,
                "romListDisplaySpacing": 30,
            }
            from ui import UIManager
            self.ui = UIManager(app.config, dummy_skin)
            app.ui = self.ui
        
        self.screen = self.ui.screen
        self.clock = self.ui.clock
        self.width = self.ui.screen_width
        self.height = self.ui.screen_height

    def run(self):
        """Main loop of the setup wizard."""
        # Make mouse visible during setup for easier debugging/use if needed
        pygame.mouse.set_visible(True)
        
        running = True
        selected_idx = 0
        
        while running:
            # Refresh platform diagnostics status
            platforms_status = []
            for p_def in self.app.config.platforms:
                issues = check_platform(self.base_path, p_def)
                errors = [i for i in issues if i.level == "error"]
                warns = [i for i in issues if i.level == "warn"]
                
                if errors:
                    status_text = "ERROR"
                    color = ERROR_COLOR
                elif warns:
                    status_text = "WARNING"
                    color = HIGHLIGHT_COLOR
                else:
                    status_text = "OK"
                    color = SUCCESS_COLOR
                
                platforms_status.append({
                    "def": p_def,
                    "status": status_text,
                    "color": color,
                    "issues": issues,
                })
            
            # Add an exit option
            menu_items = platforms_status + [{"def": None, "name": "Exit Setup Wizard", "status": "", "color": TEXT_COLOR}]
            
            # Handle input
            action = self.input.get_action()
            if action == self.input.ACTION_UP:
                selected_idx = (selected_idx - 1) % len(menu_items)
            elif action == self.input.ACTION_DOWN:
                selected_idx = (selected_idx + 1) % len(menu_items)
            elif action == self.input.ACTION_EXIT:
                running = False
            elif action == self.input.ACTION_RUN:
                item = menu_items[selected_idx]
                if item == menu_items[-1]: # Exit
                    running = False
                else:
                    self.configure_platform(item["def"])
            
            # Handle mouse click on menu items
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # Check if a menu item was clicked
                    start_y = 180
                    for idx, menu_item in enumerate(menu_items):
                        item_rect = pygame.Rect(self.width // 2 - 300, start_y + idx * 45 - 20, 600, 40)
                        if item_rect.collidepoint(mx, my):
                            selected_idx = idx
                            # Perform action
                            if menu_item == menu_items[-1]:
                                running = False
                            else:
                                self.configure_platform(menu_item["def"])
            
            # Draw Main Wizard Screen
            self.screen.fill(BG_COLOR)
            
            # Title Header
            title_font = self.ui.get_font(None, 48)
            sub_font = self.ui.get_font(None, 24)
            info_font = self.ui.get_font(None, 20)
            
            title_surf = title_font.render("MAMEly Setup Wizard", True, ACCENT_COLOR)
            self.screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 40))
            
            sub_surf = sub_font.render("Use ARROWS & ENTER to navigate, or click options with MOUSE. ESC to close.", True, MUTED_COLOR)
            self.screen.blit(sub_surf, (self.width // 2 - sub_surf.get_width() // 2, 100))
            
            # Draw platform items
            start_y = 180
            for idx, item in enumerate(menu_items):
                is_selected = (idx == selected_idx)
                item_color = HIGHLIGHT_COLOR if is_selected else TEXT_COLOR
                
                # Draw Card background if selected
                bg_rect = pygame.Rect(self.width // 2 - 350, start_y + idx * 45 - 18, 700, 36)
                if is_selected:
                    pygame.draw.rect(self.screen, CARD_COLOR, bg_rect, border_radius=6)
                    pygame.draw.rect(self.screen, ACCENT_COLOR, bg_rect, width=1, border_radius=6)
                
                if item == menu_items[-1]:
                    # Exit option
                    text_surf = sub_font.render(item["name"], True, item_color)
                    self.screen.blit(text_surf, (self.width // 2 - text_surf.get_width() // 2, start_y + idx * 45 - text_surf.get_height() // 2))
                else:
                    # Platform options
                    p_name = item["def"].name
                    status = item["status"]
                    status_color = item["color"]
                    
                    name_surf = sub_font.render(p_name, True, item_color)
                    status_surf = sub_font.render(f"[{status}]", True, status_color)
                    
                    self.screen.blit(name_surf, (self.width // 2 - 320, start_y + idx * 45 - name_surf.get_height() // 2))
                    self.screen.blit(status_surf, (self.width // 2 + 320 - status_surf.get_width(), start_y + idx * 45 - status_surf.get_height() // 2))
            
            # Bottom Info / Diagnostics panel for currently selected platform
            selected_item = menu_items[selected_idx]
            if selected_item != menu_items[-1]:
                info_box_rect = pygame.Rect(self.width // 2 - 350, self.height - 300, 700, 240)
                pygame.draw.rect(self.screen, CARD_COLOR, info_box_rect, border_radius=10)
                pygame.draw.rect(self.screen, BORDER_COLOR, info_box_rect, width=2, border_radius=10)
                
                p_def = selected_item["def"]
                p_path = os.path.join(self.base_path, "platforms", p_def.folder)
                p_conf = PlatformConfig(p_path, p_def.config_file)
                
                # Check ROMs & XML status
                roms_ok = os.path.isdir(p_conf.rom_directory) if p_conf.rom_directory else False
                xml_ok = os.path.isfile(os.path.join(p_path, "MAMEly.xml"))
                
                # Render Info
                y_offset = self.height - 280
                labels = [
                    f"Platform Folder:  {p_def.folder}",
                    f"Emulator Command: {p_conf.emulator_executable or '(not set)'}",
                    f"Emulator Base Path: {p_conf.emulator_base_path or '(not set)'}",
                    f"ROMs Folder:      {p_conf.rom_directory or '(not set)'} ({'OK' if roms_ok else 'NOT FOUND'})",
                    f"Database XML:     MAMEly.xml ({'OK' if xml_ok else 'MISSING'})"
                ]
                
                for label in labels:
                    lbl_surf = info_font.render(label, True, TEXT_COLOR)
                    self.screen.blit(lbl_surf, (self.width // 2 - 320, y_offset))
                    y_offset += 24
                
                # Show first error message if any
                errors = [i for i in selected_item["issues"] if i.level in ("error", "warn")]
                if errors:
                    err_lbl = info_font.render("Issue:", True, ERROR_COLOR)
                    self.screen.blit(err_lbl, (self.width // 2 - 320, y_offset + 10))
                    
                    err_msg = info_font.render(errors[0].message, True, TEXT_COLOR)
                    self.screen.blit(err_msg, (self.width // 2 - 250, y_offset + 10))
                    if errors[0].fix:
                        fix_msg = info_font.render(f"Fix: {errors[0].fix}", True, HIGHLIGHT_COLOR)
                        self.screen.blit(fix_msg, (self.width // 2 - 250, y_offset + 30))
            
            pygame.display.flip()
            self.clock.tick(60)
            
        pygame.mouse.set_visible(False)

    def configure_platform(self, platform_def):
        """Platform specific sub-configuration wizard screen."""
        p_path = os.path.join(self.base_path, "platforms", platform_def.folder)
        p_conf = PlatformConfig(p_path, platform_def.config_file)
        
        # Load local copies of config parameters so we can cancel/save
        config_data = {
            "emulator_executable": p_conf.emulator_executable,
            "emulator_base_path": p_conf.emulator_base_path,
            "rom_directory": p_conf.rom_directory,
            "rom_extension": p_conf.rom_extension,
            "rom_snap_directory": p_conf.rom_snap_directory,
        }
        
        running = True
        selected_idx = 0
        
        while running:
            # Evaluate field validity for visual feedback
            # Check executable
            exe_ok = False
            if config_data["emulator_executable"]:
                first_token = config_data["emulator_executable"].split()[0]
                if shutil.which(first_token) or os.path.exists(first_token) or "flatpak" in first_token:
                    exe_ok = True
                    
            # Check directories
            base_ok = os.path.isdir(config_data["emulator_base_path"]) if config_data["emulator_base_path"] else False
            rom_ok = os.path.isdir(config_data["rom_directory"]) if config_data["rom_directory"] else False
            snap_ok = os.path.isdir(config_data["rom_snap_directory"]) if config_data["rom_snap_directory"] else False
            xml_ok = os.path.isfile(os.path.join(p_path, "MAMEly.xml"))
            
            menu_items = [
                {"label": "Emulator Executable / Command", "value": config_data["emulator_executable"] or "(not set)", "ok": exe_ok, "key": "emulator_executable"},
                {"label": "Emulator Base Path", "value": config_data["emulator_base_path"] or "(not set)", "ok": base_ok, "key": "emulator_base_path", "browse": True},
                {"label": "ROMs Directory", "value": config_data["rom_directory"] or "(not set)", "ok": rom_ok, "key": "rom_directory", "browse": True},
                {"label": "ROM File Extension", "value": config_data["rom_extension"] or "(not set)", "ok": True, "key": "rom_extension"},
                {"label": "Snapshots Directory", "value": config_data["rom_snap_directory"] or "(not set)", "ok": snap_ok, "key": "rom_snap_directory", "browse": True},
                {"label": "Generate MAMEly.xml Database", "value": "MAMEly.xml exists" if xml_ok else "MISSING! Generate now", "ok": xml_ok, "action": "generate_xml"},
                {"label": "Save Changes & Return", "value": "", "ok": True, "action": "save"},
                {"label": "Discard Changes & Return", "value": "", "ok": True, "action": "cancel"},
            ]
            
            # Input
            action = self.input.get_action()
            if action == self.input.ACTION_UP:
                selected_idx = (selected_idx - 1) % len(menu_items)
            elif action == self.input.ACTION_DOWN:
                selected_idx = (selected_idx + 1) % len(menu_items)
            elif action == self.input.ACTION_EXIT:
                running = False # discard and exit
            elif action == self.input.ACTION_RUN:
                item = menu_items[selected_idx]
                if "key" in item:
                    # Select setting
                    val = config_data[item["key"]]
                    if item.get("browse"):
                        new_val = self.browse_folder(val or self.base_path)
                        if new_val:
                            config_data[item["key"]] = new_val
                    else:
                        # TextInput popup
                        if item["key"] == "emulator_executable":
                            new_val = self.select_emulator(platform_def.name, val)
                        else:
                            new_val = self.text_input(item["label"], val)
                        if new_val is not None:
                            config_data[item["key"]] = new_val
                elif item.get("action") == "generate_xml":
                    self.generate_xml(p_path, config_data["rom_directory"], config_data["rom_extension"])
                elif item.get("action") == "save":
                    # Write to config
                    p_conf.emulator_executable = config_data["emulator_executable"]
                    p_conf.emulator_base_path = config_data["emulator_base_path"]
                    p_conf.rom_directory = config_data["rom_directory"]
                    p_conf.rom_extension = config_data["rom_extension"]
                    p_conf.rom_snap_directory = config_data["rom_snap_directory"]
                    p_conf.save_config()
                    running = False
                elif item.get("action") == "cancel":
                    running = False
            
            # Mouse input
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    start_y = 150
                    for idx, menu_item in enumerate(menu_items):
                        item_rect = pygame.Rect(self.width // 2 - 400, start_y + idx * 55 - 20, 800, 48)
                        if item_rect.collidepoint(mx, my):
                            selected_idx = idx
                            # Trigger action
                            action = self.input.ACTION_RUN
                            # Feed key/action logic
                            if "key" in menu_item:
                                val = config_data[menu_item["key"]]
                                if menu_item.get("browse"):
                                    new_val = self.browse_folder(val or self.base_path)
                                    if new_val:
                                        config_data[menu_item["key"]] = new_val
                                else:
                                    if menu_item["key"] == "emulator_executable":
                                        new_val = self.select_emulator(platform_def.name, val)
                                    else:
                                        new_val = self.text_input(menu_item["label"], val)
                                    if new_val is not None:
                                        config_data[menu_item["key"]] = new_val
                            elif menu_item.get("action") == "generate_xml":
                                self.generate_xml(p_path, config_data["rom_directory"], config_data["rom_extension"])
                            elif menu_item.get("action") == "save":
                                p_conf.emulator_executable = config_data["emulator_executable"]
                                p_conf.emulator_base_path = config_data["emulator_base_path"]
                                p_conf.rom_directory = config_data["rom_directory"]
                                p_conf.rom_extension = config_data["rom_extension"]
                                p_conf.rom_snap_directory = config_data["rom_snap_directory"]
                                p_conf.save_config()
                                running = False
                            elif menu_item.get("action") == "cancel":
                                running = False
            
            # Draw Platform Config Screen
            self.screen.fill(BG_COLOR)
            
            title_font = self.ui.get_font(None, 40)
            lbl_font = self.ui.get_font(None, 24)
            val_font = self.ui.get_font(None, 20)
            
            title_surf = title_font.render(f"Configure: {platform_def.name}", True, ACCENT_COLOR)
            self.screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 40))
            
            start_y = 150
            for idx, item in enumerate(menu_items):
                is_selected = (idx == selected_idx)
                
                # Card highlight
                bg_rect = pygame.Rect(self.width // 2 - 420, start_y + idx * 55 - 24, 840, 48)
                if is_selected:
                    pygame.draw.rect(self.screen, CARD_COLOR, bg_rect, border_radius=6)
                    pygame.draw.rect(self.screen, ACCENT_COLOR, bg_rect, width=1, border_radius=6)
                
                # Get colors
                lbl_color = HIGHLIGHT_COLOR if is_selected else TEXT_COLOR
                val_color = SUCCESS_COLOR if item["ok"] else ERROR_COLOR
                if not item["value"]:
                    val_color = MUTED_COLOR
                
                # Render label
                lbl_surf = lbl_font.render(item["label"], True, lbl_color)
                self.screen.blit(lbl_surf, (self.width // 2 - 400, start_y + idx * 55 - 20))
                
                # Render value
                if item["value"]:
                    val_surf = val_font.render(item["value"], True, val_color)
                    self.screen.blit(val_surf, (self.width // 2 - 400, start_y + idx * 55 + 5))
            
            pygame.display.flip()
            self.clock.tick(60)

    def browse_folder(self, start_path):
        """Graphical folder browser."""
        if not start_path or not os.path.exists(start_path):
            start_path = self.base_path
            
        current_dir = os.path.abspath(start_path)
        if not os.path.isdir(current_dir):
            current_dir = os.path.dirname(current_dir)
            
        running = True
        selected_idx = 0
        
        while running:
            # Read folder contents (only folders)
            folders = [".."]
            try:
                for entry in sorted(os.listdir(current_dir)):
                    entry_path = os.path.join(current_dir, entry)
                    if os.path.isdir(entry_path) and not entry.startswith('.'):
                        folders.append(entry)
            except PermissionError:
                pass
                
            menu_items = ["[ SELECT CURRENT FOLDER ]"] + folders
            
            # Clamp index
            selected_idx = max(0, min(selected_idx, len(menu_items) - 1))
            
            # Input
            action = self.input.get_action()
            if action == self.input.ACTION_UP:
                selected_idx = (selected_idx - 1) % len(menu_items)
            elif action == self.input.ACTION_DOWN:
                selected_idx = (selected_idx + 1) % len(menu_items)
            elif action == self.input.ACTION_EXIT:
                return None  # Cancel
            elif action == self.input.ACTION_RUN:
                if selected_idx == 0:
                    # Select current dir
                    return current_dir
                else:
                    folder_name = menu_items[selected_idx]
                    if folder_name == "..":
                        current_dir = os.path.dirname(current_dir)
                    else:
                        current_dir = os.path.join(current_dir, folder_name)
                    selected_idx = 0  # Reset scroll on entering folder
            
            # Mouse click
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    start_y = 150
                    for idx, menu_item in enumerate(menu_items):
                        item_rect = pygame.Rect(self.width // 2 - 400, start_y + idx * 30 - 15, 800, 26)
                        if item_rect.collidepoint(mx, my):
                            selected_idx = idx
                            # Handle action
                            if selected_idx == 0:
                                return current_dir
                            else:
                                folder_name = menu_items[selected_idx]
                                if folder_name == "..":
                                    current_dir = os.path.dirname(current_dir)
                                else:
                                    current_dir = os.path.join(current_dir, folder_name)
                                selected_idx = 0

            # Draw Folder Browser Screen
            self.screen.fill(BG_COLOR)
            
            title_font = self.ui.get_font(None, 36)
            path_font = self.ui.get_font(None, 22)
            lbl_font = self.ui.get_font(None, 20)
            
            title_surf = title_font.render("Browse Folder", True, ACCENT_COLOR)
            self.screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 30))
            
            path_surf = path_font.render(f"Current Path: {current_dir}", True, MUTED_COLOR)
            self.screen.blit(path_surf, (self.width // 2 - path_surf.get_width() // 2, 75))
            
            # Show list of folders (with scroll support if there are too many)
            max_visible = (self.height - 200) // 30
            start_visible_idx = 0
            if selected_idx >= max_visible:
                start_visible_idx = selected_idx - max_visible + 1
                
            start_y = 150
            for idx in range(start_visible_idx, min(start_visible_idx + max_visible, len(menu_items))):
                item = menu_items[idx]
                draw_idx = idx - start_visible_idx
                is_selected = (idx == selected_idx)
                
                # Card highlight
                bg_rect = pygame.Rect(self.width // 2 - 410, start_y + draw_idx * 30 - 13, 820, 26)
                if is_selected:
                    pygame.draw.rect(self.screen, CARD_COLOR, bg_rect, border_radius=4)
                    pygame.draw.rect(self.screen, ACCENT_COLOR, bg_rect, width=1, border_radius=4)
                
                color = HIGHLIGHT_COLOR if is_selected else (SUCCESS_COLOR if idx == 0 else TEXT_COLOR)
                lbl_surf = lbl_font.render(item, True, color)
                self.screen.blit(lbl_surf, (self.width // 2 - 390, start_y + draw_idx * 30 - 10))
                
            pygame.display.flip()
            self.clock.tick(60)

    def select_emulator(self, platform_name, current_val):
        """Scans system for common emulators and presents list, plus text entry option."""
        # Common executables
        mapping = {
            "MAME": ["mame", "retroarch"],
            "Super Nintendo": ["snes9x-gtk", "snes9x", "retroarch", "flatpak run com.snes9x.Snes9x"],
            "Atari 2600": ["stella", "retroarch", "flatpak run org.stella.Stella"],
            "Nintendo 64": ["mupen64plus", "retroarch", "flatpak run io.github.mupen64plus.mupen64plus"],
        }
        
        candidates = mapping.get(platform_name, ["retroarch"])
        found_options = []
        
        # Check standard emulators
        for cmd in candidates:
            if cmd.startswith("flatpak"):
                if shutil.which("flatpak"):
                    found_options.append(cmd)
            else:
                first_token = cmd.split()[0]
                if shutil.which(first_token):
                    found_options.append(cmd)
                    
        menu_items = []
        for cmd in found_options:
            menu_items.append({"label": f"Use found: {cmd}", "value": cmd})
        
        menu_items.append({"label": "Enter Custom Executable / Command...", "value": "custom"})
        menu_items.append({"label": "Keep Current: " + (current_val or "(not set)"), "value": "current"})
        
        selected_idx = 0
        running = True
        
        while running:
            # Input
            action = self.input.get_action()
            if action == self.input.ACTION_UP:
                selected_idx = (selected_idx - 1) % len(menu_items)
            elif action == self.input.ACTION_DOWN:
                selected_idx = (selected_idx + 1) % len(menu_items)
            elif action == self.input.ACTION_EXIT:
                return None
            elif action == self.input.ACTION_RUN:
                item = menu_items[selected_idx]
                if item["value"] == "custom":
                    return self.text_input("Enter Emulator Command", current_val)
                elif item["value"] == "current":
                    return current_val
                else:
                    return item["value"]
            
            # Mouse click
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    start_y = 200
                    for idx, menu_item in enumerate(menu_items):
                        item_rect = pygame.Rect(self.width // 2 - 350, start_y + idx * 50 - 20, 700, 40)
                        if item_rect.collidepoint(mx, my):
                            selected_idx = idx
                            # Action
                            item = menu_items[selected_idx]
                            if item["value"] == "custom":
                                return self.text_input("Enter Emulator Command", current_val)
                            elif item["value"] == "current":
                                return current_val
                            else:
                                return item["value"]
            
            # Draw
            self.screen.fill(BG_COLOR)
            title_font = self.ui.get_font(None, 36)
            lbl_font = self.ui.get_font(None, 22)
            
            title_surf = title_font.render("Select Emulator Executable", True, ACCENT_COLOR)
            self.screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 50))
            
            start_y = 200
            for idx, item in enumerate(menu_items):
                is_selected = (idx == selected_idx)
                
                bg_rect = pygame.Rect(self.width // 2 - 370, start_y + idx * 50 - 20, 740, 40)
                if is_selected:
                    pygame.draw.rect(self.screen, CARD_COLOR, bg_rect, border_radius=6)
                    pygame.draw.rect(self.screen, ACCENT_COLOR, bg_rect, width=1, border_radius=6)
                
                color = HIGHLIGHT_COLOR if is_selected else TEXT_COLOR
                lbl_surf = lbl_font.render(item["label"], True, color)
                self.screen.blit(lbl_surf, (self.width // 2 - 350, start_y + idx * 50 - lbl_surf.get_height() // 2))
                
            pygame.display.flip()
            self.clock.tick(60)

    def text_input(self, title, current_val):
        """Displays dialog prompting user to enter text using keyboard."""
        user_text = current_val or ""
        running = True
        
        # Enable key repeat for text typing
        pygame.key.set_repeat(300, 50)
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        pygame.key.set_repeat(0, 0)
                        return user_text
                    elif event.key == pygame.K_ESCAPE:
                        pygame.key.set_repeat(0, 0)
                        return None
                    elif event.key == pygame.K_BACKSPACE:
                        user_text = user_text[:-1]
                    else:
                        if event.unicode and ord(event.unicode) >= 32:
                            user_text += event.unicode
            
            # Draw
            self.screen.fill(BG_COLOR)
            
            title_font = self.ui.get_font(None, 36)
            lbl_font = self.ui.get_font(None, 22)
            input_font = self.ui.get_font(None, 26)
            
            title_surf = title_font.render(title, True, ACCENT_COLOR)
            self.screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 100))
            
            prompt_surf = lbl_font.render("Type using keyboard. Enter to Save, ESC to Cancel.", True, MUTED_COLOR)
            self.screen.blit(prompt_surf, (self.width // 2 - prompt_surf.get_width() // 2, 150))
            
            # Draw Text box
            box_rect = pygame.Rect(self.width // 2 - 400, 250, 800, 60)
            pygame.draw.rect(self.screen, CARD_COLOR, box_rect, border_radius=8)
            pygame.draw.rect(self.screen, BORDER_COLOR, box_rect, width=2, border_radius=8)
            
            # Blinking cursor
            cursor = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
            display_str = user_text + cursor
            
            input_surf = input_font.render(display_str, True, HIGHLIGHT_COLOR)
            self.screen.blit(input_surf, (self.width // 2 - 380, 280 - input_surf.get_height() // 2))
            
            pygame.display.flip()
            self.clock.tick(60)

    def generate_xml(self, platform_path, rom_dir, rom_ext):
        """Scans ROMs folder and compiles new MAMEly.xml database."""
        if not rom_dir or not os.path.exists(rom_dir):
            # Error modal
            self.show_error_modal("ROM Directory not valid or doesn't exist.")
            return
            
        xml_path = os.path.join(platform_path, "MAMEly.xml")
        
        # Load progress screen
        self.screen.fill(BG_COLOR)
        title_font = self.ui.get_font(None, 30)
        title_surf = title_font.render("Scanning ROMs & Generating Database...", True, HIGHLIGHT_COLOR)
        self.screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, self.height // 2 - 50))
        pygame.display.flip()
        
        # Scan roms
        rom_files = []
        try:
            for entry in os.scandir(rom_dir):
                if entry.is_file() and (not rom_ext or entry.name.endswith(rom_ext)):
                    rom_files.append(entry.name)
        except Exception as e:
            self.show_error_modal(f"Error scanning folder: {e}")
            return
            
        if not rom_files:
            self.show_error_modal(f"No files matching '{rom_ext}' extension found.")
            return
            
        # Write XML
        tmp_path = xml_path + ".tmp"
        try:
            with open(tmp_path, "w") as f:
                f.write('<?xml version="1.0"?>\n')
                f.write('<menu>\n')
                f.write('  <header>\n')
                f.write('    <listname>MAMEly</listname>\n')
                f.write(f'    <lastlistupdate>{datetime.datetime.now()}</lastlistupdate>\n')
                f.write('    <listgeneratorversion>MAMEly Setup Wizard v1.0</listgeneratorversion>\n')
                f.write('  </header>\n')
                
                for r_file in sorted(rom_files):
                    desc = make_description(r_file, rom_ext)
                    f.write(f'  <game name="{r_file}">\n')
                    f.write(f'     <description>{desc}</description>\n')
                    f.write('     <genre>General</genre>\n')
                    f.write('     <rating>Rating: General</rating>\n')
                    f.write('     <favorite>0</favorite>\n')
                    f.write('     <ignore>0</ignore>\n')
                    f.write('  </game>\n')
                    
                f.write('</menu>\n')
                
            if os.path.exists(xml_path):
                if os.path.exists(xml_path + ".old"):
                    os.remove(xml_path + ".old")
                os.rename(xml_path, xml_path + ".old")
            os.rename(tmp_path, xml_path)
            
            # Show success modal
            self.show_success_modal(f"Generated MAMEly.xml successfully! ({len(rom_files)} games)")
        except Exception as e:
            self.show_error_modal(f"Failed to write XML: {e}")

    def show_error_modal(self, message):
        """Displays error modal."""
        self.show_modal("Error", message, ERROR_COLOR)

    def show_success_modal(self, message):
        """Displays success modal."""
        self.show_modal("Success", message, SUCCESS_COLOR)

    def show_modal(self, title, message, color):
        """Helper to render a simple alert box."""
        running = True
        while running:
            # Event poll to clear queue
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    running = False
                    
            # Draw overlay
            overlay = pygame.Surface((self.width, self.height))
            overlay.set_alpha(150)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, (0, 0))
            
            cx, cy = self.width // 2, self.height // 2
            
            pygame.draw.rect(self.screen, CARD_COLOR, (cx - 300, cy - 100, 600, 200), border_radius=10)
            pygame.draw.rect(self.screen, color, (cx - 300, cy - 100, 600, 200), width=2, border_radius=10)
            
            title_font = self.ui.get_font(None, 32)
            msg_font = self.ui.get_font(None, 20)
            btn_font = self.ui.get_font(None, 18)
            
            t_surf = title_font.render(title, True, color)
            self.screen.blit(t_surf, (cx - t_surf.get_width() // 2, cy - 70))
            
            # Handle wrapping for message if needed
            words = message.split()
            lines = []
            current_line = []
            for word in words:
                current_line.append(word)
                test_str = " ".join(current_line)
                if msg_font.size(test_str)[0] > 540:
                    current_line.pop()
                    lines.append(" ".join(current_line))
                    current_line = [word]
            lines.append(" ".join(current_line))
            
            y_offset = cy - 20
            for line in lines:
                m_surf = msg_font.render(line, True, TEXT_COLOR)
                self.screen.blit(m_surf, (cx - m_surf.get_width() // 2, y_offset))
                y_offset += 22
                
            b_surf = btn_font.render("Press any key or click to close", True, MUTED_COLOR)
            self.screen.blit(b_surf, (cx - b_surf.get_width() // 2, cy + 60))
            
            pygame.display.flip()
            self.clock.tick(60)
