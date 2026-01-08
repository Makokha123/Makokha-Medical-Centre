#!/usr/bin/env python3
"""
Database initialization script
Run this separately to initialize the database
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from app import User  # Make sure to import your models

def initialize_database():
    """Initialize database with default data"""
    with app.app_context():
        try:
            print("Creating database tables...")
            db.create_all()

            allow_seed = (os.getenv('SEED_DEFAULT_USERS', '').strip().lower() in ('1', 'true', 'yes', 'y', 'on'))
            if not allow_seed:
                print("Skipping user seeding (set SEED_DEFAULT_USERS=true to enable).")
                print("✓ Database initialized successfully!")
                return

            admin_username = (os.getenv('SEED_ADMIN_USERNAME') or '').strip() or 'Admin'
            admin_email = (os.getenv('SEED_ADMIN_EMAIL') or '').strip()
            admin_password = (os.getenv('SEED_ADMIN_PASSWORD') or '').strip()

            if not admin_email or not admin_password:
                raise RuntimeError("SEED_DEFAULT_USERS=true but SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD not provided")

            print("Creating initial admin user...")
            
            # Create default admin if not exists
            admin_exists = db.session.execute(
                db.select(User).filter_by(role='admin')
            ).scalar()
            
            if not admin_exists:
                admin = User(
                    username=admin_username,
                    email=admin_email,
                    role='admin',
                    is_active=True
                )
                admin.set_password(admin_password)
                db.session.add(admin)
                print("✓ Admin user created")
            else:
                print("✓ Admin user already exists")
            
            # Commit all changes
            db.session.commit()
            print("✓ Database initialized successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Error initializing database: {str(e)}")
            raise

if __name__ == '__main__':
    load_dotenv()  # Load environment variables
    initialize_database()