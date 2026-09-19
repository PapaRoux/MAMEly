#!/usr/bin/env python3
"""
Legacy wrapper for Sega Master System database generation.
MAMEly now uses SQLite (MAMEly.db) instead of XML.
"""
from SEGAMASTER_generateMAMElyDB import generate_segamaster_db

if __name__ == "__main__":
    print("MAMEly has migrated to SQLite. Generating MAMEly.db...")
    generate_segamaster_db()
