# Google OAuth Integration - Setup Guide

## Overview
This system has been updated to use Google OAuth for authentication instead of email OTP verification. Users must have their email registered in the database before they can log in via Google.

## Changes Made

### 1. Database Changes
- **Removed columns from User table:**
  - `is_email_verified` - No longer needed
  - `email_otp_hash` - OTP verification removed
  - `email_otp_expires_at` - OTP verification removed

- **Added column to User table:**
  - `google_id` - Stores Google account identifier for OAuth

### 2. Code Changes
- Removed all OTP verification logic from login and user creation
- Added Google OAuth routes: `/auth/google` and `/auth/google/callback`
- Updated login template to include "Sign in with Google" button
- Simplified admin user creation (no more OTP verification)

### 3. Configuration
Added new environment variables in `.env`:
- `GOOGLE_CLIENT_ID` - Your Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET` - Your Google OAuth Client Secret
- `GOOGLE_REDIRECT_URI` - Callback URL (default: http://localhost:5000/auth/google/callback)

## Setup Instructions

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API (or Google Identity Platform)
4. Go to "Credentials" in the sidebar
5. Click "Create Credentials" → "OAuth 2.0 Client ID"
6. Select "Web application"
7. Add authorized redirect URI:
   - For development: `http://localhost:5000/auth/google/callback`
   - For production: `https://yourdomain.com/auth/google/callback`
8. Save and copy your Client ID and Client Secret

### Step 3: Update Environment Variables

Add to your `.env` file:
```bash
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

### Step 4: Run Database Migration

```bash
flask db upgrade
```

Or run the migration manually:
```bash
python -m flask db upgrade
```

The migration will:
- Add `google_id` column to the user table
- Drop `is_email_verified`, `email_otp_hash`, and `email_otp_expires_at` columns

## How It Works

### User Login Flow

1. **Standard Login (Username/Password):**
   - User enters username/email and password
   - System validates credentials
   - User is logged in if valid

2. **Google OAuth Login:**
   - User clicks "Sign in with Google" button
   - User is redirected to Google for authentication
   - Google redirects back with user info
   - System checks if email exists in database:
     - ✅ If exists and active → User is logged in
     - ❌ If not exists → Login blocked with error message
     - ❌ If inactive → Login blocked with error message
   - Google ID is automatically linked to user account on first login

### Security Features

- **Email must exist in database**: Users cannot create accounts via Google. Only registered users can log in.
- **Account linking**: On first Google login, the `google_id` is saved to the user's account
- **Active status check**: Inactive accounts cannot log in, even with valid Google credentials
- **Secure token handling**: Uses authlib for secure OAuth token management

### Admin User Creation

- No more OTP verification required
- Admins can directly create users with username, email, and password
- New users can then choose to log in with password or link their Google account

## Testing

1. **Test Standard Login:**
   ```
   - Go to /auth/login
   - Enter username and password
   - Should log in successfully
   ```

2. **Test Google Login (Registered User):**
   ```
   - Go to /auth/login
   - Click "Sign in with Google"
   - Authenticate with Google
   - Should log in successfully if email exists in database
   ```

3. **Test Google Login (Unregistered Email):**
   ```
   - Click "Sign in with Google"
   - Authenticate with a Google account not in database
   - Should see error: "Your email is not registered in our system"
   ```

## Troubleshooting

### Error: "redirect_uri_mismatch"
- Ensure `GOOGLE_REDIRECT_URI` in `.env` matches the URI registered in Google Cloud Console
- Check that the protocol (http/https) matches

### Error: "Invalid Google account information"
- Check that Google OAuth credentials are correct
- Verify that Google+ API is enabled

### Error: "Your email is not registered in our system"
- The user's Google email doesn't exist in the database
- Admin must create the user account first

### Users can't log in with Google
- Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set correctly
- Check application logs for detailed error messages
- Ensure the user's email in the database matches their Google email exactly

## Migration Notes

### For Existing Users
- Existing users can continue logging in with username/password
- First time using Google login, their `google_id` will be linked automatically
- No action required from users

### For Administrators
- Update `.env` file with Google OAuth credentials
- Run database migration before deploying
- Test Google login in staging environment first
- Inform users about the new Google login option

## Rollback Plan

If you need to rollback to OTP verification:
```bash
flask db downgrade
```

This will:
- Remove `google_id` column
- Restore `is_email_verified`, `email_otp_hash`, and `email_otp_expires_at` columns
- You'll need to restore the old code from git history

## Support

For issues or questions:
1. Check application logs: `logs/clinic.log`
2. Verify environment variables are set correctly
3. Test with a known working Google account
4. Review the migration was applied successfully
