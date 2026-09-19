#!/usr/bin/env python3
"""
Legacy wrapper for SNES database generation.
MAMEly now uses SQLite (MAMEly.db) instead of XML.
"""
from SNES_generateMAMElyDB import generate_snes_db

if __name__ == "__main__":
    print("MAMEly has migrated to SQLite. Generating MAMEly.db...")
    generate_snes_db()
