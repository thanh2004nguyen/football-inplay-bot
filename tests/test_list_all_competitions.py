"""
Test script to get all Football (Soccer) competitions and their events from Betfair API

This script uses:
1. listCompetitions method with eventTypeIds = [1] (Soccer) to get all competitions
2. listMarketCatalogue method for each competition to get all events

Displays:
- Total number of competitions
- For each competition: ID, name, market count, and all events
- Total number of events across all competitions
"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService
from utils.auth_utils import perform_login_with_retry


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_list_all_competitions():
    """Test getting all Football competitions from Betfair API"""
    print_section("Test: List All Football Competitions from Betfair")
    
    try:
        # Load configuration
        print("\n📋 Loading configuration...")
        config = load_config()
        betfair_config = config["betfair"]
        
        # Initialize authenticator
        use_password_login = betfair_config.get("use_password_login", False)
        cert_path = betfair_config.get("certificate_path") if not use_password_login else None
        key_path = betfair_config.get("key_path") if not use_password_login else None
        
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config["password"],
            cert_path=cert_path,
            key_path=key_path,
            login_endpoint=betfair_config.get("login_endpoint")
        )
        
        # Perform login
        print("🔐 Logging in to Betfair...")
        session_token, _ = perform_login_with_retry(config, authenticator, None)
        
        if not session_token:
            print("❌ Failed to obtain session token")
            return
        
        print("✅ Login successful")
        
        # Initialize MarketService
        print("\n📡 Initializing Market Service...")
        market_service = MarketService(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            api_endpoint=betfair_config.get("api_endpoint", "https://api.betfair.com/exchange/betting/rest/v1.0")
        )
        
        # Get all Football competitions (eventTypeIds = [1] for Soccer)
        print("\n⚽ Fetching all Football competitions from Betfair...")
        print("   Method: listCompetitions")
        print("   Filter: eventTypeIds = [1] (Soccer)")
        
        competitions = market_service.list_competitions([1])
        
        if not competitions:
            print("\n⚠️  No competitions found")
            return
        
        # Display results
        print_section("Results")
        print(f"\n✅ Total competitions found: {len(competitions)}")
        
        # Sort by marketCount (descending) to show most active competitions first
        sorted_competitions = sorted(
            competitions,
            key=lambda x: x.get("marketCount", 0),
            reverse=True
        )
        
        # Display top 20 examples
        print(f"\n📊 Top 20 competitions (by market count):")
        print("-" * 70)
        print(f"{'ID':<12} {'Market Count':<15} {'Competition Name'}")
        print("-" * 70)
        
        for i, comp in enumerate(sorted_competitions[:20], 1):
            comp_info = comp.get("competition", {})
            comp_id = comp_info.get("id", "N/A")
            comp_name = comp_info.get("name", "N/A")
            market_count = comp.get("marketCount", 0)
            
            print(f"{comp_id:<12} {market_count:<15} {comp_name}")
        
        # Get events for each competition
        print(f"\n📋 Fetching events for all {len(competitions)} competitions...")
        print("   This may take a while...")
        
        competitions_with_events = []
        total_events = 0
        
        for i, comp in enumerate(sorted_competitions, 1):
            comp_info = comp.get("competition", {})
            comp_id = comp_info.get("id", "N/A")
            comp_name = comp_info.get("name", "N/A")
            market_count = comp.get("marketCount", 0)
            
            print(f"\n[{i}/{len(competitions)}] Processing: {comp_name} (ID: {comp_id})...")
            
            # Get all markets for this competition
            try:
                # Convert comp_id to int if it's a string
                comp_id_int = int(comp_id) if comp_id != "N/A" else None
                
                if comp_id_int:
                    # Get markets for this competition (not filtered by inPlay to get all events)
                    markets = market_service.list_market_catalogue(
                        event_type_ids=[1],
                        competition_ids=[comp_id_int],
                        in_play_only=False,  # Get all events, not just in-play
                        market_type_codes=None,  # Get all market types
                        max_results=1000
                    )
                    
                    # Extract unique events from markets
                    unique_events = {}
                    for market in markets:
                        event = market.get("event", {})
                        event_id = event.get("id")
                        if event_id:
                            event_id_str = str(event_id)
                            if event_id_str not in unique_events:
                                unique_events[event_id_str] = {
                                    "event_id": event_id_str,
                                    "event_name": event.get("name", "N/A"),
                                    "start_time": event.get("openDate", "N/A"),
                                    "market_count": 0
                                }
                            unique_events[event_id_str]["market_count"] += 1
                    
                    events_list = list(unique_events.values())
                    total_events += len(events_list)
                    
                    comp_data = {
                        "competition": comp_info,
                        "market_count": market_count,
                        "event_count": len(events_list),
                        "events": events_list
                    }
                    
                    competitions_with_events.append(comp_data)
                    
                    print(f"    ✅ Found {len(events_list)} event(s)")
                    if len(events_list) > 0:
                        print(f"    Example events:")
                        for event in events_list[:3]:  # Show first 3 events
                            print(f"      • {event['event_id']}: {event['event_name']}")
                        if len(events_list) > 3:
                            print(f"      ... and {len(events_list) - 3} more")
                else:
                    print(f"    ⚠️  Invalid competition ID")
                    comp_data = {
                        "competition": comp_info,
                        "market_count": market_count,
                        "event_count": 0,
                        "events": []
                    }
                    competitions_with_events.append(comp_data)
                    
            except Exception as e:
                print(f"    ❌ Error fetching events: {str(e)}")
                comp_data = {
                    "competition": comp_info,
                    "market_count": market_count,
                    "event_count": 0,
                    "events": [],
                    "error": str(e)
                }
                competitions_with_events.append(comp_data)
        
        # Display summary
        print_section("Summary")
        print(f"\n✅ Total competitions: {len(competitions)}")
        print(f"✅ Total events across all competitions: {total_events}")
        print(f"✅ Average events per competition: {total_events / len(competitions):.1f}" if competitions else "N/A")
        
        # Display top competitions with most events
        print(f"\n📊 Top 10 competitions by event count:")
        print("-" * 70)
        print(f"{'ID':<12} {'Events':<10} {'Markets':<10} {'Competition Name'}")
        print("-" * 70)
        
        sorted_by_events = sorted(
            competitions_with_events,
            key=lambda x: x.get("event_count", 0),
            reverse=True
        )
        
        for comp_data in sorted_by_events[:10]:
            comp_info = comp_data.get("competition", {})
            comp_id = comp_info.get("id", "N/A")
            comp_name = comp_info.get("name", "N/A")
            event_count = comp_data.get("event_count", 0)
            market_count = comp_data.get("market_count", 0)
            
            print(f"{comp_id:<12} {event_count:<10} {market_count:<10} {comp_name}")
        
        # Save to JSON file for reference
        output_file = Path(__file__).parent.parent / "competitions" / "betfair_all_competitions_with_events.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_competitions": len(competitions),
                "total_events": total_events,
                "competitions": competitions_with_events
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_file}")
        print("\n✅ Test completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_list_all_competitions()

