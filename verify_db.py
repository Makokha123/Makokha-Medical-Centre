#!/usr/bin/env python
"""Verify database file and tables."""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(BASE_DIR, 'instance', 'clinic.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    print(f'✓ Database file exists at: {db_path}')
    print(f'✓ Total tables: {len(tables)}')
    if tables:
        print(f'✓ First 10 tables: {[t[0] for t in tables[:10]]}')
        # Check for user table
        user_tables = [t[0] for t in tables if 'user' in t[0].lower()]
        print(f'✓ User-related tables: {user_tables}')
    conn.close()
else:
    print(f'✗ Database file does not exist at: {db_path}')
