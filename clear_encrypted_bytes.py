#!/usr/bin/env python3
"""Clear encrypted bytes from the last_login column."""
import sqlite3

conn = sqlite3.connect('instance/clinic.db')
cursor = conn.cursor()

# SQLite's typeof() function to detect blob type
cursor.execute("SELECT id, last_login FROM user WHERE typeof(last_login) = 'blob'")
rows = cursor.fetchall()

print(f"Found {len(rows)} rows with blob data in last_login column")

if rows:
    for user_id, value in rows:
        print(f"  Clearing user_id={user_id}")
    
    cursor.execute("UPDATE user SET last_login = NULL WHERE typeof(last_login) = 'blob'")
    conn.commit()
    print(f"Updated {cursor.rowcount} rows")

conn.close()
print("✅ Done")
