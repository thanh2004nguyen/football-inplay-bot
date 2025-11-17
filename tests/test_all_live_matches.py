"""
Test script to get ALL live matches from Betfair API (no competition filter)
This script authenticates and retrieves all available live football matches
"""
import sys
from pathlib import Path
import json
from datetime import datetime
from collections import OrderedDict

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService


def filter_match_specific_markets(markets):
    """
    Filter out Winner/Champion markets, keep only match-specific markets
    
    Args:
        markets: List of market dictionaries
        
    Returns:
        Filtered list of match-specific markets
    """
    match_specific_keywords = [
        "Match Odds", "Over/Under", "Both Teams to Score", "Correct Score",
        "First Goal", "Half Time", "Full Time", "Asian Handicap",
        "Draw No Bet", "Double Chance", "Total Goals", "Handicap"
    ]
    
    filtered = []
    for market in markets:
        market_name = market.get("marketName", "")
        # Exclude Winner/Champion markets
        if "Winner" in market_name or "Champion" in market_name:
            continue
        # Include match-specific markets
        if any(keyword in market_name for keyword in match_specific_keywords):
            filtered.append(market)
    
    return filtered


def test_all_live_matches():
    """Test function to get all live matches from Betfair (no competition filter)"""
    print("=" * 70)
    print("Betfair - Get ALL Live Matches Test (No Competition Filter)")
    print("=" * 70)
    
    try:
        # Load configuration
        print("\n[1/4] Loading configuration...")
        config = load_config()
        betfair_config = config["betfair"]
        print("✓ Configuration loaded")
        
        # Check login method
        use_password_login = betfair_config.get("use_password_login", False)
        
        # Initialize authenticator
        print("\n[2/4] Authenticating with Betfair...")
        cert_path = betfair_config.get("certificate_path") if not use_password_login else None
        key_path = betfair_config.get("key_path") if not use_password_login else None
        
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config.get("password") or input("Enter Betfair password: "),
            cert_path=cert_path,
            key_path=key_path,
            login_endpoint=betfair_config.get("login_endpoint")
        )
        
        # Login based on method
        if use_password_login:
            success, error = authenticator.login_with_password()
        else:
            success, error = authenticator.login()
            
        if not success:
            print(f"✗ Login failed: {error}")
            return 1
        
        session_token = authenticator.get_session_token()
        print(f"✓ Login successful (Session token: {session_token[:20]}...)")
        
        # Initialize market service
        print("\n[3/4] Initializing market service...")
        market_service = MarketService(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            api_endpoint=betfair_config["api_endpoint"]
        )
        print("✓ Market service initialized")
        
        # Get all live matches (no competition filter)
        print("\n[4/4] Fetching ALL live matches from Betfair...")
        print("   (This may take a moment, fetching all competitions...)")
        
        # Get markets with in-play only, no competition filter
        markets = market_service.list_market_catalogue(
            event_type_ids=[1],  # Football only
            competition_ids=None,  # NO FILTER - get all competitions
            in_play_only=True  # Only in-play matches
        )
        
        if not markets:
            print("✗ No live markets found")
            return 1
        
        print(f"✓ Found {len(markets)} live market(s)")
        
        # Filter to only match-specific markets
        markets = filter_match_specific_markets(markets)
        print(f"✓ After filtering: {len(markets)} match-specific market(s)")
        
        # Get unique events from markets
        unique_events: dict = {}
        for market in markets:
            event = market.get("event", {})
            event_id = event.get("id", "")
            if event_id and event_id not in unique_events:
                unique_events[event_id] = {
                    "event": event,
                    "competition": market.get("competition", {}),
                    "markets": []
                }
            if event_id:
                unique_events[event_id]["markets"].append(market)
        
        print(f"\n{'=' * 70}")
        print(f"RESULTS: Found {len(unique_events)} unique live match(es)")
        print(f"{'=' * 70}\n")
        
        # Group by competition
        competitions_dict = {}
        for event_id, event_data in unique_events.items():
            comp_name = event_data["competition"].get("name", "Unknown Competition")
            if comp_name not in competitions_dict:
                competitions_dict[comp_name] = []
            competitions_dict[comp_name].append(event_data)
        
        # Display results grouped by competition
        print(f"Live matches grouped by competition:\n")
        for comp_name, events in sorted(competitions_dict.items()):
            print(f"  📋 {comp_name}: {len(events)} match(es)")
            for i, event_data in enumerate(events[:5], 1):  # Show first 5 per competition
                event = event_data["event"]
                event_name = event.get("name", "N/A")
                market_count = len(event_data["markets"])
                print(f"     [{i}] {event_name} - {market_count} market(s)")
            if len(events) > 5:
                print(f"     ... and {len(events) - 5} more match(es)")
            print()
        
        # Prepare data for JSON export
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "total_matches": len(unique_events),
            "total_markets": len(markets),
            "competitions": {}
        }
        
        for comp_name, events in competitions_dict.items():
            export_data["competitions"][comp_name] = {
                "match_count": len(events),
                "matches": []
            }
            for event_data in events:
                event = event_data["event"]
                match_info = {
                    "event_id": event.get("id", ""),
                    "event_name": event.get("name", "N/A"),
                    "market_count": len(event_data["markets"]),
                    "markets": [
                        {
                            "market_id": m.get("marketId", ""),
                            "market_name": m.get("marketName", ""),
                            "market_type": m.get("marketType", "")
                        }
                        for m in event_data["markets"]
                    ]
                }
                export_data["competitions"][comp_name]["matches"].append(match_info)
        
        # Save to JSON file
        output_file = Path(__file__).parent.parent / "all_live_matches.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Results saved to: {output_file}")
        print(f"\n{'=' * 70}")
        print("SUMMARY:")
        print(f"  - Total live matches: {len(unique_events)}")
        print(f"  - Total competitions: {len(competitions_dict)}")
        print(f"  - Total markets: {len(markets)}")
        print(f"  - Output file: {output_file}")
        print(f"{'=' * 70}\n")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = test_all_live_matches()
    sys.exit(exit_code)

