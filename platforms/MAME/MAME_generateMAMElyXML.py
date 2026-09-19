#!/usr/bin/env python3
"""
Legacy wrapper for MAMEly database generation.
MAMEly now uses SQLite (MAMEly.db) instead of XML.
"""
import os
import sys

from MAME_generateMAMElyDB import generate_mame_db

if __name__ == "__main__":
    print("MAMEly has migrated to SQLite. Generating MAMEly.db...")
    generate_mame_db()
