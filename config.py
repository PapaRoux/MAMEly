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
        self.rom_directory = ""
        self.mamely_xml_path = ""
        self.favorites_directory = ""
        self.show_xml_progress_bar = False
        self.compare_xml_to_roms = False
        
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
                             # Replace /home/rossi/ or similar with current user home
                             current_home = os.path.expanduser("~")
                             if "/home/rossi/" in val:
                                 val = val.replace("/home/rossi/", current_home + "/")
                             elif val.startswith("~"):
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
                            
            # Path normalization
            if self.rom_snap_directory and not self.rom_snap_directory.startswith("/"):
                self.rom_snap_directory = os.path.join(self.emulator_base_path, self.rom_snap_directory)
            if self.rom_directory and not self.rom_directory.startswith("/"):
                self.rom_directory = os.path.join(self.emulator_base_path, self.rom_directory)
                            
        except Exception as e:
            print(f"Error reading platform config: {e}")

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
        return self.config.get(key, default)
