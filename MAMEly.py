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


def _config_file_from_args(argv):
    for arg in argv:
        if arg.startswith("-config="):
            return arg.split("=", 1)[1]
    return "config.xml"


if __name__ == "__main__":
    if "--config-map" in sys.argv:
        from diagnostics import CONFIG_MAP
        print(CONFIG_MAP.strip())
        sys.exit(0)

    if "--check" in sys.argv:
        from diagnostics import check_all, print_report, has_errors, CONFIG_MAP
        config_file = _config_file_from_args(sys.argv)
        issues = check_all(current_dir, config_file)
        print_report(issues)
        print("\n" + CONFIG_MAP.strip())
        sys.exit(1 if has_errors(issues) else 0)

    try:
        from main import MAMElyApp
    except ImportError as e:
        print(f"Error starting MAMEly: {e}")
        sys.exit(1)

    app = MAMElyApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Application crashed: {e}")
        # In a real app we might log this or show a dialog
