#!/usr/bin/env python3
"""
Test Email Configuration and Sending
This script helps diagnose email sending issues with Resend.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment first
from dotenv import load_dotenv
load_dotenv()

def check_config():
    """Check current email configuration."""
    print("=" * 70)
    print("EMAIL CONFIGURATION CHECK")
    print("=" * 70)
    
    api_key = os.getenv("RESEND_API_KEY", "")
    from_address = os.getenv("RESEND_FROM", "")
    reply_to = os.getenv("RESEND_REPLY_TO", "")
    
    print(f"\n📧 Resend Configuration:")
    print(f"  • API Key: {'✓ Set' if api_key else '✗ Missing'} ({len(api_key)} chars)")
    print(f"  • From Address: {from_address or '✗ Not set'}")
    print(f"  • Reply-To: {reply_to or '(default)'}")
    
    # Check for test domain
    if 'onboarding@resend.dev' in from_address.lower() or 'resend.dev' in from_address.lower():
        print("\n" + "⚠" * 35)
        print("⚠  WARNING: USING RESEND TEST DOMAIN  ⚠")
        print("⚠" * 35)
        print("\n🚨 CRITICAL ISSUE DETECTED:")
        print("   You are using Resend's test domain (onboarding@resend.dev)")
        print("\n❌ Limitation:")
        print("   Emails will ONLY be sent to email addresses that are:")
        print("   • Verified in your Resend dashboard")
        print("   • Explicitly whitelisted for testing")
        print("\n✅ Solution:")
        print("   1. Add your own domain to Resend:")
        print("      → https://resend.com/domains")
        print("   2. Update RESEND_FROM in .env file:")
        print("      → RESEND_FROM=Makokha Medical Centre <noreply@yourdomain.com>")
        print("   3. Restart the application")
        print("\n📖 Full setup guide: RESEND_DOMAIN_SETUP.md")
        print("=" * 70)
        return False
    else:
        print("\n✅ Production domain configured!")
        return True

def test_email_send(recipient: str = None):
    """Test sending an email."""
    from app import app, _email_sender, _resend_config
    
    if not recipient:
        recipient = input("\n📬 Enter recipient email to test: ").strip()
    
    if not recipient or '@' not in recipient:
        print("❌ Invalid email address")
        return
    
    with app.app_context():
        if not _email_sender.is_healthy():
            print("\n❌ Email sender not configured properly")
            return
        
        print(f"\n📤 Sending test email to: {recipient}")
        print("   Please wait...")
        
        result = _email_sender.send(
            recipient=recipient,
            subject="Test Email - Makokha Medical Centre",
            html_body="""
                <h2>Test Email</h2>
                <p>This is a test email from Makokha Medical Centre system.</p>
                <p>If you received this, your email configuration is working correctly!</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    Sent from Makokha Medical Centre Email System
                </p>
            """,
            text_body="This is a test email from Makokha Medical Centre system.",
        )
        
        print("\n" + "=" * 70)
        if result.success:
            print("✅ EMAIL SENT SUCCESSFULLY!")
            print(f"   Recipient: {recipient}")
            print(f"   Attempts: {result.attempt_count}")
            print("\n📬 Check the recipient's inbox (and spam folder)")
        else:
            print("❌ EMAIL SEND FAILED")
            print(f"   Error: {result.error}")
            print(f"   Attempts: {result.attempt_count}")
            print(f"   Error Code: {result.last_error_code}")
            
            if 'onboarding@resend.dev' in _resend_config.from_address.lower():
                print("\n⚠️  Likely cause: Using test domain")
                print(f"   {recipient} must be verified in Resend dashboard")
                print("   OR set up production domain (see RESEND_DOMAIN_SETUP.md)")
        print("=" * 70)

def verify_emails_in_resend():
    """Show instructions for verifying emails in Resend dashboard."""
    print("\n" + "=" * 70)
    print("HOW TO VERIFY EMAILS IN RESEND (TEMPORARY SOLUTION)")
    print("=" * 70)
    print("\n📝 Steps:")
    print("   1. Go to: https://resend.com/overview")
    print("   2. Navigate to: Settings → Verified Emails")
    print("   3. Click: 'Add Email Address'")
    print("   4. Enter the email address you want to send to")
    print("   5. Check that email's inbox for verification link")
    print("   6. Click the verification link")
    print("   7. Now that email will receive test emails")
    print("\n⚠️  Note: This is only for development/testing")
    print("   For production, you MUST set up your own domain")
    print("   See: RESEND_DOMAIN_SETUP.md")
    print("=" * 70)

def main():
    """Main menu."""
    config_ok = check_config()
    
    while True:
        print("\n" + "=" * 70)
        print("EMAIL TESTING MENU")
        print("=" * 70)
        print("\n1. Check configuration")
        print("2. Send test email")
        print("3. How to verify emails in Resend (test domain)")
        print("4. View setup guide")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            check_config()
        elif choice == "2":
            test_email_send()
        elif choice == "3":
            verify_emails_in_resend()
        elif choice == "4":
            guide_path = Path(__file__).parent / "RESEND_DOMAIN_SETUP.md"
            if guide_path.exists():
                print(f"\n📖 Setup guide: {guide_path}")
                print("   Open this file for detailed instructions")
            else:
                print("\n❌ Setup guide not found: RESEND_DOMAIN_SETUP.md")
        elif choice == "5":
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid option")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
