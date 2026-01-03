import pygame
import os
from version import __version__

class UIManager:
    def __init__(self, config, skin_config):
        self.config = config
        self.skin = skin_config
        self.screen_width = config.screen_width
        self.screen_height = config.screen_height
        
        # Initialize Screen
        flags = pygame.SCALED | pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), flags)
        pygame.mouse.set_visible(False)
        pygame.display.set_caption(f"MAMEly v{__version__} Emulator Launcher")
        self.clock = pygame.time.Clock()
        
        # Font Cache
        self.fonts = {}
        
        # Image Cache (Path -> Surface)
        self.image_cache = {}
        
        # Load Background
        self.background = None
        self.load_background()

    def load_background(self):
        bg_path = self.skin.get("backgroundImage")
        if bg_path:
            full_path = os.path.join(self.skin.platform_path, bg_path)
            if os.path.exists(full_path):
                try:
                    self.background = pygame.image.load(full_path)
                except:
                    print(f"Failed to load background: {full_path}")
        
        if self.background is None:
            self.background = pygame.Surface((self.screen_width, self.screen_height))
            self.background.fill((0, 0, 0))

    def get_font(self, font_name, size):
        key = (font_name, size)
        if key not in self.fonts:
            font_path = os.path.join(self.skin.platform_path, font_name) if font_name else None
            try:
                if font_path and os.path.exists(font_path):
                     self.fonts[key] = pygame.font.Font(font_path, size)
                else:
                     self.fonts[key] = pygame.font.Font(None, size)
            except:
                self.fonts[key] = pygame.font.Font(None, size)
        return self.fonts[key]

    def draw_text(self, text, x, y, font_name, size, color, shadow_color=None, shadow=False, truncate_len=0, centered=True):
        if x is None or y is None:
            # Skip drawing if coordinates are missing
            return

        if truncate_len > 0 and len(text) > truncate_len:
            text = text[:truncate_len]
            
        font = self.get_font(font_name, size)
        
        if shadow and shadow_color:
            shadow_surf = font.render(text, True, shadow_color)
            shadow_rect = shadow_surf.get_rect()
            offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2)]
            for ox, oy in offsets:
                if centered:
                    shadow_rect.center = (x + ox, y + oy)
                else:
                    shadow_rect.topleft = (x + ox, y + oy)
                self.screen.blit(shadow_surf, shadow_rect)
                
        text_surf = font.render(text, True, color)
        text_rect = text_surf.get_rect()
        if centered:
            text_rect.center = (x, y)
        else:
            text_rect.topleft = (x, y)
        self.screen.blit(text_surf, text_rect)

    def draw_image(self, image_path, x1, y1, x2, y2, fallback_path=None):
        """Draw and scale image to fit within box defined by (x1, y1) to (x2, y2)."""
        # Check cache (scaled result could be cached but dimensions change rarely for same path)
        # We will cache the ORIGINAL loaded surface to avoid disk I/O.
        # Scaling is fast enough for one image, but we can cache scaled too if needed.
        # Given the usage, caching the result of load is critical.
        
        img = None
        if image_path in self.image_cache:
            img = self.image_cache[image_path]
        elif fallback_path and fallback_path in self.image_cache:
            img = self.image_cache[fallback_path]
            
        if img is None:
            # Try loading
            path_to_load = None
            if os.path.exists(image_path):
                path_to_load = image_path
            elif fallback_path and os.path.exists(fallback_path):
                path_to_load = fallback_path
                
            if path_to_load:
                try:
                    img = pygame.image.load(path_to_load)
                    
                    # Manage cache size - simple eviction
                    if len(self.image_cache) > 50:
                        self.image_cache.pop(next(iter(self.image_cache)))
                        
                    self.image_cache[path_to_load] = img
                    # Also link the requested path if it was the primary one
                    if path_to_load == image_path:
                        self.image_cache[image_path] = img
                        
                except Exception:
                    return
            else:
                return

        width = x2 - x1
        height = y2 - y1
        x_center = x1 + width // 2
        y_center = y1 + height // 2
        
        # Scale Logic
        img_w, img_h = img.get_size()
        scale_w = width / float(img_w)
        scale_h = height / float(img_h)
        scale = min(scale_w, scale_h) # Fit inside
        
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        # Transform (this creates a new surface, but it's in memory)
        # For absolute max performance we could cache this too, but disk I/O is the main killer.
        scaled_img = pygame.transform.scale(img, (new_w, new_h))
        
        draw_x = x_center - new_w // 2
        draw_y = y_center - new_h // 2
        
        self.screen.blit(scaled_img, (draw_x, draw_y))

    def draw_progress_bar(self, percent, x1, y1, x2):
        if percent <= 0: return
        full_width = x2 - x1
        bar_width = int(full_width * (percent / 100))
        pygame.draw.line(self.screen, (255, 0, 0), (x1, y1), (x1 + bar_width, y1), 20)

    def begin_frame(self):
        self.screen.blit(self.background, (0, 0))

    def end_frame(self):
        pygame.display.flip()
        self.clock.tick(60)
        
    def show_message(self, message, color=None):
        if not message: return
        # Use default message settings from skin
        x = self.skin.get("romListDisplayAreaXCenter", self.screen_width // 2)
        y = self.skin.get("romListDisplayAreaYCenter", self.screen_height // 2)
        # Fallback defaults if skin is missing keys but these usually exist
        if x is None: x = self.screen_width // 2
        if y is None: y = self.screen_height // 2
            
        font = self.skin.get("messageFont")
        size = self.skin.get("messageFontSize", 30)
        color = color if color else self.skin.get("defaultMessageColor", (255, 255, 255))
        
        self.draw_text(message, x, y, font, size, color, shadow=True, shadow_color=(0,0,0))
