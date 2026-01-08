#!/usr/bin/env python3
"""Initialize database tables."""

from app import app, db

with app.app_context():
    # Create all tables
    db.create_all()
    print("✓ Created all database tables")
    
    # Verify backup_login_users table
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    if 'backup_login_users' in tables:
        columns = [c['name'] for c in inspector.get_columns('backup_login_users')]
        print(f"✓ backup_login_users table exists with columns: {', '.join(columns)}")
    else:
        print("✗ backup_login_users table NOT found")
    
    print(f"\nAll tables: {', '.join(sorted(tables))}")
