"""
Test script for sound notifications
Tests if sound files can be played correctly
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from notifications.sound_notifier import SoundNotifier
import time

def test_sound_notifications():
    """Test sound notifications"""
    print("=" * 60)
    print("Testing Sound Notifications")
    print("=" * 60)
    
    # Load config
    project_root = Path(__file__).parent
    config_path = project_root / "config" / "config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    import json
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    notifications_config = config.get("notifications", {})
    
    print(f"\n📋 Configuration:")
    print(f"  - Sound enabled: {notifications_config.get('sound_enabled', False)}")
    print(f"  - Bet placed sound: {notifications_config.get('sounds', {}).get('bet_placed', 'N/A')}")
    print(f"  - Bet matched sound: {notifications_config.get('sounds', {}).get('bet_matched', 'N/A')}")
    
    # Initialize sound notifier
    print(f"\n🔧 Initializing sound notifier...")
    try:
        sound_notifier = SoundNotifier(notifications_config)
        print("✓ Sound notifier initialized")
    except Exception as e:
        print(f"❌ Failed to initialize sound notifier: {str(e)}")
        return
    
    if not sound_notifier.enabled:
        print("⚠ Sound notifications are disabled")
        return
    
    # Test bet placed sound
    print(f"\n🔊 Testing bet placed sound...")
    print("   Playing success.mp3...")
    try:
        sound_notifier.play_bet_placed_sound()
        print("✓ Bet placed sound played")
        time.sleep(1)  # Wait for sound to finish
    except Exception as e:
        print(f"❌ Error playing bet placed sound: {str(e)}")
    
    # Wait a bit between sounds
    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Test bet matched sound
    print(f"\n🔊 Testing bet matched sound...")
    print("   Playing ping.mp3...")
    try:
        sound_notifier.play_bet_matched_sound()
        print("✓ Bet matched sound played")
        time.sleep(1)  # Wait for sound to finish
    except Exception as e:
        print(f"❌ Error playing bet matched sound: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Sound notification test completed!")
    print("=" * 60)
    print("\nIf you heard both sounds, the notifications are working correctly!")
    print("If not, please check:")
    print("  1. Sound files exist in sounds/ directory")
    print("  2. playsound3 is installed (pip install playsound3)")
    print("  3. System volume is not muted")

if __name__ == "__main__":
    try:
        test_sound_notifications()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

