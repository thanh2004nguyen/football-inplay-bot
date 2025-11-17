"""
Test script for Telegram notifications
Tests if messages can be sent via Telegram Bot API to chat room
"""
import sys
from pathlib import Path
import json
import requests

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_telegram_basic():
    """Test basic Telegram message sending to verify connection to chat room"""
    print("=" * 60)
    print("Testing Telegram Connection")
    print("=" * 60)
    
    # Load config
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    notifications_config = config.get("notifications", {})
    telegram_config = notifications_config.get("telegram", {})
    
    print(f"\n📋 Telegram Configuration:")
    print(f"  - Telegram enabled: {notifications_config.get('telegram_enabled', False)}")
    print(f"  - Bot Token: {telegram_config.get('bot_token', 'N/A')[:20]}..." if telegram_config.get('bot_token') else "  - Bot Token: Not set")
    print(f"  - Chat ID: {telegram_config.get('chat_id', 'N/A')}")
    
    if not telegram_config.get("bot_token") or not telegram_config.get("chat_id"):
        print("\n⚠ Telegram configuration incomplete!")
        print("   Please add to config.json:")
        print('   "notifications": {')
        print('     "telegram_enabled": true,')
        print('     "telegram": {')
        print('       "bot_token": "YOUR_BOT_TOKEN",')
        print('       "chat_id": "YOUR_CHAT_ID"')
        print('     }')
        print('   }')
        return
    
    bot_token = telegram_config.get("bot_token")
    chat_id = telegram_config.get("chat_id")
    
    # Test: Send simple test message
    print(f"\n📱 Sending test message to verify connection...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "🧪 This is a test message to verify connection to chat room.\n\nIf you receive this message, Telegram connection is working!"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            print("✅ Message sent successfully!")
            print(f"   Message ID: {result.get('result', {}).get('message_id', 'N/A')}")
            print("\n" + "=" * 60)
            print("✅ Telegram connection is working!")
            print("=" * 60)
            print("\nPlease check your Telegram app to confirm you received the message.")
        else:
            error_desc = result.get('description', 'Unknown error')
            print(f"❌ Failed to send message: {error_desc}")
            
            if "chat not found" in error_desc.lower():
                print("\n💡 Suggestion: Make sure you have:")
                print("   1. Found the bot on Telegram (e.g., @my_betfair_bot)")
                print("   2. Clicked 'Start' or sent /start")
                print("   3. Checked that Chat ID in config.json is correct")
            elif "unauthorized" in error_desc.lower() or "invalid token" in error_desc.lower():
                print("\n💡 Suggestion: Check that Bot Token in config.json is correct")
            return
    except requests.exceptions.Timeout:
        print("❌ Error: Timeout when connecting to Telegram API")
        print("   Please check your internet connection")
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to Telegram API")
        print("   Please check your internet connection")
    except Exception as e:
        print(f"❌ Error sending message: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        test_telegram_basic()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

