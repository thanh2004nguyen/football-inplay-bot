"""
Test script for Telegram notifications
Tests if messages can be sent via Telegram Bot API
"""
import sys
from pathlib import Path
import json
import requests
import time
from datetime import datetime

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_telegram_basic():
    """Test basic Telegram message sending"""
    print("=" * 60)
    print("Testing Telegram Notifications")
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
    
    # Test 1: Simple message
    print(f"\n📱 Test 1: Sending simple test message...")
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "🧪 Test message from Betfair Bot!\n\nThis is a test to verify Telegram notifications are working."
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            print("✓ Simple message sent successfully!")
            print(f"   Message ID: {result.get('result', {}).get('message_id', 'N/A')}")
        else:
            print(f"❌ Failed to send message: {result.get('description', 'Unknown error')}")
            return
    except Exception as e:
        print(f"❌ Error sending message: {str(e)}")
        return
    
    # Wait a bit
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Test 2: Bet Matched notification format
    print(f"\n📱 Test 2: Testing Bet Matched notification format...")
    try:
        bet_result = {
            "betId": "123456789",
            "marketName": "Over/Under 2.5 Goals",
            "runnerName": "Over 2.5",
            "layPrice": 2.5,
            "stake": 10.0,
            "sizeMatched": 10.0,
            "eventName": "AC Milan vs Inter Milan"
        }
        
        message = f"""🎯 <b>Bet Matched!</b>

📊 <b>Match:</b> {bet_result['eventName']}
📈 <b>Market:</b> {bet_result['marketName']}
🎲 <b>Selection:</b> {bet_result['runnerName']}
💰 <b>Odds:</b> {bet_result['layPrice']}
💵 <b>Stake:</b> {bet_result['stake']} EUR
✅ <b>Matched:</b> {bet_result['sizeMatched']} EUR
🆔 <b>Bet ID:</b> {bet_result['betId']}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            print("✓ Bet Matched notification sent successfully!")
        else:
            print(f"❌ Failed to send Bet Matched notification: {result.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error sending Bet Matched notification: {str(e)}")
    
    # Wait a bit
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Test 3: Bet Won notification format
    print(f"\n📱 Test 3: Testing Bet Won notification format...")
    try:
        bet_record = {
            "bet_id": "123456789",
            "match_id": "987654321",
            "competition": "Serie A",
            "market_name": "Over/Under 2.5 Goals",
            "selection": "Over 2.5",
            "odds": 2.5,
            "stake": 10.0,
            "event_name": "AC Milan vs Inter Milan",
            "final_score": "3-1",
            "outcome": "Won",
            "profit_loss": 15.0
        }
        
        message = f"""✅ <b>Bet Won!</b>

📊 <b>Match:</b> {bet_record['event_name']}
🏆 <b>Final Score:</b> {bet_record['final_score']}
📈 <b>Market:</b> {bet_record['market_name']}
🎲 <b>Selection:</b> {bet_record['selection']}
💰 <b>Odds:</b> {bet_record['odds']}
💵 <b>Stake:</b> {bet_record['stake']} EUR
💚 <b>Profit:</b> +{bet_record['profit_loss']} EUR
🆔 <b>Bet ID:</b> {bet_record['bet_id']}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            print("✓ Bet Won notification sent successfully!")
        else:
            print(f"❌ Failed to send Bet Won notification: {result.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error sending Bet Won notification: {str(e)}")
    
    # Wait a bit
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Test 4: Bet Lost notification format
    print(f"\n📱 Test 4: Testing Bet Lost notification format...")
    try:
        bet_record = {
            "bet_id": "123456789",
            "match_id": "987654321",
            "competition": "Serie A",
            "market_name": "Over/Under 2.5 Goals",
            "selection": "Over 2.5",
            "odds": 2.5,
            "stake": 10.0,
            "event_name": "AC Milan vs Inter Milan",
            "final_score": "1-0",
            "outcome": "Lost",
            "profit_loss": -10.0
        }
        
        message = f"""❌ <b>Bet Lost</b>

📊 <b>Match:</b> {bet_record['event_name']}
🏆 <b>Final Score:</b> {bet_record['final_score']}
📈 <b>Market:</b> {bet_record['market_name']}
🎲 <b>Selection:</b> {bet_record['selection']}
💰 <b>Odds:</b> {bet_record['odds']}
💵 <b>Stake:</b> {bet_record['stake']} EUR
💔 <b>Loss:</b> {bet_record['profit_loss']} EUR
🆔 <b>Bet ID:</b> {bet_record['bet_id']}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("ok"):
            print("✓ Bet Lost notification sent successfully!")
        else:
            print(f"❌ Failed to send Bet Lost notification: {result.get('description', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error sending Bet Lost notification: {str(e)}")
    
    # Test 5: Error handling (invalid token)
    print(f"\n📱 Test 5: Testing error handling (invalid token)...")
    try:
        url = f"https://api.telegram.org/botINVALID_TOKEN/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": "This should fail"
        }
        
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if not result.get("ok"):
            print(f"✓ Error handling works correctly (expected error: {result.get('description', 'Unknown')})")
        else:
            print("⚠ Unexpected: Invalid token was accepted (this shouldn't happen)")
    except Exception as e:
        print(f"✓ Error handling works correctly (exception caught: {type(e).__name__})")
    
    print("\n" + "=" * 60)
    print("✅ Telegram notification test completed!")
    print("=" * 60)
    print("\nPlease check your Telegram app for the test messages.")
    print("\nIf you received all test messages, Telegram notifications are working correctly!")
    print("\nNote: Make sure you have started a conversation with your bot first:")
    print("  1. Find your bot on Telegram (e.g., @my_betfair_bot)")
    print("  2. Click 'Start' or send /start")
    print("  3. Then run this test again")

if __name__ == "__main__":
    try:
        test_telegram_basic()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

