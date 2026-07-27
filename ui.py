import pygame
import os
import math
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

        # Video Capture State
        self.video_cap = None
        self.current_video_path = None
        self.last_video_frame_surf = None

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

    def draw_text(self, text, x, y, font_name, size, color, shadow_color=None, shadow=False, truncate_len=0, centered=True, align=None):
        """Draw text. With centered=True, y is the vertical middle and `align`
        picks the horizontal anchor: 'left' treats x as the left edge, 'right'
        as the right edge, 'center' (default) as the midpoint."""
        if x is None or y is None:
            # Skip drawing if coordinates are missing
            return

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
                        self.video_cap = None
                except Exception as e:
                    print(f"Error opening video: {e}")
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
            print(f"Error rendering video frame: {e}")
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
        line_height = 28
        font = self.get_font(None, font_size)
        max_visible = (panel_h - 50) // line_height
        visible = lines[scroll_line:scroll_line + max_visible]

        y = margin + 20
        for line in visible:
            color = (255, 255, 100) if line.startswith("MAMEly") else (220, 220, 220)
            if line.startswith("  !"):
                color = (255, 120, 120)
            elif line.startswith("  ?"):
                color = (255, 200, 120)
            elif line in ("Paths", "Emulator", "Controls", "Settings live in:", "Troubleshooting:", "Issues"):
                color = (180, 220, 255)

            text_surf = font.render(line, True, color)
            self.screen.blit(text_surf, (margin + 20, y))
            y += line_height

        footer = "F1 or Esc to close"
        if len(lines) > max_visible:
            footer += f"   |   Up/Down scroll ({scroll_line + 1}-{min(scroll_line + max_visible, len(lines))} of {len(lines)})"
        footer_surf = font.render(footer, True, (160, 160, 160))
        self.screen.blit(footer_surf, (margin + 20, margin + panel_h - 35))

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
