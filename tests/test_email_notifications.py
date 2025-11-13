"""
Test script for email notifications
Tests if email can be sent via Gmail SMTP
"""
import sys
from pathlib import Path
import json

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from notifications.email_notifier import EmailNotifier

def test_email_notifications():
    """Test email notifications"""
    print("=" * 60)
    print("Testing Email Notifications")
    print("=" * 60)
    
    # Load config
    project_root = Path(__file__).parent
    config_path = project_root / "config" / "config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    notifications_config = config.get("notifications", {})
    
    print(f"\n📋 Email Configuration:")
    print(f"  - Email enabled: {notifications_config.get('email_enabled', False)}")
    
    email_config = notifications_config.get("email", {})
    if email_config:
        print(f"  - SMTP Server: {email_config.get('smtp_server', 'N/A')}")
        print(f"  - SMTP Port: {email_config.get('smtp_port', 'N/A')}")
        print(f"  - Sender: {email_config.get('sender_email', 'N/A')}")
        print(f"  - Recipient: {email_config.get('recipient_email', 'N/A')}")
    else:
        print("  ⚠ Email config not found in config.json")
        return
    
    # Initialize email notifier
    print(f"\n🔧 Initializing email notifier...")
    try:
        email_notifier = EmailNotifier(notifications_config)
        print("✓ Email notifier initialized")
    except Exception as e:
        print(f"❌ Failed to initialize email notifier: {str(e)}")
        return
    
    if not email_notifier.enabled:
        print("⚠ Email notifications are disabled")
        print("   Please check config.json and ensure:")
        print("   - email_enabled: true")
        print("   - email.sender_email is set")
        print("   - email.sender_password is set (use Gmail App Password)")
        print("   - email.recipient_email is set")
        return
    
    # Test 1: Send maintenance alert
    print(f"\n📧 Test 1: Sending Betfair maintenance alert...")
    try:
        email_notifier.send_betfair_maintenance_alert(
            "UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT - Betfair is under maintenance"
        )
        print("✓ Maintenance alert email sent")
    except Exception as e:
        print(f"❌ Error sending maintenance alert: {str(e)}")
    
    # Wait a bit
    import time
    print("\n⏳ Waiting 3 seconds before next test...")
    time.sleep(3)
    
    # Test 2: Send terms confirmation alert
    print(f"\n📧 Test 2: Sending Betfair terms confirmation alert...")
    try:
        email_notifier.send_betfair_terms_confirmation_alert(
            "Terms and conditions acceptance required"
        )
        print("✓ Terms confirmation alert email sent")
    except Exception as e:
        print(f"❌ Error sending terms confirmation alert: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Email notification test completed!")
    print("=" * 60)
    print("\nPlease check your email inbox (and spam folder) for test messages.")
    print("\nNote: If you see authentication errors, make sure:")
    print("  1. You're using Gmail App Password (not regular password)")
    print("  2. 2-Step Verification is enabled on your Gmail account")
    print("  3. App Password is generated from: https://myaccount.google.com/apppasswords")

if __name__ == "__main__":
    try:
        test_email_notifications()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

