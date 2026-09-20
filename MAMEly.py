#!/usr/bin/env python3
"""
MAMEly Bootstrap Script
This script launches the refactored main application.
"""
import sys
import os
from mamely_log import setup_logging, get_logger

# Ensure the current directory is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Ensure GLX compatibility with Mesa fallback for systems with problematic NV-GLX drivers
os.environ["__GLX_VENDOR_LIBRARY_NAME"] = "mesa"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"


def _config_file_from_args(argv):
    for i, arg in enumerate(argv):
        if arg.startswith("--config="):
            return arg.split("=", 1)[1]
        elif arg == "--config" and i + 1 < len(argv):
            return argv[i + 1]
    return "config.xml"


if __name__ == "__main__":
    setup_logging(current_dir)
    log = get_logger("boot")

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
        log.error("Error starting MAMEly: %s", e)
        sys.exit(1)

    app = MAMElyApp()
    try:
        app.run()
    except KeyboardInterrupt:
        log.info("interrupted")
    except Exception:
        log.exception("Application crashed")
