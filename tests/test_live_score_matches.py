"""
Test script to get live matches from Live Score API
This script fetches and displays all currently live matches
"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from football_api.live_score_client import LiveScoreClient
from football_api.parser import parse_match_teams, parse_match_competition, parse_match_minute, parse_match_score

def test_get_live_matches():
    """Test getting live matches from Live Score API"""
    print("=" * 60)
    print("Testing Live Score API - Get Live Matches")
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
    
    # Get live matches
    print(f"\n📊 Fetching live matches from Live Score API...")
    try:
        live_matches = client.get_live_matches()
        
        if not live_matches:
            print("\n⚠ No live matches found")
            print("\nThis could mean:")
            print("  1. There are currently no matches being played")
            print("  2. All matches are finished, not started, or postponed")
            print("  3. API returned empty result")
            
            # Try to get raw response to see what API returned
            print(f"\n🔍 Checking raw API response...")
            try:
                params = {
                    "key": api_key,
                    "secret": api_secret
                }
                raw_result = client._make_request("/matches/live.json", params=params)
                
                if raw_result:
                    print(f"✓ API responded successfully")
                    if isinstance(raw_result, dict):
                        if raw_result.get("success"):
                            raw_matches = raw_result.get("data", {}).get("match", [])
                            if raw_matches:
                                print(f"⚠ Found {len(raw_matches)} match(es) in raw response, but filtered out:")
                                print(f"   (These matches may be finished, not started, or have invalid minute)")
                                
                                # Show first few matches that were filtered
                                for i, match in enumerate(raw_matches[:5], 1):
                                    home, away = parse_match_teams(match)
                                    status = match.get("status", "N/A")
                                    minute = parse_match_minute(match)
                                    score = parse_match_score(match)
                                    print(f"   [{i}] {home} v {away} - {score} @ {minute}' [{status}]")
                                
                                if len(raw_matches) > 5:
                                    print(f"   ... and {len(raw_matches) - 5} more match(es)")
                            else:
                                print(f"✓ API returned empty match list (no matches in response)")
                        else:
                            print(f"⚠ API returned success=false")
                            print(f"   Response: {json.dumps(raw_result, indent=2)[:500]}")
                    else:
                        print(f"⚠ Unexpected response type: {type(raw_result)}")
                        print(f"   Response: {str(raw_result)[:500]}")
                else:
                    print(f"⚠ API returned None or empty response")
            except Exception as e:
                print(f"⚠ Could not check raw response: {str(e)}")
            
            return
        
        print(f"✓ Successfully fetched {len(live_matches)} live match(es)")
        
        # Display live matches
        print(f"\n📋 Live Matches:")
        print("=" * 60)
        
        for idx, match in enumerate(live_matches, 1):
            home, away = parse_match_teams(match)
            comp = parse_match_competition(match)
            minute = parse_match_minute(match)
            score = parse_match_score(match)
            status = match.get("status", "N/A")
            match_id = match.get("id", "N/A")
            
            print(f"{idx:3d}. {home:25s} v {away:25s}")
            print(f"     Competition: {comp}")
            print(f"     Score: {score} @ {minute}' | Status: {status} | ID: {match_id}")
            print()
        
        print("=" * 60)
        print(f"\n✅ Total: {len(live_matches)} live match(es)")
        
        # Save to file (optional)
        output_file = project_root / "competitions" / "live_matches_test.json"
        output_file.parent.mkdir(exist_ok=True)
        
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "total_matches": len(live_matches),
            "matches": live_matches
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Live matches data saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error fetching live matches: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
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
        test_get_live_matches()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

