import os
import xml.etree.ElementTree as ET

def hex_to_color(color_hex):
    """Convert hex string (e.g., 'RRGGBB') to RGB tuple."""
    try:
        if color_hex.startswith('0x'):
            color_hex = color_hex[2:]
        elif color_hex.startswith('#'):
            color_hex = color_hex[1:]
            
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)
        return (r, g, b)
    except Exception:
        return (128, 128, 128)

class Platform:
    def __init__(self, name, folder, config_file, skin_file):
        self.name = name
        self.folder = folder
        self.config_file = config_file
        self.skin_file = skin_file

class Config:
    def __init__(self, base_path, config_file="config.xml"):
        self.base_path = base_path
        self.config_file = config_file
        self.screen_width = 800
        self.screen_height = 600
        self.platforms = []
        self.load_main_config()

    def load_main_config(self):
        config_path = os.path.join(self.base_path, self.config_file)
        print(f"Loading main config from: {config_path}")
        if not os.path.exists(config_path):
            print(f"Config file not found: {config_path}")
            self.generate_default_config()
            if not os.path.exists(config_path):
                return

        try:
            tree = ET.parse(config_path)
            root = tree.getroot()

            for child in root:
                if child.tag == "screensize":
                    self.screen_width = int(child.attrib.get("screenX", 800))
                    self.screen_height = int(child.attrib.get("screenY", 600))
                
                if child.tag == "platform":
                    name = child.attrib.get('name')
                    folder = ""
                    config = ""
                    skin = ""
                    
                    for grandchild in child:
                        if grandchild.tag == "folder":
                            folder = grandchild.text
                        if grandchild.tag == "config":
                            config = grandchild.text
                        if grandchild.tag == "skin":
                            skin = grandchild.text
                            
                    if name and folder and config and skin:
                        self.platforms.append(Platform(name, folder, config, skin))
                        
        except ET.ParseError as e:
            print(f"Error parsing config.xml: {e}")

    def generate_default_config(self):
        config_path = os.path.join(self.base_path, self.config_file)
        platforms_dir = os.path.join(self.base_path, "platforms")
        found_platforms = []
        if os.path.exists(platforms_dir):
            for d in sorted(os.listdir(platforms_dir)):
                d_path = os.path.join(platforms_dir, d)
                if os.path.isdir(d_path):
                    config_file = None
                    skin_file = None
                    for f in os.listdir(d_path):
                        if f.endswith(".txt") and not f.startswith("_"):
                            config_file = f
                        elif f.endswith(".skin") and (skin_file is None or "synthwave" in f):
                            skin_file = f
                    if not config_file:
                        config_file = f"platform_{d}.txt"
                    if not skin_file:
                        skin_file = f"synthwave_1920x1080.skin"
                    
                    # Convert platform folder name to friendly name
                    friendly_name = d
                    if d == "ATARI2600":
                        friendly_name = "Atari 2600"
                    elif d == "SNES":
                        friendly_name = "Super Nintendo"
                    elif d == "N64":
                        friendly_name = "Nintendo 64"
                    found_platforms.append((friendly_name, d, config_file, skin_file))
        
        with open(config_path, "w") as f:
            f.write('<?xml version="1.0"?>\n')
            f.write('<platforms>\n')
            f.write('    <screensize screenX="1920" screenY="1080"/>\n')
            for name, folder, config_f, skin_f in found_platforms:
                f.write(f'    <platform name="{name}">\n')
                f.write(f'        <folder>{folder}</folder>\n')
                f.write(f'        <config>{config_f}</config>\n')
                f.write(f'        <skin>{skin_f}</skin>\n')
                f.write('    </platform>\n')
            f.write('</platforms>\n')
        print(f"Generated default main config at: {config_path}")

    def save_main_config(self):
        config_path = os.path.join(self.base_path, self.config_file)
        try:
            with open(config_path, "w") as f:
                f.write('<?xml version="1.0"?>\n')
                f.write('<platforms>\n')
                f.write(f'    <screensize screenX="{self.screen_width}" screenY="{self.screen_height}"/>\n')
                for p in self.platforms:
                    f.write(f'    <platform name="{p.name}">\n')
                    f.write(f'        <folder>{p.folder}</folder>\n')
                    f.write(f'        <config>{p.config_file}</config>\n')
                    f.write(f'        <skin>{p.skin_file}</skin>\n')
                    f.write('    </platform>\n')
                f.write('</platforms>\n')
            print(f"Saved main config to: {config_path}")
        except Exception as e:
            print(f"Error saving main config: {e}")


class PlatformConfig:
    def __init__(self, platform_path, config_file):
        self.platform_path = platform_path
        self.config_file = config_file
        
        # Defaults
        self.emulator_executable = ""
        self.rom_extension = ".zip"
        self.snap_extension = ".png"
        self.emulator_base_path = ""
        self.rom_snap_directory = ""
        self.rom_video_directory = "video/"
        self.video_extension = ".mp4"
        self.rom_directory = ""
        self.mamely_xml_path = ""
        self.favorites_directory = ""
        self.show_xml_progress_bar = False
        self.compare_xml_to_roms = False
        self.emulator_default_flags = ""
        
        self.load_config()

    def load_config(self):
        full_path = os.path.join(self.platform_path, self.config_file)
        print(f"Loading platform config from: {full_path}")
        if not os.path.exists(full_path):
            print(f"Platform config not found: {full_path}")
            return

        try:
            with open(full_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        var, val = line.split("=", 1)
                        var = var.strip()
                        val = val.strip()

                        # Sanitize Paths
                        if "/home/" in val or "~" in val:
                             current_home = os.path.expanduser("~")
                             # Replace any /home/username/ with current user home dynamically
                             import re
                             val = re.sub(r'^/home/[^/]+', current_home, val)
                             val = re.sub(r'(?<=\s)/home/[^/]+', current_home, val)
                             if val.startswith("~"):
                                 val = os.path.expanduser(val)
                        
                        if var == "emulatorExecutable":
                            self.emulator_executable = val
                        elif var == "romExtension":
                            self.rom_extension = val
                        elif var == "snapExtension":
                            self.snap_extension = val
                        elif var == "emulatorBasePath":
                            self.emulator_base_path = val
                        elif var == "romSnapDirectory":
                            self.rom_snap_directory = val
                        elif var == "romVideoDirectory":
                            self.rom_video_directory = val
                        elif var == "videoExtension":
                            self.video_extension = val
                        elif var == "romDirectory":
                            self.rom_directory = val
                        elif var == "MAMElyxmlPath":
                            self.mamely_xml_path = val
                        elif var == "favoritesDirectory":
                            self.favorites_directory = val
                        elif var == "showXMLprogressBar":
                            self.show_xml_progress_bar = (val == "True")
                        elif var == "compareXMLtoRoms":
                            self.compare_xml_to_roms = (val == "True")
                        elif var == "emulatorDefaultFlags":
                            self.emulator_default_flags = val
                            
            # Path normalization
            if self.rom_snap_directory and not self.rom_snap_directory.startswith("/"):
                self.rom_snap_directory = os.path.join(self.emulator_base_path, self.rom_snap_directory)
            if self.rom_video_directory and not self.rom_video_directory.startswith("/"):
                self.rom_video_directory = os.path.join(self.emulator_base_path, self.rom_video_directory)
            if self.rom_directory and not self.rom_directory.startswith("/"):
                self.rom_directory = os.path.join(self.emulator_base_path, self.rom_directory)
                            
        except Exception as e:
            print(f"Error reading platform config: {e}")

    def save_config(self):
        full_path = os.path.join(self.platform_path, self.config_file)
        lines = []
        existing_vars = {}
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("#") or not stripped:
                        lines.append(line)
                    elif "=" in stripped:
                        var, _ = stripped.split("=", 1)
                        var = var.strip()
                        existing_vars[var] = len(lines)
                        lines.append(line)
                    else:
                        lines.append(line)

        # Before writing, let's make paths relative if they are subpaths of emulator_base_path
        save_rom_dir = self.rom_directory
        save_snap_dir = self.rom_snap_directory
        save_video_dir = self.rom_video_directory
        
        base_path = self.emulator_base_path
        if base_path:
            # If absolute paths start with base_path, make them relative
            if save_rom_dir and os.path.isabs(save_rom_dir) and save_rom_dir.startswith(base_path):
                save_rom_dir = os.path.relpath(save_rom_dir, base_path)
            if save_snap_dir and os.path.isabs(save_snap_dir) and save_snap_dir.startswith(base_path):
                save_snap_dir = os.path.relpath(save_snap_dir, base_path)
            if save_video_dir and os.path.isabs(save_video_dir) and save_video_dir.startswith(base_path):
                save_video_dir = os.path.relpath(save_video_dir, base_path)

        # Convert absolute home paths to tildes (~) so it's clean and portable in Git
        home_dir = os.path.expanduser("~")
        save_base_path = self.emulator_base_path
        if save_base_path and save_base_path.startswith(home_dir):
            save_base_path = "~" + save_base_path[len(home_dir):]
            
        save_exe = self.emulator_executable
        if save_exe and home_dir in save_exe:
            save_exe = save_exe.replace(home_dir, "~")

        settings = {
            "emulatorExecutable": save_exe,
            "romExtension": self.rom_extension,
            "snapExtension": self.snap_extension,
            "emulatorBasePath": save_base_path,
            "romSnapDirectory": save_snap_dir,
            "romVideoDirectory": save_video_dir,
            "videoExtension": self.video_extension,
            "romDirectory": save_rom_dir,
            "MAMElyxmlPath": self.mamely_xml_path,
            "favoritesDirectory": self.favorites_directory,
            "showXMLprogressBar": str(self.show_xml_progress_bar),
            "compareXMLtoRoms": str(self.compare_xml_to_roms),
            "emulatorDefaultFlags": self.emulator_default_flags,
        }

        for var, val in settings.items():
            if var in existing_vars:
                idx = existing_vars[var]
                lines[idx] = f"{var} = {val}\n"
            else:
                lines.append(f"{var} = {val}\n")

        with open(full_path, "w") as f:
            f.writelines(lines)
        print(f"Saved platform config to: {full_path}")

DEFAULT_SKIN_COLORS = {
    "defaultFontForegroundColor": (255, 255, 255),
    "defaultHighlightFontForegroundColor": (255, 255, 0),
    "defaultRomNameDisplayLineShadowColor": (0, 0, 0),
    "defaultRomNameDisplayLineHighlightShadowColor": (119, 119, 119),
    "defaultRomNameDisplayBoxShadowColor": (0, 0, 0),
    "defaultRomNameDisplayBoxColor": (255, 255, 255),
    "defaultTitleBarColor": (255, 255, 255),
    "defaultTitleBarShadowColor": (0, 0, 0),
    "defaultRomCountColor": (255, 255, 255),
    "defaultRomCountShadowColor": (0, 0, 0),
    "defaultMessageColor": (255, 255, 0),
    "defaultGameSetBarColor": (255, 255, 255),
    "defaultGameSetBarShadowColor": (0, 0, 0),
    "defaultRomGenreColor": (255, 255, 255),
    "defaultRomGenreShadowColor": (0, 0, 0),
    "defaultRomRatingColor": (255, 255, 255),
    "defaultRomRatingShadowColor": (0, 0, 0),
    "defaultRomFileNameColor": (255, 255, 255),
    "defaultRomFileNameShadowColor": (0, 0, 0),
}


class SkinConfig:
    def __init__(self, platform_path, skin_file):
        self.platform_path = platform_path
        self.skin_file = skin_file
        self.config = {}
        self.load_skin()

    def load_skin(self):
        full_path = os.path.join(self.platform_path, self.skin_file)
        print(f"Loading skin config from: {full_path}")
        if not os.path.exists(full_path):
            print(f"Skin file not found: {full_path}")
            return

        try:
            with open(full_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        var, val = line.split("=", 1)
                        var = var.strip()
                        val = val.strip()
                        
                        # Store everything in a dict for flexibility
                        if "Color" in var:
                            self.config[var] = hex_to_color(val)
                        elif any(x in var for x in ["X1", "Y1", "X2", "Y2", "Size", "Len", "Offset", "Time", "Spacing"]):
                             try:
                                  self.config[var] = int(val)
                             except ValueError:
                                  self.config[var] = val
                        elif val == "True":
                            self.config[var] = True
                        elif val == "False":
                            self.config[var] = False
                        else:
                            self.config[var] = val
        except Exception as e:
            print(f"Error reading skin config: {e}")

        # Calculate Derived Values (mimicking MAMEly.py logic)
        try:
             # ROM List
             x1 = self.config.get("romListDisplayAreaX1", 0)
             x2 = self.config.get("romListDisplayAreaX2", 0)
             y1 = self.config.get("romListDisplayAreaY1", 0)
             y2 = self.config.get("romListDisplayAreaY2", 0)
             self.config["romListDisplayAreaXCenter"] = x1 + (x2 - x1) // 2
             self.config["romListDisplayAreaYCenter"] = y1 + (y2 - y1) // 2
             
             # Genre
             x1 = self.config.get("romGenreX1", 0)
             x2 = self.config.get("romGenreX2", 0)
             y1 = self.config.get("romGenreY1", 0)
             y2 = self.config.get("romGenreY2", 0)
             self.config["romGenreXCenter"] = x1 + (x2 - x1) // 2
             self.config["romGenreYCenter"] = y1 + (y2 - y1) // 2
             
             # Rating
             if "romRatingX1" in self.config:
                 rx1 = self.config.get("romRatingX1", 0)
                 rx2 = self.config.get("romRatingX2", 0)
                 ry1 = self.config.get("romRatingY1", 0)
                 ry2 = self.config.get("romRatingY2", 0)
                 self.config["romRatingXCenter"] = rx1 + (rx2 - rx1) // 2
                 self.config["romRatingYCenter"] = ry1 + (ry2 - ry1) // 2
                 self.config["romGenreYCenter_effective"] = self.config["romGenreYCenter"]
             else:
                 # Legacy fallback: derive romRating coordinates from romGenre + genreRatingOffset
                 self.config["romRatingX1"] = x1
                 self.config["romRatingX2"] = x2
                 self.config["romRatingY1"] = y1
                 self.config["romRatingY2"] = y2
                 self.config["romRatingXCenter"] = self.config["romGenreXCenter"]
                 offset = self.config.get("genreRatingOffset", 20)
                 self.config["romGenreYCenter_effective"] = self.config["romGenreYCenter"] - offset
                 self.config["romRatingYCenter"] = self.config["romGenreYCenter"] + offset
             
             # File Name Box
             x1 = self.config.get("romFileNameDisplayBoxX1", 0)
             x2 = self.config.get("romFileNameDisplayBoxX2", 0)
             y1 = self.config.get("romFileNameDisplayBoxY1", 0)
             y2 = self.config.get("romFileNameDisplayBoxY2", 0)
             self.config["romFileNameDisplayBoxXCenter"] = x1 + (x2 - x1) // 2
             self.config["romFileNameDisplayBoxYCenter"] = y1 + (y2 - y1) // 2

             # Genre Set
             x1 = self.config.get("genreSetX1", 0)
             x2 = self.config.get("genreSetX2", 0)
             y1 = self.config.get("genreSetY1", 0)
             y2 = self.config.get("genreSetY2", 0)
             self.config["genreSetXCenter"] = x1 + (x2 - x1) // 2
             self.config["genreSetYCenter"] = y1 + (y2 - y1) // 2
             
             # ROM Snap
             x1 = self.config.get("romSnapX1", 0)
             x2 = self.config.get("romSnapX2", 0)
             y1 = self.config.get("romSnapY1", 0)
             y2 = self.config.get("romSnapY2", 0)
             self.config["romSnapXCenter"] = x1 + (x2 - x1) // 2
             self.config["romSnapYCenter"] = y1 + (y2 - y1) // 2
             self.config["maxRomSnapWidth"] = x2 - x1
             self.config["maxRomSnapHeight"] = y2 - y1

             # ROM Count
             x1 = self.config.get("romCountX1", 0)
             x2 = self.config.get("romCountX2", 0)
             y1 = self.config.get("romCountY1", 0)
             y2 = self.config.get("romCountY2", 0)
             self.config["romCountXCenter"] = x1 + (x2 - x1) // 2
             self.config["romCountYCenter"] = y1 + (y2 - y1) // 2
             
        except Exception as e:
            print(f"Error calculating derived skin values: {e}")

    def get(self, key, default=None):
        if key in self.config:
            return self.config[key]
        if default is not None:
            return default
        if key in DEFAULT_SKIN_COLORS:
            return DEFAULT_SKIN_COLORS[key]
        return None
