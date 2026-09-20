#!/usr/bin/env python3
"""Tests for mamely_log setup and file output."""
import logging
import os
import tempfile

import mamely_log


def _reset_logger():
    mamely_log._configured = False
    logger = logging.getLogger(mamely_log.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_setup_logging_writes_info_and_debug():
    _reset_logger()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            mamely_log.setup_logging(tmp, console_level=logging.CRITICAL)
            log = mamely_log.get_logger("test")
            log.info("hello event rom=%s", "pacman")
            log.debug("debug event")
            for handler in logging.getLogger(mamely_log.LOGGER_NAME).handlers:
                handler.flush()
            path = os.path.join(tmp, mamely_log.LOG_FILENAME)
            assert os.path.isfile(path)
            text = open(path, encoding="utf-8").read()
            assert "hello event rom=pacman" in text
            assert "debug event" in text
            assert "logging to" in text
        finally:
            _reset_logger()


if __name__ == "__main__":
    test_setup_logging_writes_info_and_debug()
    print("All logging tests passed.")
