import pygame
import time

class InputManager:
    def __init__(self):
        # Action Constants
        self.ACTION_NONE = 0
        self.ACTION_UP = 1
        self.ACTION_DOWN = 2
        self.ACTION_LEFT = 3
        self.ACTION_RIGHT = 4
        self.ACTION_PLATFORM = 5
        self.ACTION_FAVORITE = 6
        self.ACTION_GENRE = 7
        self.ACTION_IGNORE = 8
        self.ACTION_RUN = 9
        self.ACTION_EXIT = 10
        self.ACTION_PAGE_UP = 11
        self.ACTION_PAGE_DOWN = 12

        # Initialize Joysticks
        pygame.joystick.init()
        self.joysticks = []
        for i in range(pygame.joystick.get_count()):
             j = pygame.joystick.Joystick(i)
             j.init()
             self.joysticks.append(j)

        # Timers for repeat suppression
        self.last_action_time = 0
        self.repeat_delay = 0.05  # Faster scrolling (was 0.2)
        self.first_repeat_delay = 0.25 # Snappier initial hold (was 0.5)
        self.current_action = self.ACTION_NONE
        self.hold_start_time = 0

    def get_action(self):
        """Process inputs and return the highest priority action."""
        
        # Poll events (needed for pygame internal state)
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                return self.ACTION_EXIT
            elif event.type == pygame.KEYDOWN:
                # Handle single press events immediately if needed, 
                # but we'll mostly rely on state checking for continuous movement
                if event.key == pygame.K_ESCAPE:
                    return self.ACTION_EXIT
                elif event.key == pygame.K_TAB:
                     # Clear queue on tab like original?
                     pygame.event.clear()

        # Check raw states for hold/repeat
        keys = pygame.key.get_pressed()
        
        # Keyboard Map
        action = self.ACTION_NONE
        
        if keys[pygame.K_UP]: action = self.ACTION_UP
        elif keys[pygame.K_DOWN]: action = self.ACTION_DOWN
        elif keys[pygame.K_LEFT]: action = self.ACTION_LEFT
        elif keys[pygame.K_RIGHT]: action = self.ACTION_RIGHT
        elif keys[pygame.K_PAGEUP]: action = self.ACTION_PAGE_UP
        elif keys[pygame.K_PAGEDOWN]: action = self.ACTION_PAGE_DOWN
        elif keys[pygame.K_RETURN]: action = self.ACTION_RUN
        elif keys[pygame.K_e]: action = self.ACTION_PLATFORM
        elif keys[pygame.K_f]: action = self.ACTION_FAVORITE
        elif keys[pygame.K_TAB]: action = self.ACTION_GENRE
        elif keys[pygame.K_i]: action = self.ACTION_IGNORE
        
        # Joystick Map override
        if action == self.ACTION_NONE:
            for joy in self.joysticks:
                # Axis 1 (Up/Down)
                try:
                    if joy.get_axis(1) < -0.5: action = self.ACTION_UP
                    elif joy.get_axis(1) > 0.5: action = self.ACTION_DOWN
                    # Axis 0 (Left/Right)
                    elif joy.get_axis(0) < -0.5: action = self.ACTION_LEFT
                    elif joy.get_axis(0) > 0.5: action = self.ACTION_RIGHT
                    
                    # Hats
                    if joy.get_numhats() > 0:
                        hat = joy.get_hat(0)
                        if hat[1] == 1: action = self.ACTION_UP
                        elif hat[1] == -1: action = self.ACTION_DOWN
                        elif hat[0] == -1: action = self.ACTION_LEFT
                        elif hat[0] == 1: action = self.ACTION_RIGHT
                        
                    # Buttons (Mapping based on original)
                    # 0: Run, 1: Genre, 2: Platform, 3: Favorite
                    if joy.get_button(0): action = self.ACTION_RUN
                    elif joy.get_button(1): action = self.ACTION_GENRE
                    elif joy.get_button(2): action = self.ACTION_PLATFORM
                    elif joy.get_button(3): action = self.ACTION_FAVORITE
                except:
                    pass
        
        # Repeat Logic
        current_time = time.time()
        
        if action == self.ACTION_NONE:
            self.current_action = self.ACTION_NONE
            self.hold_start_time = 0
            return self.ACTION_NONE
            
        if action != self.current_action:
            # New action
            self.current_action = action
            self.hold_start_time = current_time
            self.last_action_time = current_time
            return action
        else:
            # Holding same action
            hold_duration = current_time - self.hold_start_time
            time_since_last = current_time - self.last_action_time
            
            if hold_duration > self.first_repeat_delay:
                 if time_since_last > self.repeat_delay:
                     self.last_action_time = current_time
                     return action
                     
        return self.ACTION_NONE
