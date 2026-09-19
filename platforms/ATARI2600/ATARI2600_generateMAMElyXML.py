#!/usr/bin/env python3
"""
Legacy wrapper for Atari 2600 database generation.
MAMEly now uses SQLite (MAMEly.db) instead of XML.
"""
from ATARI2600_generateMAMElyDB import generate_atari_db

if __name__ == "__main__":
    print("MAMEly has migrated to SQLite. Generating MAMEly.db...")
    generate_atari_db()
