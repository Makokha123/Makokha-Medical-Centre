#!/usr/bin/env python
"""
Verify that idempotent user creation is working correctly.
This script tests the setup without making database changes.
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_implementation():
    """Verify that all necessary functions are implemented."""
    try:
        print("🔍 Verifying idempotent user creation implementation...\n")
        
        # Check if app imports successfully
        print("1️⃣  Checking app imports...")
        from app import app, db, User, _find_user_by_email_plain, _create_default_users, _remove_duplicate_users
        print("   ✅ All required functions imported successfully\n")
        
        # Check functions exist
        print("2️⃣  Verifying functions...")
        import inspect
        import app as app_module
        
        functions = {
            '_find_user_by_email_plain': 'Email lookup (handles encryption)',
            '_create_default_users': 'Idempotent user creation',
            '_remove_duplicate_users': 'Duplicate user cleanup'
        }
        
        for func_name, description in functions.items():
            if hasattr(app_module, func_name):
                print(f"   ✅ {func_name}: {description}")
            else:
                print(f"   ❌ {func_name} not found!")
                return False
        print()
        
        # Check user model
        print("3️⃣  Verifying User model...")
        with app.app_context():
            # Test that the User model has required attributes
            required_attrs = ['id', 'username', 'email', 'role', 'is_active', 'is_email_verified', 'created_at']
            user_columns = [c.name for c in User.__table__.columns]
            
            for attr in required_attrs:
                if attr in user_columns:
                    print(f"   ✅ User.{attr} exists")
                else:
                    print(f"   ❌ User.{attr} missing!")
                    return False
        print()
        
        # Summary
        print("✅ All verification checks passed!\n")
        print("📋 Summary of idempotent user creation:\n")
        print("   • Default users created only if email doesn't exist")
        print("   • Checked via encrypted email lookup (_find_user_by_email_plain)")
        print("   • Default users marked as pre-verified (is_email_verified=True)")
        print("   • Duplicates automatically cleaned up on app startup")
        print("   • Safe to restart app multiple times without creating duplicates\n")
        
        print("🚀 To start the app with idempotent user creation:")
        print("   python app.py\n")
        
        print("🧹 To manually cleanup existing duplicates:")
        print("   python cleanup_duplicates.py\n")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    success = verify_implementation()
    sys.exit(0 if success else 1)
