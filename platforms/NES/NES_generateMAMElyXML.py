#!/usr/bin/env python3
"""
Legacy wrapper for NES database generation.
MAMEly now uses SQLite (MAMEly.db) instead of XML.
"""
from NES_generateMAMElyDB import generate_nes_db

if __name__ == "__main__":
    print("MAMEly has migrated to SQLite. Generating MAMEly.db...")
    generate_nes_db()
