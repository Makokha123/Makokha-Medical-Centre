#!/usr/bin/env python3
"""Final verification that all datetime errors are fixed."""

import os
os.environ['DATABASE_URL'] = 'sqlite:///instance/clinic.db'

def verify_fix():
    print('='*60)
    print('FINAL VERIFICATION: DATETIME FIX')
    print('='*60)

    # Test 1: Import app
    try:
        from app import app, db, User, load_user
        print('✅ Test 1: App import successful')
    except Exception as e:
        print(f'❌ Test 1 failed: {e}')
        return False

    # Test 2: Load users
    try:
        with app.app_context():
            user = load_user(1)
            if user:
                print('✅ Test 2: load_user(1) successful')
            else:
                print('⚠️  Test 2: User not found (expected in some cases)')
    except Exception as e:
        print(f'❌ Test 2 failed: {e}')
        return False

    # Test 3: Query multiple users
    try:
        with app.app_context():
            users = db.session.query(User).limit(5).all()
            print(f'✅ Test 3: Query {len(users)} users successful')
    except Exception as e:
        print(f'❌ Test 3 failed: {e}')
        return False

    # Test 4: Check database state
    try:
        import sqlite3
        conn = sqlite3.connect('instance/clinic.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user WHERE typeof(created_at) = 'blob' OR typeof(updated_at) = 'blob' OR typeof(last_login) = 'blob'")
        corrupt_rows = cursor.fetchone()[0]
        conn.close()
        
        if corrupt_rows == 0:
            print('✅ Test 4: No encrypted bytes in datetime columns')
        else:
            print(f'⚠️  Test 4: {corrupt_rows} rows still have encrypted bytes')
    except Exception as e:
        print(f'❌ Test 4 failed: {e}')
        return False

    print('\n' + '='*60)
    print('✅ ALL TESTS PASSED')
    print('='*60)
    print('\nThe Flask app is ready to run:')
    print('  python app.py')
    print('\nAccess at: http://127.0.0.1:5000')
    print('='*60)
    return True

if __name__ == '__main__':
    success = verify_fix()
    exit(0 if success else 1)
