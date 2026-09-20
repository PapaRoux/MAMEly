import pygame
import os
import math
from version import __version__
from config import is_none_token, is_off_token, is_procedural_show, is_procedural_decor_show, resolve_sprite_path
from mamely_log import get_logger

log = get_logger("ui")

NAV_KEY_ITEMS = [
    ("UP / DN:", "Scroll"),
    ("LEFT / RIGHT:", "Page Up / Dn"),
    ("ENTER / B1:", "Select / Play"),
    ("TAB / B2:", "Genre / Favs"),
    ("E / B3:", "Next Emu"),
    ("F / B4:", "+/- Favorite"),
    ("S / F4:", "Skin Switcher"),
    ("F3 / *:", "Settings"),
    ("D / F1:", "Diagnostics"),
    ("ESC / B9+10:", "Exit"),
]
NAV_SPRITE_IDS = {"up", "scroll_up", "mamely", "pasted_layer"}

class UIManager:
    def __init__(self, config, skin_config, platform_name=None):
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
        self._proc_overlay = None
        self.sprites_drawn = []
        self._sprite_scaled_cache = {}
        self.load_background(platform_name)
        self.load_sprites()

        # Video Capture State
        self.video_cap = None
        self.current_video_path = None
        self.last_video_frame_surf = None

    def _iter_visible_sprites(self):
        for spr in getattr(self.skin, "sprites", None) or []:
            if spr.get("show", True) and spr.get("file"):
                yield spr

    def _has_visible_nav_sprites(self):
        return any(spr.get("id") in NAV_SPRITE_IDS for spr in self._iter_visible_sprites())

    def _proc_base_size(self):
        is_portrait = (self.screen_width < self.screen_height)
        return (1080, 1920) if is_portrait else (1920, 1080)

    def generate_procedural_retrocade(self, platform_name=None):
        """CRT fill used when there is no background PNG. Chrome is a separate overlay."""
        base_w, base_h = self._proc_base_size()
        surf = pygame.Surface((base_w, base_h))
        surf.fill((12, 12, 18))
        scanline_surf = pygame.Surface((base_w, 2), pygame.SRCALPHA)
        scanline_surf.fill((0, 0, 0, 40))
        for y in range(0, base_h, 4):
            surf.blit(scanline_surf, (0, y))
        if (self.screen_width, self.screen_height) != (base_w, base_h):
            surf = pygame.transform.smoothscale(surf, (self.screen_width, self.screen_height))
        return surf

    def _draw_procedural_chrome_onto(self, surf, platform_name=None):
        """Paint neon frames, marquee, and pixel art onto surf (base Retrocade resolution)."""
        is_portrait = surf.get_width() < surf.get_height()
        neon_red = (245, 32, 68)
        neon_glow = (180, 20, 45)
        neon_cyan = (0, 230, 255)
        neon_green = (57, 255, 20)

        def draw_neon_box(x1, y1, x2, y2, radius=16, border_w=4):
            rect = pygame.Rect(x1, y1, x2 - x1, y2 - y1)
            pygame.draw.rect(surf, (18, 18, 25), rect, border_radius=radius)
            glow_rect = rect.inflate(2, 2)
            pygame.draw.rect(surf, neon_glow, glow_rect, width=1, border_radius=radius + 1)
            pygame.draw.rect(surf, neon_red, rect, width=border_w, border_radius=radius)

        def get_proc_font(size):
            return self.get_font("Continuum-Bold-Regular.ttf", size)

        p_name = platform_name
        if not p_name:
            if hasattr(self.skin, "platform_path") and self.skin.platform_path:
                p_name = os.path.basename(self.skin.platform_path)
            else:
                p_name = "MAME"

        if not is_portrait:
            if is_procedural_show(self.skin):
                draw_neon_box(42, 32, 1053, 148, radius=16)
                draw_neon_box(42, 190, 1053, 900, radius=18)
                draw_neon_box(42, 928, 1053, 1042, radius=16)
                rx1, rx2 = 1348, 1877
                draw_neon_box(rx1, 343, rx2, 470, radius=16)
                draw_neon_box(rx1, 469, rx2, 926, radius=16)
                draw_neon_box(rx1, 929, rx2, 1047, radius=16)

            if is_procedural_decor_show(self.skin):
                plat_title = p_name.upper()
                title_font = get_proc_font(58)
                sub_font = self.get_font(None, 22)
                tx, ty = 1470, 110
                for ox, oy, s_col in [(-4, -4, (0, 0, 0)), (4, 4, (10, 40, 100)), (2, 2, (20, 80, 180)), (0, 0, neon_cyan)]:
                    t_surf = title_font.render(plat_title, True, s_col)
                    surf.blit(t_surf, t_surf.get_rect(center=(tx + ox, ty + oy)))

                if "MAME" in plat_title or "ARCADE" in plat_title:
                    sub_text = "MULTIPLE ARCADE MACHINE EMULATOR"
                else:
                    sub_text = f"{plat_title} EMULATION SYSTEM"
                sub_surf = sub_font.render(sub_text, True, (220, 230, 245))
                surf.blit(sub_surf, sub_surf.get_rect(center=(tx, ty + 46)))
        else:
            if is_procedural_show(self.skin):
                draw_neon_box(44, 330, 751, 415, radius=14)
                draw_neon_box(48, 448, 740, 1708, radius=16)
                draw_neon_box(44, 1754, 746, 1850, radius=14)
                rx1, rx2 = 780, 1050
                draw_neon_box(rx1, 762, rx2, 828, radius=12)
                draw_neon_box(rx1, 828, rx2, 1378, radius=14)
                draw_neon_box(rx1, 1379, rx2, 1460, radius=12)

            if is_procedural_decor_show(self.skin):
                plat_title = p_name.upper()
                title_font = get_proc_font(52)
                sub_font = self.get_font(None, 22)
                tx, ty = 540, 160
                for ox, oy, s_col in [(-3, -3, (0, 0, 0)), (3, 3, (10, 40, 100)), (0, 0, neon_cyan)]:
                    t_surf = title_font.render(plat_title, True, s_col)
                    surf.blit(t_surf, t_surf.get_rect(center=(tx + ox, ty + oy)))
                if "MAME" in plat_title or "ARCADE" in plat_title:
                    sub_text = "MULTIPLE ARCADE MACHINE EMULATOR"
                else:
                    sub_text = f"{plat_title} ARCADE & CONSOLE EMULATION"
                sub_surf = sub_font.render(sub_text, True, (220, 230, 245))
                surf.blit(sub_surf, sub_surf.get_rect(center=(tx, ty + 46)))

        if not is_procedural_decor_show(self.skin):
            return

        def draw_pixel_matrix(matrix, px, py, scale, color):
            for r_i, row in enumerate(matrix):
                for c_i, char in enumerate(row):
                    if char != " ":
                        pygame.draw.rect(surf, color, (px + c_i * scale, py + r_i * scale, scale, scale))

        invader_sprite = [
            "  #     #  ",
            "   #   #   ",
            "  #######  ",
            " ## ### ## ",
            "###########",
            "# ####### #",
            "# #     # #",
            "   ## ##   ",
        ]
        ghost_sprite = [
            "  #####  ",
            " ####### ",
            "##  #  ##",
            "##  #  ##",
            "#########",
            "#########",
            "# # # # #",
            "#   #   #",
        ]

        if not is_portrait:
            draw_pixel_matrix(invader_sprite, 1180, 310, 5, neon_green)
            draw_pixel_matrix(ghost_sprite, 1100, 40, 5, (255, 60, 60))
            draw_pixel_matrix(ghost_sprite, 1160, 40, 5, neon_cyan)
            draw_pixel_matrix(ghost_sprite, 1220, 40, 5, (255, 184, 82))
            draw_pixel_matrix(ghost_sprite, 1280, 40, 5, (255, 184, 255))
        else:
            draw_pixel_matrix(invader_sprite, 790, 340, 4, neon_green)
            draw_pixel_matrix(ghost_sprite, 180, 50, 4, (255, 60, 60))
            draw_pixel_matrix(ghost_sprite, 240, 50, 4, neon_cyan)
            draw_pixel_matrix(ghost_sprite, 300, 50, 4, (255, 184, 82))

    def rebuild_procedural_overlay(self, platform_name=None):
        """Cache a transparent chrome overlay when frames and/or header art are on."""
        if not is_procedural_show(self.skin) and not is_procedural_decor_show(self.skin):
            self._proc_overlay = None
            return
        base_w, base_h = self._proc_base_size()
        surf = pygame.Surface((base_w, base_h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        self._draw_procedural_chrome_onto(surf, platform_name)
        if (self.screen_width, self.screen_height) != (base_w, base_h):
            surf = pygame.transform.smoothscale(surf, (self.screen_width, self.screen_height))
        self._proc_overlay = surf

    def generate_blank_background(self):
        """Flat dark fill used when backgroundImage is off (no PNG, no CRT)."""
        surf = pygame.Surface((self.screen_width, self.screen_height))
        surf.fill((0, 0, 0))
        return surf

    def load_background(self, platform_name=None):
        bg_path = self.skin.get("backgroundImage") if self.skin else None
        is_off = bool(self.skin) and is_off_token(bg_path)
        is_none_skin = (
            not self.skin
            or is_none_token(getattr(self.skin, "skin_file", None))
            or is_none_token(bg_path)
        )
        loaded = False
        self.procedural_background = False
        if is_off:
            self.background = self.generate_blank_background()
            loaded = True
        elif bg_path and not is_none_skin:
            full_path = os.path.join(self.skin.platform_path, bg_path)
            if os.path.exists(full_path):
                try:
                    self.background = pygame.image.load(full_path)
                    if self.background.get_size() != (self.screen_width, self.screen_height):
                        self.background = pygame.transform.smoothscale(
                            self.background, (self.screen_width, self.screen_height)
                        )
                    loaded = True
                except Exception as e:
                    log.warning("failed to load background path=%s: %s", full_path, e)

        if not loaded:
            self.background = self.generate_procedural_retrocade(platform_name)
            self.procedural_background = True
        self.rebuild_procedural_overlay(platform_name)

    def load_sprites(self):
        """Load skin-configured sprites from platforms/<PLATFORM>/sprites/ (or repo sprites/)."""
        self.sprites_drawn = []
        self._sprite_scaled_cache = {}
        if not self.skin:
            return
        platform_path = getattr(self.skin, "platform_path", "") or ""
        for spr in getattr(self.skin, "sprites", None) or []:
            if not spr.get("show", True):
                continue
            filename = spr.get("file")
            path = resolve_sprite_path(filename, platform_path)
            if not path:
                if filename:
                    log.warning("sprite not found file=%s", filename)
                continue
            try:
                if path in self.image_cache:
                    surf = self.image_cache[path]
                else:
                    try:
                        surf = pygame.image.load(path).convert_alpha()
                    except pygame.error:
                        surf = pygame.image.load(path)
                    self.image_cache[path] = surf
                self.sprites_drawn.append({
                    "id": spr.get("id"),
                    "surf": surf,
                    "x": int(spr.get("x") or 0),
                    "y": int(spr.get("y") or 0),
                    "w": spr.get("w"),
                    "h": spr.get("h"),
                    "show": True,
                })
            except Exception as e:
                log.warning("failed to load sprite path=%s: %s", path, e)

    def draw_sprites(self):
        """Blit active skin sprites over the background."""
        hide_nav = self.skin and not self.skin.get("navKeysShow", True)
        for spr in self.sprites_drawn:
            if hide_nav and spr.get("id") in NAV_SPRITE_IDS:
                continue
            surf = spr["surf"]
            x, y = spr["x"], spr["y"]
            w, h = spr.get("w"), spr.get("h")
            draw_surf = surf
            if w or h:
                src_w, src_h = surf.get_size()
                if w and h:
                    nw, nh = int(w), int(h)
                elif w:
                    nw = int(w)
                    nh = int(src_h * (nw / float(src_w))) if src_w else int(w)
                else:
                    nh = int(h)
                    nw = int(src_w * (nh / float(src_h))) if src_h else int(h)
                if nw < 1:
                    nw = 1
                if nh < 1:
                    nh = 1
                key = (id(surf), nw, nh)
                cached = self._sprite_scaled_cache.get(key)
                if cached is None:
                    cached = pygame.transform.smoothscale(surf, (nw, nh))
                    self._sprite_scaled_cache[key] = cached
                draw_surf = cached
            self.screen.blit(draw_surf, (x, y))

    def get_font(self, font_name, size):
        try:
            size = int(size)
        except (ValueError, TypeError):
            size = 20

        key = (font_name, size)
        if key not in self.fonts:
            font_path = os.path.join(self.skin.platform_path, font_name) if font_name else None
            try:
                if font_path and os.path.exists(font_path):
                     self.fonts[key] = pygame.font.Font(font_path, size)
                else:
                     self.fonts[key] = pygame.font.Font(None, size)
            except Exception:
                self.fonts[key] = pygame.font.Font(None, size)
        return self.fonts[key]

    def draw_text(self, text, x, y, font_name, size, color, shadow_color=None, shadow=False, truncate_len=0, centered=True, align=None):
        """Draw text. With centered=True, y is the vertical middle and `align`
        picks the horizontal anchor: 'left' treats x as the left edge, 'right'
        as the right edge, 'center' (default) as the midpoint."""
        if x is None or y is None:
            # Skip drawing if coordinates are missing
            return

        if not isinstance(truncate_len, int):
            truncate_len = 0

        if color is None:
            color = (255, 255, 255)
        if shadow and shadow_color is None:
            shadow_color = (0, 0, 0)

        if truncate_len > 0 and len(text) > truncate_len:
            text = text[:truncate_len]
            
        # Defensive check to prevent "invalid color argument" crashes
        if not isinstance(color, (tuple, list, pygame.Color)) or len(color) < 3:
            color = (255, 255, 255)
        if shadow:
            if not isinstance(shadow_color, (tuple, list, pygame.Color)) or len(shadow_color) < 3:
                shadow_color = (0, 0, 0)

        font = self.get_font(font_name, size)

        def anchor(rect, ax, ay):
            if not centered:
                rect.topleft = (ax, ay)
            elif align == "left":
                rect.midleft = (ax, ay)
            elif align == "right":
                rect.midright = (ax, ay)
            else:
                rect.center = (ax, ay)

        if shadow and shadow_color:
            shadow_surf = font.render(text, True, shadow_color)
            shadow_rect = shadow_surf.get_rect()
            offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2)]
            for ox, oy in offsets:
                anchor(shadow_rect, x + ox, y + oy)
                self.screen.blit(shadow_surf, shadow_rect)
                
        text_surf = font.render(text, True, color)
        text_rect = text_surf.get_rect()
        anchor(text_rect, x, y)
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

    def set_active_video(self, video_path):
        """Set the active video snap to play. Release old capture if path changes."""
        if self.current_video_path != video_path:
            self.close_video()
            self.current_video_path = video_path
            if video_path and os.path.exists(video_path):
                import cv2
                try:
                    self.video_cap = cv2.VideoCapture(video_path)
                    if not self.video_cap.isOpened():
                        log.debug("video snap not opened path=%s", video_path)
                        self.video_cap = None
                    else:
                        log.debug("video snap start path=%s", video_path)
                except Exception as e:
                    log.warning("error opening video path=%s: %s", video_path, e)
                    self.video_cap = None

    def draw_video_frame(self, x1, y1, x2, y2, paused=False):
        """Read next frame from active video, scale, and render inside rect."""
        if self.video_cap is None:
            return False
            
        width = x2 - x1
        height = y2 - y1
        x_center = x1 + width // 2
        y_center = y1 + height // 2
        
        # If paused, render the cached frame surface
        if paused and self.last_video_frame_surf is not None:
            self.screen.blit(self.last_video_frame_surf, (x_center - self.last_video_frame_surf.get_width() // 2, y_center - self.last_video_frame_surf.get_height() // 2))
            return True
            
        import cv2
        try:
            ret, frame = self.video_cap.read()
            if not ret:
                # Loop video by resetting to start frame
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_cap.read()
                
            if ret:
                # Convert BGR (OpenCV) to RGB (Pygame)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Transpose frame (OpenCV is HxW, Pygame is WxH)
                frame = cv2.transpose(frame)
                img = pygame.surfarray.make_surface(frame)
                
                img_w, img_h = img.get_size()
                scale = min(width / float(img_w), height / float(img_h))
                new_w, new_h = int(img_w * scale), int(img_h * scale)
                
                scaled_img = pygame.transform.scale(img, (new_w, new_h))
                self.last_video_frame_surf = scaled_img  # Cache the surface
                self.screen.blit(scaled_img, (x_center - new_w // 2, y_center - new_h // 2))
                return True
        except Exception as e:
            log.warning("error rendering video frame: %s", e)
            self.close_video()
            
        return False

    def close_video(self):
        """Release active video resources."""
        if self.video_cap is not None:
            try:
                self.video_cap.release()
            except Exception:
                pass
            self.video_cap = None
        self.current_video_path = None
        self.last_video_frame_surf = None

    def draw_progress_bar(self, percent, x1, y1, x2):
        if percent <= 0: return
        full_width = x2 - x1
        bar_width = int(full_width * (percent / 100))
        pygame.draw.line(self.screen, (255, 0, 0), (x1, y1), (x1 + bar_width, y1), 20)

    def begin_frame(self):
        self.screen.blit(self.background, (0, 0))
        overlay = getattr(self, "_proc_overlay", None)
        if overlay is not None:
            self.screen.blit(overlay, (0, 0))
        self.draw_sprites()
        self.draw_nav_keys()

    def _nav_keys_rect(self):
        portrait = self.screen_width < self.screen_height
        if portrait:
            dx1, dy1, dx2, dy2 = 775, 1475, 1050, 1860
        else:
            dx1, dy1, dx2, dy2 = 1075, 670, 1330, 1030
        x1 = int(self.skin.get("navKeysX1", dx1) or dx1)
        y1 = int(self.skin.get("navKeysY1", dy1) or dy1)
        x2 = int(self.skin.get("navKeysX2", dx2) or dx2)
        y2 = int(self.skin.get("navKeysY2", dy2) or dy2)
        return pygame.Rect(x1, y1, max(8, x2 - x1), max(8, y2 - y1))

    def draw_nav_keys(self):
        """Draw or hide the in-game navigation keys card according to navKeysShow."""
        if not self.skin:
            return
        show = self.skin.get("navKeysShow", True)
        rect = self._nav_keys_rect()
        if not show:
            pygame.draw.rect(self.screen, (0, 0, 0), rect)
            return
        if not is_procedural_decor_show(self.skin):
            return
        if self._has_visible_nav_sprites():
            return

        neon_red = (245, 32, 68)
        neon_glow = (180, 20, 45)
        neon_yellow = (255, 235, 0)
        neon_cyan = (0, 230, 255)
        nx1, ny1, nw, nh = rect.x, rect.y, rect.w, rect.h
        pygame.draw.rect(self.screen, (16, 16, 24), rect, border_radius=14)
        pygame.draw.rect(self.screen, neon_glow, rect.inflate(2, 2), width=1, border_radius=15)
        pygame.draw.rect(self.screen, neon_red, rect, width=3, border_radius=14)

        header_font = self.get_font("Continuum-Bold-Regular.ttf", 26)
        header_surf = header_font.render("MAMEly", True, neon_yellow)
        self.screen.blit(header_surf, header_surf.get_rect(center=(nx1 + nw // 2, ny1 + 22)))
        pygame.draw.line(self.screen, neon_yellow, (nx1 + 30, ny1 + 38), (nx1 + nw - 30, ny1 + 38), 2)

        nav_font = self.get_font(None, 20)
        key_x = nx1 + int(nw * 0.44)
        act_x = nx1 + int(nw * 0.46)
        row_h = max(22, (nh - 56) // max(1, len(NAV_KEY_ITEMS)))
        row_y = ny1 + 48
        for key_lbl, act_lbl in NAV_KEY_ITEMS:
            k_surf = nav_font.render(key_lbl, True, (255, 255, 255))
            a_surf = nav_font.render(act_lbl, True, neon_cyan)
            self.screen.blit(k_surf, k_surf.get_rect(midright=(key_x, row_y + 12)))
            self.screen.blit(a_surf, a_surf.get_rect(midleft=(act_x, row_y + 12)))
            row_y += row_h

    def end_frame(self):
        pygame.display.flip()
        self.clock.tick(60)
        
    def draw_toast_message(self, message, color=None):
        """Draw centered toast message with a semi-transparent contrast card background."""
        if not message:
            return

        cx, cy = self.screen_width // 2, self.screen_height // 2

        font_name = self.skin.get("messageFont")
        size = self.skin.get("messageFontSize", 28)
        try:
            size = int(size)
        except (ValueError, TypeError):
            size = 28

        if color is None:
            color = self.skin.get("defaultMessageColor", (255, 230, 90))

        font = self.get_font(font_name, size)

        pad_x, pad_y = 28, 14
        max_text_w = self.screen_width - 40 - pad_x * 2
        lines = self._wrap_text(font, message, max_text_w, max_lines=4)

        line_h = font.get_linesize()
        text_w = max(font.size(line)[0] for line in lines)
        box_w = min(self.screen_width - 40, text_w + pad_x * 2)
        box_h = line_h * len(lines) + pad_y * 2

        # Draw semi-transparent contrast background card
        card = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(card, (15, 17, 26, 220), card.get_rect(), border_radius=10)
        pygame.draw.rect(card, (137, 180, 250, 200), card.get_rect(), width=2, border_radius=10)

        draw_x = cx - box_w // 2
        draw_y = cy - box_h // 2
        self.screen.blit(card, (draw_x, draw_y))

        # Render centered text lines on top of contrast box
        for i, line in enumerate(lines):
            line_y = draw_y + pad_y + i * line_h + line_h // 2
            self.draw_text(line, cx, line_y, font_name, size, color, shadow=True, shadow_color=(0, 0, 0))

    @staticmethod
    def _wrap_text(font, text, max_width, max_lines=4):
        """Word-wrap text to max_width pixels. Words wider than a line (long
        paths) are split by character. Overflow past max_lines ends in '...'."""
        lines, current = [], ""
        for word in text.split():
            candidate = f"{current} {word}" if current else word
            if font.size(candidate)[0] <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = ""
            while font.size(word)[0] > max_width:
                cut = len(word) - 1
                while cut > 1 and font.size(word[:cut])[0] > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        if current:
            lines.append(current)
        if not lines:
            return [""]
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and font.size(last + "...")[0] > max_width:
                last = last[:-1]
            lines[-1] = last + "..."
        return lines

    def show_message(self, message, color=None):
        """Show transient toast message in screen center with contrast box."""
        self.draw_toast_message(message, color=color)

    def draw_modal(self, message, subtext="Press RUN to Confirm, EXIT to Cancel"):
        # Overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # Helper for centering
        cx, cy = self.screen_width // 2, self.screen_height // 2
        
        # Draw Box (Optional, just text is fine for retro feel implies overlay is sufficient)
        pygame.draw.rect(self.screen, (50, 50, 50), (cx - 300, cy - 100, 600, 200))
        pygame.draw.rect(self.screen, (255, 255, 255), (cx - 300, cy - 100, 600, 200), 2)
        
        # Message
        self.draw_text(message, cx, cy - 20, None, 40, (255, 255, 255), shadow=True)
        
        # Subtext
        self.draw_text(subtext, cx, cy + 30, None, 25, (200, 200, 200), shadow=True)

    def info_panel_page_size(self):
        """How many help lines fit between the MORE cues and footer."""
        margin = 40
        panel_h = self.screen_height - margin * 2
        line_height = 30
        cue_h = 48
        footer_h = 40
        return max(1, (panel_h - cue_h * 2 - footer_h) // line_height)

    def _draw_more_cue(self, cx, y, pointing_up):
        """Bright ▲ MORE / ▼ MORE hint for the F1 help panel."""
        pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 220.0))
        color = (int(255 * pulse), int(230 * pulse), int(80 * pulse))
        half_w, h = 16, 14
        if pointing_up:
            pts = [(cx, y), (cx - half_w, y + h), (cx + half_w, y + h)]
            text_y = y + h + 2
        else:
            pts = [(cx, y + h), (cx - half_w, y), (cx + half_w, y)]
            text_y = y - 22
        pygame.draw.polygon(self.screen, color, pts)
        pygame.draw.polygon(self.screen, (255, 255, 200), pts, 2)
        label = self.get_font(None, 22).render("MORE", True, color)
        self.screen.blit(label, label.get_rect(midtop=(cx, text_y)))

    def draw_info_panel(self, lines, scroll_line=0):
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(210)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        margin = 40
        panel_w = self.screen_width - margin * 2
        panel_h = self.screen_height - margin * 2
        pygame.draw.rect(self.screen, (30, 30, 40), (margin, margin, panel_w, panel_h))
        pygame.draw.rect(self.screen, (255, 255, 0), (margin, margin, panel_w, panel_h), 2)

        font_size = 22
        line_height = 30
        font = self.get_font(None, font_size)
        cue_h = 48
        footer_h = 40
        max_visible = self.info_panel_page_size()
        more_above = scroll_line > 0
        more_below = scroll_line + max_visible < len(lines)
        visible = lines[scroll_line:scroll_line + max_visible]

        text_x = margin + 28
        tab_x = text_x + 300
        y = margin + cue_h
        cx = margin + panel_w // 2
        if more_above:
            self._draw_more_cue(cx, margin + 8, pointing_up=True)

        for line in visible:
            color = (255, 255, 100) if line.startswith("MAMEly") else (220, 220, 220)
            if line.startswith("  !"):
                color = (255, 120, 120)
            elif line.startswith("  ?"):
                color = (255, 200, 120)
            elif line in ("Paths", "Emulator", "Controls", "Settings live in:", "Troubleshooting:", "Issues"):
                color = (180, 220, 255)

            if "\t" in line:
                left, right = line.split("\t", 1)
                left_surf = font.render(left, True, (255, 255, 255))
                right_surf = font.render(right, True, (180, 190, 205))
                self.screen.blit(left_surf, (text_x, y))
                rx = max(tab_x, text_x + left_surf.get_width() + 28)
                self.screen.blit(right_surf, (rx, y))
            else:
                text_surf = font.render(line, True, color)
                self.screen.blit(text_surf, (text_x, y))
            y += line_height

        if more_below:
            self._draw_more_cue(cx, margin + panel_h - footer_h - 28, pointing_up=False)

        footer_surf = font.render("F1 or Esc to close", True, (160, 160, 160))
        self.screen.blit(footer_surf, (margin + 20, margin + panel_h - 32))

    def settings_gear_rect(self):
        size = 72
        margin = 16
        return pygame.Rect(self.screen_width - size - margin, margin, size, size)

    def draw_settings_gear(self, highlighted=False):
        """Top-right gear affordance for mouse users."""
        rect = self.settings_gear_rect()
        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        ox, oy = rect.w // 2, rect.h // 2
        fill = (255, 220, 100, 240) if highlighted else (220, 225, 235, 220)
        pygame.draw.circle(overlay, (20, 22, 32, 210), (ox, oy), ox - 2)
        pygame.draw.circle(overlay, fill, (ox, oy), ox - 6, 2)
        r_outer = ox - 16
        for i in range(6):
            ang = math.radians(i * 60)
            x = ox + int(math.cos(ang) * r_outer)
            y = oy + int(math.sin(ang) * r_outer)
            pygame.draw.circle(overlay, fill, (x, y), 7)
        pygame.draw.circle(overlay, fill, (ox, oy), 15, 3)
        pygame.draw.circle(overlay, (20, 22, 32, 240), (ox, oy), 7)
        pygame.draw.circle(overlay, fill, (ox, oy), 7, 2)
        self.screen.blit(overlay, rect.topleft)
        return rect

    def draw_settings_panel(self, rows, selected_idx):
        """Draw the Settings OSD. Returns a list of (key, rect) for mouse hits."""
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        self.screen.blit(overlay, (0, 0))

        box_w = min(820, self.screen_width - 80)
        box_h = min(560, self.screen_height - 80)
        box = pygame.Rect(
            (self.screen_width - box_w) // 2,
            (self.screen_height - box_h) // 2,
            box_w,
            box_h,
        )
        pygame.draw.rect(self.screen, (24, 26, 38), box, border_radius=14)
        pygame.draw.rect(self.screen, (255, 220, 100), box, width=3, border_radius=14)

        title_font = self.get_font(None, 36)
        title = title_font.render("SETTINGS", True, (255, 220, 100))
        self.screen.blit(title, title.get_rect(center=(box.centerx, box.top + 42)))

        sub_font = self.get_font(None, 20)
        sub = sub_font.render("Startup & browser preferences", True, (180, 190, 210))
        self.screen.blit(sub, sub.get_rect(center=(box.centerx, box.top + 78)))

        label_font = self.get_font(None, 26)
        hint_font = self.get_font(None, 18)
        section_font = self.get_font(None, 20)
        y = box.top + 110
        hit_rects = []
        toggle_i = 0
        for row in rows:
            if row.get("section"):
                y += 8
                hdr = section_font.render(row["section"].upper(), True, (137, 180, 250))
                self.screen.blit(hdr, (box.left + 40, y))
                y += 34
                continue

            selected = toggle_i == selected_idx
            row_rect = pygame.Rect(box.left + 28, y - 8, box_w - 56, 64)
            if selected:
                pygame.draw.rect(self.screen, (45, 48, 70), row_rect, border_radius=10)
                pygame.draw.rect(self.screen, (255, 220, 100), row_rect, width=2, border_radius=10)

            on = bool(row.get("value"))
            box_color = (166, 227, 161) if on else (88, 91, 112)
            check_rect = pygame.Rect(box.left + 48, y + 8, 28, 28)
            pygame.draw.rect(self.screen, box_color, check_rect, border_radius=4)
            pygame.draw.rect(self.screen, (255, 255, 255), check_rect, width=2, border_radius=4)
            if on:
                cx, cy = check_rect.centerx, check_rect.centery
                check = [
                    (cx - 7, cy + 1),
                    (cx - 2, cy + 7),
                    (cx + 8, cy - 6),
                ]
                pygame.draw.lines(self.screen, (20, 40, 28), False, check, 4)

            label_color = (255, 255, 255) if selected else (220, 225, 235)
            label = label_font.render(row["label"], True, label_color)
            self.screen.blit(label, (check_rect.right + 16, y + 2))
            hint = hint_font.render(row.get("hint") or "", True, (160, 168, 185))
            self.screen.blit(hint, (check_rect.right + 16, y + 32))

            on_lbl = hint_font.render("ON" if on else "OFF", True, box_color)
            self.screen.blit(on_lbl, on_lbl.get_rect(midright=(box.right - 48, y + 22)))

            hit_rects.append((row["key"], row_rect))
            toggle_i += 1
            y += 70

        footer_font = self.get_font(None, 18)
        footer = footer_font.render(
            "Up/Down select   Enter, Space, or Left/Right toggle   F3 or Esc close",
            True,
            (160, 160, 160),
        )
        self.screen.blit(footer, footer.get_rect(center=(box.centerx, box.bottom - 28)))
        return hit_rects

    def draw_search_bar(self, query, active=True):
        # Position at the bottom center of the screen
        bar_h = 50
        bar_w = 700
        x = (self.screen_width - bar_w) // 2
        y = self.screen_height - bar_h - 25
        
        # Draw background card
        rect = pygame.Rect(x, y, bar_w, bar_h)
        pygame.draw.rect(self.screen, (30, 30, 46), rect, border_radius=8)
        
        # Border
        border_color = (137, 180, 250) if active else (88, 91, 112)
        pygame.draw.rect(self.screen, border_color, rect, width=2, border_radius=8)
        
        # Render Text
        font = self.get_font(None, 24)
        
        # Prompt label
        prompt_str = "Search: "
        prompt_surf = font.render(prompt_str, True, (205, 214, 244))
        self.screen.blit(prompt_surf, (x + 25, y + (bar_h - prompt_surf.get_height()) // 2))
        
        # Blinking cursor & query
        cursor = "|" if active and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        query_str = query + cursor
        query_surf = font.render(query_str, True, (249, 226, 175) if active else (166, 173, 200))
        self.screen.blit(query_surf, (x + 25 + prompt_surf.get_width(), y + (bar_h - query_surf.get_height()) // 2))
        
        # Help controls subtext
        help_str = "ESC to Clear | ENTER to Lock"
        help_font = self.get_font(None, 16)
        help_surf = help_font.render(help_str, True, (166, 173, 200))
        self.screen.blit(help_surf, (x + bar_w - help_surf.get_width() - 25, y + (bar_h - help_surf.get_height()) // 2))

    def draw_slot_machine(self, labels, reel_pos, font_name=None, phase="spin", flash=0.0):
        """Fullscreen slot-machine reel overlay.

        labels: list of display strings (ROM descriptions)
        reel_pos: continuous reel position (integer part = index at payline when frac==0)
        phase: 'spin' | 'win'
        flash: 0..1 win celebration pulse
        """
        n = len(labels)
        if n == 0:
            return

        w, h = self.screen_width, self.screen_height
        cx, cy = w // 2, h // 2

        # Dim the cabinet UI behind the machine
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 210))
        self.screen.blit(dim, (0, 0))

        # Machine body
        body_w = min(920, w - 80)
        body_h = min(620, h - 60)
        body = pygame.Rect(cx - body_w // 2, cy - body_h // 2, body_w, body_h)
        pygame.draw.rect(self.screen, (28, 18, 42), body, border_radius=18)
        pygame.draw.rect(self.screen, (255, 200, 60), body, width=5, border_radius=18)
        pygame.draw.rect(self.screen, (180, 40, 70), body.inflate(-14, -14), width=3, border_radius=14)

        # Marquee
        title_font = self.get_font(font_name, 54)
        subtitle_font = self.get_font(font_name, 22)
        title = "LUCKY DIP"
        if phase == "win":
            title = "WINNER!"
        title_col = (255, 230, 90) if phase != "win" else (255, 255, 160)
        if flash > 0:
            pulse = 0.55 + 0.45 * abs(math.sin(flash * 12))
            title_col = (
                min(255, int(255 * pulse)),
                min(255, int(240 * pulse)),
                min(255, int(80 + 120 * pulse)),
            )
        title_surf = title_font.render(title, True, title_col)
        title_shadow = title_font.render(title, True, (0, 0, 0))
        tr = title_surf.get_rect(center=(cx, body.top + 48))
        self.screen.blit(title_shadow, tr.move(3, 3))
        self.screen.blit(title_surf, tr)

        sub = "Press ESC to cancel" if phase == "spin" else "Get ready to play..."
        sub_surf = subtitle_font.render(sub, True, (220, 180, 220))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(cx, body.top + 92)))

        # Reel window
        row_h = 70
        visible = 7
        reel_h = row_h * visible
        reel_w = body_w - 100
        reel_rect = pygame.Rect(cx - reel_w // 2, cy - reel_h // 2 + 20, reel_w, reel_h)

        # Inner well
        pygame.draw.rect(self.screen, (8, 8, 16), reel_rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 215, 80), reel_rect, width=3, border_radius=8)

        # Clip to reel window
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(reel_rect)

        name_font = self.get_font(font_name, 32)
        frac = reel_pos % 1.0
        base_idx = int(reel_pos) % n
        # Rows relative to center payline (-3..+3)
        half = visible // 2
        for row in range(-half - 1, half + 2):
            idx = (base_idx + row) % n
            # Center row sits at reel midpoint; frac scrolls upward (items move up)
            y = reel_rect.centery + row * row_h - int(frac * row_h)
            text = labels[idx]
            if len(text) > 36:
                text = text[:35] + "…"

            # Distance from payline for fade / scale
            dist = abs(row - frac)
            if dist > half + 0.6:
                continue

            # Motion blur: draw trailing ghost copies while spinning fast
            if phase == "spin" and frac > 0.02:
                for ghost in (0.35, 0.2):
                    gy = y + int(row_h * ghost)
                    gcol = (90, 70, 110)
                    gsurf = name_font.render(text, True, gcol)
                    gsurf.set_alpha(70)
                    self.screen.blit(gsurf, gsurf.get_rect(center=(cx, gy)))

            is_center = abs(row - frac) < 0.5
            if is_center:
                color = (255, 245, 160) if phase == "spin" else (255, 255, 255)
            else:
                fade = max(0.35, 1.0 - dist * 0.22)
                color = (int(200 * fade), int(190 * fade), int(220 * fade))

            surf = name_font.render(text, True, color)
            self.screen.blit(surf, surf.get_rect(center=(cx, y)))

        self.screen.set_clip(prev_clip)

        # Payline glass / highlight bar
        pay = pygame.Rect(reel_rect.left + 6, reel_rect.centery - row_h // 2, reel_rect.width - 12, row_h)
        glass = pygame.Surface((pay.width, pay.height), pygame.SRCALPHA)
        if phase == "win":
            alpha = int(90 + 80 * abs(math.sin(flash * 10)))
            glass.fill((255, 220, 60, alpha))
        else:
            glass.fill((255, 255, 255, 35))
        self.screen.blit(glass, pay.topleft)
        pygame.draw.rect(self.screen, (255, 80, 80), pay, width=3)

        # Side arrows pointing at payline
        ay = pay.centery
        pygame.draw.polygon(self.screen, (255, 60, 80), [
            (reel_rect.left - 18, ay),
            (reel_rect.left - 4, ay - 14),
            (reel_rect.left - 4, ay + 14),
        ])
        pygame.draw.polygon(self.screen, (255, 60, 80), [
            (reel_rect.right + 18, ay),
            (reel_rect.right + 4, ay - 14),
            (reel_rect.right + 4, ay + 14),
        ])

        # Decorative lights along the frame
        light_y = body.top + 18
        for i in range(9):
            lx = body.left + 40 + i * ((body_w - 80) / 8)
            on = ((pygame.time.get_ticks() // 90) + i) % 3 == 0
            col = (255, 220, 80) if on else (80, 50, 20)
            pygame.draw.circle(self.screen, col, (int(lx), light_y), 7)
            pygame.draw.circle(self.screen, (255, 255, 200) if on else (40, 30, 20), (int(lx), light_y), 3)

        # Footer chrome
        foot = "SPINNING..." if phase == "spin" else "LAUNCHING..."
        foot_surf = subtitle_font.render(foot, True, (255, 200, 120))
        self.screen.blit(foot_surf, foot_surf.get_rect(center=(cx, body.bottom - 36)))

    def draw_skin_picker(self, skin_files, selected_idx, active_skin_filename, platform_name):
        """Draw interactive skin switcher file picker modal."""
        w, h = self.screen_width, self.screen_height
        cx, cy = w // 2, h // 2

        # Dim background overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))

        # Dialog Box Dimensions
        box_w = min(750, w - 80)
        box_h = min(520, h - 80)
        box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)

        # Draw outer container with border
        pygame.draw.rect(self.screen, (24, 26, 38), box_rect, border_radius=14)
        pygame.draw.rect(self.screen, (137, 180, 250), box_rect, width=3, border_radius=14)
        pygame.draw.rect(self.screen, (45, 48, 70), box_rect.inflate(-10, -10), width=2, border_radius=10)

        # Title Header
        title_font = self.get_font(None, 34)
        title_text = f"SKIN SWITCHER — {platform_name}"
        title_surf = title_font.render(title_text, True, (255, 220, 100))
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, box_rect.top + 40)))

        # Subtitle
        sub_font = self.get_font(None, 20)
        sub_surf = sub_font.render("Live Previewing Platform Skins", True, (180, 190, 210))
        self.screen.blit(sub_surf, sub_surf.get_rect(center=(cx, box_rect.top + 72)))

        # List Area
        list_y_start = box_rect.top + 105
        item_h = 44
        max_visible = (box_h - 170) // item_h
        
        n = len(skin_files)
        if n == 0:
            no_font = self.get_font(None, 24)
            no_surf = no_font.render("No .skin files found in platform folder", True, (255, 100, 100))
            self.screen.blit(no_surf, no_surf.get_rect(center=(cx, cy)))
        else:
            # Scroll window calculation
            start_idx = max(0, min(selected_idx - max_visible // 2, n - max_visible))
            if start_idx < 0: start_idx = 0
            end_idx = min(n, start_idx + max_visible)

            for slot_i, i in enumerate(range(start_idx, end_idx)):
                skin_name = skin_files[i]
                item_y = list_y_start + slot_i * item_h
                item_rect = pygame.Rect(cx - (box_w - 60) // 2, item_y, box_w - 60, item_h - 6)

                is_selected = (i == selected_idx)
                is_active = (skin_name == active_skin_filename) or (
                    skin_name == "none" and is_none_token(active_skin_filename)
                )

                if is_selected:
                    pygame.draw.rect(self.screen, (137, 180, 250), item_rect, border_radius=6)
                    text_col = (15, 17, 26)
                    badge_col = (40, 40, 80)
                else:
                    bg_col = (36, 39, 58) if slot_i % 2 == 0 else (30, 32, 48)
                    pygame.draw.rect(self.screen, bg_col, item_rect, border_radius=6)
                    text_col = (230, 235, 245)
                    badge_col = (255, 215, 0)

                # Skin filename text
                item_font = self.get_font(None, 24)
                if skin_name == "none":
                    display_name = "none (Procedural Retrocade)"
                else:
                    display_name = skin_name
                    if len(display_name) > 42:
                        display_name = display_name[:41] + "…"
                t_surf = item_font.render(display_name, True, text_col)
                self.screen.blit(t_surf, (item_rect.left + 20, item_rect.centery - t_surf.get_height() // 2))

                # Active indicator badge
                if is_active:
                    badge_font = self.get_font(None, 18)
                    b_surf = badge_font.render("★ SAVED", True, badge_col)
                    self.screen.blit(b_surf, (item_rect.right - b_surf.get_width() - 20, item_rect.centery - b_surf.get_height() // 2))

        # Footer control help
        footer_font = self.get_font(None, 20)
        footer_text = "▲/▼ Scroll Live Preview  |  ENTER Apply & Save  |  ESC Cancel"
        footer_surf = footer_font.render(footer_text, True, (200, 210, 230))
        self.screen.blit(footer_surf, footer_surf.get_rect(center=(cx, box_rect.bottom - 30)))

