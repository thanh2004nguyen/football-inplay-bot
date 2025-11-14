"""
Test script to get all competitions from Live Score API
This script fetches and displays all available competitions
"""
import sys
from pathlib import Path
import json

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_api.live_score_client import LiveScoreClient

def test_get_competitions():
    """Test getting all competitions from Live Score API"""
    print("=" * 60)
    print("Testing Live Score API - Get All Competitions")
    print("=" * 60)
    
    # Load config
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    live_score_config = config.get("live_score_api", {})
    api_key = live_score_config.get("api_key", "")
    api_secret = live_score_config.get("api_secret", "")
    base_url = live_score_config.get("base_url", "https://livescore-api.com/api-client")
    rate_limit_per_day = live_score_config.get("rate_limit_per_day", 1500)
    
    print(f"\n📋 Live Score API Configuration:")
    print(f"  - API Key: {api_key[:10]}..." if api_key else "  - API Key: Not set")
    print(f"  - Base URL: {base_url}")
    print(f"  - Rate Limit: {rate_limit_per_day} requests/day")
    
    if not api_key or not api_secret:
        print("\n⚠ Live Score API configuration incomplete!")
        print("   Please add to config.json:")
        print('   "live_score_api": {')
        print('     "api_key": "YOUR_API_KEY",')
        print('     "api_secret": "YOUR_API_SECRET"')
        print('   }')
        return
    
    # Initialize Live Score client
    print(f"\n🔧 Initializing Live Score API client...")
    try:
        client = LiveScoreClient(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            rate_limit_per_day=rate_limit_per_day
        )
        print("✓ Live Score API client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Live Score API client: {str(e)}")
        return
    
    # Get competitions list
    print(f"\n📊 Fetching competitions list from Live Score API...")
    try:
        # Use the _make_request method to call competitions/list endpoint
        competitions_data = client._make_request(
            endpoint="/competitions/list.json",
            params={
                "key": api_key,
                "secret": api_secret
            }
        )
        
        if not competitions_data:
            print("❌ Failed to fetch competitions (empty response)")
            return
        
        # Check response structure
        if "data" in competitions_data:
            competitions = competitions_data["data"].get("competition", [])
        elif "competition" in competitions_data:
            competitions = competitions_data["competition"]
        elif isinstance(competitions_data, list):
            competitions = competitions_data
        else:
            print(f"⚠ Unexpected response structure: {list(competitions_data.keys())}")
            print(f"Response preview: {json.dumps(competitions_data, indent=2)[:500]}")
            competitions = []
        
        if not competitions:
            print("⚠ No competitions found in response")
            print(f"Response: {json.dumps(competitions_data, indent=2)[:500]}")
            return
        
        print(f"✓ Successfully fetched {len(competitions)} competitions")
        
        # Display competitions
        print(f"\n📋 Competitions List:")
        print("=" * 60)
        
        # Sort by name for easier reading
        sorted_competitions = sorted(competitions, key=lambda x: x.get("name", ""))
        
        for idx, comp in enumerate(sorted_competitions, 1):
            comp_id = comp.get("id", "N/A")
            comp_name = comp.get("name", "N/A")
            country = comp.get("country", {}).get("name", "N/A") if isinstance(comp.get("country"), dict) else comp.get("country", "N/A")
            
            print(f"{idx:4d}. ID: {comp_id:6s} | {comp_name:40s} | Country: {country}")
        
        print("=" * 60)
        print(f"\n✅ Total: {len(competitions)} competitions")
        
        # Save to file (optional)
        output_file = project_root / "competitions" / "live_score_competitions.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(competitions_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Competitions data saved to: {output_file}")
        
        # Also save as simple text list
        txt_file = project_root / "competitions" / "live_score_competitions_list.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("Live Score API - Competitions List\n")
            f.write("=" * 60 + "\n\n")
            for comp in sorted_competitions:
                comp_id = comp.get("id", "N/A")
                comp_name = comp.get("name", "N/A")
                country = comp.get("country", {}).get("name", "N/A") if isinstance(comp.get("country"), dict) else comp.get("country", "N/A")
                f.write(f"ID: {comp_id:6s} | {comp_name:40s} | Country: {country}\n")
        
        print(f"💾 Text list saved to: {txt_file}")
        
    except Exception as e:
        print(f"❌ Error fetching competitions: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Show rate limit status
    print(f"\n📊 Rate Limit Status:")
    status = client.rate_limiter.get_status()
    print(f"  - Requests today: {status['requests_today']}/{status['requests_per_day']}")
    print(f"  - Remaining today: {status['remaining_today']}")
    print(f"  - Requests this hour: {status['requests_this_hour']:.1f}/{status['requests_per_hour']:.1f}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        test_get_competitions()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

