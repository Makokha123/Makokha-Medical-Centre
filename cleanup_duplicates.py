#!/usr/bin/env python
"""
Cleanup script to remove duplicate users from the database.
Run this once to clean up any existing duplicates, then the app will maintain idempotency.

Usage: python cleanup_duplicates.py
"""
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, _find_user_by_email_plain

def cleanup_duplicate_users():
    """Remove duplicate users, keeping only the first one (lowest ID) for each email."""
    with app.app_context():
        try:
            # Get all users
            all_users = User.query.all()
            print(f"\n📊 Total users in database: {len(all_users)}")
            
            # Group by email and find duplicates
            emails_seen = {}
            duplicates = []
            
            for user in all_users:
                try:
                    user_email = str(user.email).strip().lower()
                    
                    if user_email in emails_seen:
                        existing_user_id = emails_seen[user_email]['id']
                        existing_user_created = emails_seen[user_email]['created_at']
                        
                        # Keep the one created first (lower ID)
                        if user.id > existing_user_id:
                            duplicates.append({
                                'id': user.id,
                                'email': user_email,
                                'keep_id': existing_user_id
                            })
                        else:
                            # Current user is older, keep it and mark the previous as duplicate
                            old_duplicate = duplicates[-1] if duplicates else None
                            if old_duplicate and old_duplicate['email'] == user_email:
                                duplicates[-1] = {
                                    'id': existing_user_id,
                                    'email': user_email,
                                    'keep_id': user.id
                                }
                            else:
                                duplicates.append({
                                    'id': existing_user_id,
                                    'email': user_email,
                                    'keep_id': user.id
                                })
                            emails_seen[user_email] = {'id': user.id, 'created_at': user.id}
                    else:
                        emails_seen[user_email] = {'id': user.id, 'created_at': user.id}
                except Exception as e:
                    print(f"⚠️  Error processing user {user.id}: {e}")
                    continue
            
            # Display duplicates found
            if duplicates:
                print(f"\n🔍 Found {len(duplicates)} duplicate user(s):\n")
                for dup in duplicates:
                    print(f"  ❌ User ID {dup['id']} (email: {dup['email']}) - will DELETE, keeping ID {dup['keep_id']}")
                
                # Confirm deletion
                response = input("\n⚠️  Delete duplicate users? (yes/no): ").strip().lower()
                if response in ['yes', 'y']:
                    deleted_count = 0
                    for dup in duplicates:
                        try:
                            user_to_delete = User.query.get(dup['id'])
                            if user_to_delete:
                                print(f"  🗑️  Deleting user ID {dup['id']}...")
                                db.session.delete(user_to_delete)
                                deleted_count += 1
                        except Exception as e:
                            print(f"  ❌ Failed to delete user {dup['id']}: {e}")
                    
                    if deleted_count > 0:
                        db.session.commit()
                        print(f"\n✅ Successfully deleted {deleted_count} duplicate user(s)")
                    else:
                        print("\n❌ No users were deleted")
                else:
                    print("\n⏭️  Cleanup cancelled")
            else:
                print("\n✅ No duplicate users found!")
            
            # Show final count
            final_count = User.query.count()
            print(f"\n📊 Final user count: {final_count}\n")
            
        except Exception as e:
            print(f"\n❌ Error during cleanup: {e}")
            db.session.rollback()
            sys.exit(1)

if __name__ == '__main__':
    cleanup_duplicate_users()
