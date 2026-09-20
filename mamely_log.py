"""MAMEly application logging.

Writes a rotating file log for debugging and session analysis, and mirrors
INFO+ to stdout so the old print() chatter still shows in a terminal.

  mamely.log     MAMEly events (this module)
  debug.log      emulator stdout/stderr, written by main.run_rom

Override console verbosity with MAMELY_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR.
The file always records DEBUG and above.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FILENAME = "mamely.log"
LOGGER_NAME = "mamely"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3

_configured = False


def _level_from_env(default=logging.INFO):
    raw = os.environ.get("MAMELY_LOG_LEVEL", "").strip().upper()
    if not raw:
        return default
    return getattr(logging, raw, default)


def setup_logging(base_path, console_level=None, file_level=logging.DEBUG):
    """Attach rotating-file and console handlers to the `mamely` logger."""
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured and logger.handlers:
        return logger

    if console_level is None:
        console_level = _level_from_env(logging.INFO)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_path = os.path.join(base_path, LOG_FILENAME)
    file_ok = False
    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        file_ok = True
    except OSError:
        pass

    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    _configured = True
    if file_ok:
        logger.info("logging to %s", log_path)
    else:
        logger.warning("could not write %s; console logging only", log_path)
    return logger


def get_logger(name=None):
    """Return the app logger, or a child such as mamely.main."""
    if not name or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)
    if name.startswith(LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
