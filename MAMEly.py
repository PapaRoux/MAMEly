#!/usr/bin/env python3
"""
MAMEly Bootstrap Script
This script launches the refactored main application.
"""
import sys
import os

# Ensure the current directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from main import MAMElyApp
except ImportError as e:
    print(f"Error starting MAMEly: {e}")
    sys.exit(1)

if __name__ == "__main__":
    app = MAMElyApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Application crashed: {e}")
        # In a real app we might log this or show a dialog
