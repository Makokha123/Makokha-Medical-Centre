#!/usr/bin/env python3
"""
Fix datetime columns in SQLite database that contain NULL or invalid values.
This script updates all datetime columns to ensure they contain valid datetime values.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

# Find the SQLite database file
def find_sqlite_db():
    """Locate the SQLite database file."""
    possible_paths = [
        'instance/clinic.db',
        Path(__file__).parent / 'instance' / 'clinic.db',
    ]
    
    for path in possible_paths:
        db_path = Path(path)
        if db_path.exists():
            return str(db_path)
    
    return None

def fix_datetime_columns():
    """Fix all datetime columns in the database."""
    db_path = find_sqlite_db()
    
    if not db_path:
        print("❌ SQLite database not found")
        return False
    
    print(f"📦 Found database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        tables = cursor.fetchall()
        
        datetime_columns_fixed = 0
        null_values_cleared = 0
        
        for (table_name,) in tables:
            try:
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                for col_id, col_name, col_type, not_null, default_val, pk in columns:
                    # Check if this is a datetime column
                    if col_type.upper() in ('DATETIME', 'TIMESTAMP'):
                        print(f"\n  🔍 Checking {table_name}.{col_name} ({col_type})")
                        
                        # Find NULL values
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table_name} WHERE {col_name} IS NULL"
                        )
                        null_count = cursor.fetchone()[0]
                        
                        if null_count > 0:
                            print(f"     Found {null_count} NULL values")
                            # Set NULL values to current time
                            cursor.execute(
                                f"UPDATE {table_name} SET {col_name} = datetime('now') WHERE {col_name} IS NULL"
                            )
                            null_values_cleared += null_count
                            datetime_columns_fixed += 1
                        
                        # Find empty strings
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table_name} WHERE {col_name} = ''"
                        )
                        empty_count = cursor.fetchone()[0]
                        
                        if empty_count > 0:
                            print(f"     Found {empty_count} empty string values")
                            cursor.execute(
                                f"UPDATE {table_name} SET {col_name} = datetime('now') WHERE {col_name} = ''"
                            )
                            null_values_cleared += empty_count
                            datetime_columns_fixed += 1
                        
                        # Check for invalid datetime strings
                        try:
                            cursor.execute(
                                f"SELECT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL AND {col_name} != '' LIMIT 5"
                            )
                            sample_values = cursor.fetchall()
                            
                            invalid_count = 0
                            for (value,) in sample_values:
                                if value and isinstance(value, str):
                                    try:
                                        # Try to parse as ISO format
                                        datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    except (ValueError, TypeError):
                                        invalid_count += 1
                            
                            if invalid_count > 0:
                                print(f"     ⚠️  Found {invalid_count} invalid datetime strings")
                                # Replace invalid values
                                cursor.execute(
                                    f"UPDATE {table_name} SET {col_name} = datetime('now') WHERE {col_name} NOT LIKE '%-%-% %:%:%' AND {col_name} IS NOT NULL AND {col_name} != ''"
                                )
                                datetime_columns_fixed += 1
                        except Exception as e:
                            print(f"     ⚠️  Could not validate sample values: {e}")
                            
            except Exception as e:
                print(f"  ❌ Error processing table {table_name}: {e}")
                continue
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print(f"\n✅ Datetime column fixes applied:")
        print(f"   - Tables processed: {len(tables)}")
        print(f"   - Datetime columns fixed: {datetime_columns_fixed}")
        print(f"   - NULL/empty values cleared: {null_values_cleared}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("🔧 SQLite Datetime Column Fixer\n")
    success = fix_datetime_columns()
    exit(0 if success else 1)
