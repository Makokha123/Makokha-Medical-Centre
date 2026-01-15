#!/usr/bin/env python3
"""Decrypt or clear encrypted datetime columns in SQLite database."""

import sqlite3
from app import app, EncryptionUtils
from cryptography.fernet import InvalidToken

def decrypt_field(encrypted_bytes):
    """Try to decrypt a field using the app's Fernet key."""
    try:
        if not encrypted_bytes or not isinstance(encrypted_bytes, bytes):
            return None
        
        # Use the app's EncryptionUtils
        with app.app_context():
            cipher = EncryptionUtils.get_cipher()
            if cipher:
                decrypted = cipher.decrypt(encrypted_bytes)
                return decrypted.decode('utf-8')
    except (InvalidToken, AttributeError, ValueError, TypeError):
        pass
    
    return None

def fix_encrypted_datetimes():
    """Fix encrypted datetime columns."""
    conn = sqlite3.connect('instance/clinic.db')
    cursor = conn.cursor()
    
    print("🔧 Fixing encrypted datetime columns\n")
    
    # Get all encrypted datetime fields
    cursor.execute("SELECT id, created_at, updated_at FROM user WHERE typeof(created_at) = 'blob'")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} rows with encrypted datetime values")
    
    fixed = 0
    for user_id, created_at_encrypted, updated_at_encrypted in rows:
        print(f"\nUser {user_id}:")
        
        # Try to decrypt created_at
        if created_at_encrypted:
            decrypted = decrypt_field(created_at_encrypted)
            if decrypted:
                print(f"  ✅ Decrypted created_at: {decrypted}")
                cursor.execute("UPDATE user SET created_at = ? WHERE id = ?", (decrypted, user_id))
                fixed += 1
            else:
                print(f"  ❌ Could not decrypt created_at, clearing to NULL")
                cursor.execute("UPDATE user SET created_at = NULL WHERE id = ?", (user_id,))
                fixed += 1
        
        # Try to decrypt updated_at
        if updated_at_encrypted:
            decrypted = decrypt_field(updated_at_encrypted)
            if decrypted:
                print(f"  ✅ Decrypted updated_at: {decrypted}")
                cursor.execute("UPDATE user SET updated_at = ? WHERE id = ?", (decrypted, user_id))
                fixed += 1
            else:
                print(f"  ❌ Could not decrypt updated_at, clearing to NULL")
                cursor.execute("UPDATE user SET updated_at = NULL WHERE id = ?", (user_id,))
                fixed += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Fixed {fixed} encrypted datetime values")
    return True

if __name__ == '__main__':
    fix_encrypted_datetimes()
