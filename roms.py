import os
import xml.etree.ElementTree as ET
import datetime
import operator

class Rom:
    def __init__(self, name, description, genre, rating, favorite=0, ignore=0):
        self.name = name
        self.description = description
        self.genre = genre
        self.rating = rating
        self.favorite = int(favorite)
        self.ignore = int(ignore)

class RomManager:
    def __init__(self, platform_path, platform_config):
        self.platform_path = platform_path
        self.config = platform_config
        self.roms = {}  # Dictionary of name -> Rom object
        self.genres = set()
        self.ratings = set()
        
        # Lists for special filtering
        self.skip_genres = set()
        self.skip_ratings = set()
        self.flag_options = {}

    def load_skips_and_flags(self):
        """Load skip lists and run flags from files."""
        # Flags
        try:
            flag_path = os.path.join(self.platform_path, "_flags.txt")
            if os.path.exists(flag_path):
                with open(flag_path, "r") as f:
                    for line in f:
                        if "#" not in line and "=" in line:
                            parts = line.split("=", 1)
                            self.flag_options[parts[0].strip()] = parts[1].strip()
        except Exception:
            pass

        # Skip Genre
        try:
            skip_gen_path = os.path.join(self.platform_path, "_skipGenre.txt")
            if os.path.exists(skip_gen_path):
                with open(skip_gen_path, "r") as f:
                    for line in f:
                        if "#" not in line:
                            self.skip_genres.add(line.strip())
        except Exception:
            pass

        # Skip Rating
        try:
            skip_rat_path = os.path.join(self.platform_path, "_skipRating.txt")
            if os.path.exists(skip_rat_path):
                with open(skip_rat_path, "r") as f:
                    for line in f:
                        if "#" not in line:
                            self.skip_ratings.add(line.strip())
        except Exception:
            pass

    def load_roms(self, callback_progress=None):
        """Load ROMs from XML and optional file system check."""
        import time
        t_start = time.time()
        print(f"[{time.time()}] Starting Game Load...")
        
        xml_path = os.path.join(self.platform_path, "MAMEly.xml")
        xml_roms = {}
        
        if os.path.exists(xml_path):
            try:
                print(f"[{time.time()}] Parsing XML: {xml_path}")
                tree = ET.parse(xml_path)
                root = tree.getroot()
                children = list(root)
                total_nodes = len(children)
                
                print(f"[{time.time()}] Processing {total_nodes} XML nodes...")
                
                for i, child in enumerate(children):
                    if child.tag == "game":
                        name = child.attrib.get('name')
                        description = ""
                        genre = "General"
                        rating = "General"
                        favorite = 0
                        ignore = 0
                        
                        for grandchild in child:
                            if grandchild.tag == "description":
                                description = grandchild.text.title() if grandchild.text else ""
                            elif grandchild.tag == "genre":
                                genre = grandchild.text.title() if grandchild.text else "General"
                                if "/" in genre:
                                    genre = genre.split("/")[0].strip()
                            elif grandchild.tag == "rating":
                                rating = grandchild.text if grandchild.text else "General"
                            elif grandchild.tag == "favorite":
                                try:
                                    favorite = int(grandchild.text)
                                except:
                                    favorite = 0
                            elif grandchild.tag == "ignore":
                                try:
                                    ignore = int(grandchild.text)
                                except:
                                    ignore = 0
                                    
                        # Filtering Logic
                        if genre in self.skip_genres:
                            continue
                        if "Ttl -" in genre: # Hardcoded skip from original
                            continue
                        if rating in self.skip_ratings:
                            continue
                            
                        # Store ROM
                        rom_obj = Rom(name, description, genre, rating, favorite, ignore)
                        xml_roms[name] = rom_obj
                        
                        if genre != "General":
                            self.genres.add(genre)
                        if rating != "General":
                            self.ratings.add(rating)
                            
                    if callback_progress:
                         callback_progress((i + 1) / total_nodes * 100)
            except ET.ParseError as e:
                print(f"XML Parse Error: {e}")
        
        print(f"[{time.time()}] XML Processing Complete. Found {len(xml_roms)} potential games.")

        # Directory Comparison Logic
        if self.config.compare_xml_to_roms:
            print(f"[{time.time()}] Scanning ROM Directory: {self.config.rom_directory}")
            self.roms = {}
            if os.path.exists(self.config.rom_directory):
                print(f"[{time.time()}] Starting Directory Scan using os.scandir (Optimized)...")
                
                count = 0
                with os.scandir(self.config.rom_directory) as it:
                    for entry in it:
                        # entry.is_file() uses cached stat info from the directory listing if available
                        if entry.is_file():
                            f = entry.name
                            
                            # Strip extension
                            base_name = f
                            if self.config.rom_extension in f:
                                base_name = f.replace(self.config.rom_extension, "")
                            
                            # Find in XML dict
                            if base_name in xml_roms:
                                 self.roms[base_name] = xml_roms[base_name]
                            elif f in xml_roms: # Try with extension if needed
                                 self.roms[f] = xml_roms[f]
                                 
                            count += 1
                            if count % 1000 == 0:
                                print(f"[{time.time()}] Scanned {count} files...")
                                
            print(f"[{time.time()}] Directory Scan Complete. Processed {count} files.")
        else:
            print(f"[{time.time()}] Skipping ROM directory scan (compareXMLtoRoms=False). using XML list directly.")
            self.roms = xml_roms

        print(f"[{time.time()}] Load Complete. Total Loading Time: {time.time() - t_start:.2f}s")

    def save_xml(self):
        """Dump current ROM list to XML."""
        xml_path = os.path.join(self.platform_path, "MAMEly.xml")
        tmp_path = xml_path + ".tmp"
        
        try:
            with open(tmp_path, "w") as f, \
                 open(os.path.join(self.platform_path, "favorites.txt"), "w") as f_fav, \
                 open(os.path.join(self.platform_path, "ignore.txt"), "w") as f_ign:
                
                f.write("<?xml version=\"1.0\"?>\n")
                f.write("<menu>\n")
                f.write("  <header>\n")
                f.write("    <listname>MAMEly</listname>\n")
                f.write(f"    <lastlistupdate>{datetime.datetime.now()}</lastlistupdate>\n")
                f.write("    <listgeneratorversion>MAMEly Refactored</listgeneratorversion>\n")
                f.write("  </header>\n")
                
                count = 0
                for rom in self.roms.values():
                    if rom.name:
                        f.write(f"  <game name=\"{rom.name}\">\n")
                        f.write(f"     <description>{rom.description}</description>\n")
                        f.write(f"     <genre>{rom.genre}</genre>\n")
                        f.write(f"     <rating>{rom.rating}</rating>\n")
                        f.write(f"     <favorite>{rom.favorite}</favorite>\n")
                        f.write(f"     <ignore>{rom.ignore}</ignore>\n")
                        f.write("  </game>\n")
                        
                        if rom.favorite == 1:
                            f_fav.write(f"{rom.name}\n")
                        if rom.ignore == 1:
                            f_ign.write(f"{rom.name}\n")
                        count += 1
                
                f.write("</menu>\n")

            # Rename if successful
            if os.path.exists(xml_path):
                os.rename(xml_path, xml_path + ".old")
            os.rename(tmp_path, xml_path)
            
        except Exception as e:
            print(f"Error saving XML: {e}")

    def get_genre_list(self):
        """Return sorted list of genres including special categories."""
        genre_list = sorted(list(self.genres))
        # Logic to handle ratings if they were mixed in genres in original
        # The original prefixed ratings with "__" to sort them at the end.
        # Here we can just append them sorted if we want to mimic that behavior
        # or just return proper lists. 
        # Original logic: lines 819-833 MAMEly.py
        
        # Let's just return what they had for now, but formatted nicely
        full_list = ["All Games", "Favorites"] + genre_list + ["Ignore"]
        return full_list

    def get_roms_by_genre(self, genre_name):
        """Return filtered list of ROMs for a given genre category."""
        results = []
        
        # Sort by description
        sorted_roms = sorted(self.roms.values(), key=operator.attrgetter('description'))
        
        for rom in sorted_roms:
            if genre_name == "All Games":
                if rom.ignore == 0:
                    results.append(rom)
            elif genre_name == "Favorites":
                if rom.favorite == 1:
                    results.append(rom)
            elif genre_name == "Ignore":
                if rom.ignore == 1:
                    results.append(rom)
            else:
                if rom.genre == genre_name and rom.ignore == 0:
                    results.append(rom)
                    
        return results

    def toggle_favorite(self, rom_name):
        if rom_name in self.roms:
            self.roms[rom_name].favorite = 1 - self.roms[rom_name].favorite
            self.save_xml()
            return self.roms[rom_name].favorite == 1
        return False

    def toggle_ignore(self, rom_name):
        if rom_name in self.roms:
            self.roms[rom_name].ignore = 1 - self.roms[rom_name].ignore
            self.save_xml()
            return self.roms[rom_name].ignore == 1
        return False

    def get_rom_flags(self, rom_name):
        return self.flag_options.get(rom_name, "")
