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
            
            print("Creating default users...")
            
            # Create default admin if not exists
            admin_exists = db.session.execute(
                db.select(User).filter_by(role='admin')
            ).scalar()
            
            if not admin_exists:
                admin = User(
                    username='Makokha Nelson',
                    email='makokhanelson4@gmail.com',
                    role='admin',
                    is_active=True
                )
                admin.set_password('Doc.makokha@2024')
                db.session.add(admin)
                print("✓ Admin user created")
            else:
                print("✓ Admin user already exists")
            
            # Create default doctor if not exists
            doctor_exists = db.session.execute(
                db.select(User).filter_by(role='doctor')
            ).scalar()
            
            if not doctor_exists:
                doctor = User(
                    username='Default Doctor',
                    email='doctor@clinic.com',
                    role='doctor',
                    is_active=True
                )
                doctor.set_password('Doctor@123')
                db.session.add(doctor)
                print("✓ Doctor user created")
            else:
                print("✓ Doctor user already exists")
            
            # Create default pharmacist if not exists
            pharmacist_exists = db.session.execute(
                db.select(User).filter_by(role='pharmacist')
            ).scalar()
            
            if not pharmacist_exists:
                pharmacist = User(
                    username='Default Pharmacist',
                    email='pharmacist@clinic.com',
                    role='pharmacist',
                    is_active=True
                )
                pharmacist.set_password('Pharmacist@123')
                db.session.add(pharmacist)
                print("✓ Pharmacist user created")
            else:
                print("✓ Pharmacist user already exists")
            
            # Create default receptionist if not exists
            receptionist_exists = db.session.execute(
                db.select(User).filter_by(role='receptionist')
            ).scalar()
            
            if not receptionist_exists:
                receptionist = User(
                    username='Default Receptionist',
                    email='receptionist@clinic.com',
                    role='receptionist',
                    is_active=True
                )
                receptionist.set_password('Receptionist@123')
                db.session.add(receptionist)
                print("✓ Receptionist user created")
            else:
                print("✓ Receptionist user already exists")
            
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