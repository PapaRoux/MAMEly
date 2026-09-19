#!/usr/bin/env python3
"""
Legacy wrapper for N64 database generation.
MAMEly now uses SQLite (MAMEly.db) instead of XML.
"""
from N64_generateMAMElyDB import generate_n64_db

if __name__ == "__main__":
    print("MAMEly has migrated to SQLite. Generating MAMEly.db...")
    generate_n64_db()
