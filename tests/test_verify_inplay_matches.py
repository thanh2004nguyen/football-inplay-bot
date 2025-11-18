"""
Test script to verify InPlay matches from Betfair
This script checks if markets marked as inPlay are actually live
"""
import sys
from pathlib import Path
import json
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService
from betfair.market_filter import filter_match_specific_markets


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_verify_inplay_matches():
    """Test and verify InPlay matches from Betfair"""
    print_section("Verifying InPlay Matches from Betfair")
    
    # Load config
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "config.json"
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    # Change to project root to ensure .env file is found
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(project_root)
        
        env_path = project_root / ".env"
        if env_path.exists():
            print(f"✓ Found .env file at: {env_path}")
        
        from config.loader import load_config
        config = load_config(str(config_path.relative_to(project_root)))
    except Exception as e:
        print(f"❌ Failed to load config: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    finally:
        os.chdir(original_cwd)
    
    betfair_config = config.get("betfair", {})
    app_key = betfair_config.get("app_key", "")
    username = betfair_config.get("username", "")
    password = betfair_config.get("password", "")
    cert_path = betfair_config.get("certificate_path", "")
    key_path = betfair_config.get("key_path", "")
    api_endpoint = betfair_config.get("api_endpoint", "https://api.betfair.com/exchange/betting/rest/v1.0")
    
    if not app_key or not username or not password:
        print("❌ Betfair configuration incomplete!")
        return
    
    # Initialize authenticator
    print(f"\n🔧 Initializing Betfair authenticator...")
    try:
        authenticator = BetfairAuthenticator(
            app_key=app_key,
            username=username,
            password=password,
            cert_path=cert_path if cert_path else None,
            key_path=key_path if key_path else None
        )
        
        # Login
        success, error = authenticator.login_with_password()
        if not success and cert_path and key_path:
            success, error = authenticator.login()
        
        if not success:
            print(f"❌ Login failed: {error}")
            return
        
        session_token = authenticator.get_session_token()
        if not session_token:
            print("❌ No session token received")
            return
        
        print(f"✓ Login successful")
        print(f"  - App Key: {app_key}")
        print(f"  - Session Token: {session_token}")
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Initialize market service
    print(f"\n🔧 Initializing Market Service...")
    try:
        market_service = MarketService(
            app_key=app_key,
            session_token=session_token,
            api_endpoint=api_endpoint
        )
        print("✓ Market Service initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Market Service: {str(e)}")
        return
    
    # Get current time
    current_time = datetime.now(timezone.utc)
    print(f"\n⏰ Current Time (UTC): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Get all markets with inPlay filter
    print(f"\n📊 Step 1: Fetching markets with inPlay=true filter...")
    try:
        markets = market_service.list_market_catalogue(
            event_type_ids=[1],  # Soccer
            in_play_only=True,
            max_results=1000
        )
        
        print(f"✓ Retrieved {len(markets)} markets from catalogue (with inPlay filter)")
        
        if not markets:
            print("⚠ No markets found with inPlay filter")
            return
        
        # Filter match-specific markets
        match_markets = filter_match_specific_markets(markets)
        print(f"  → After filtering match-specific: {len(match_markets)} markets")
        
    except Exception as e:
        print(f"❌ Error fetching markets: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Get detailed market book data to verify actual status
    print(f"\n📊 Step 2: Verifying actual market status from MarketBook...")
    
    # Extract unique events
    unique_events = {}
    for market in match_markets:
        event = market.get("event", {})
        event_id = event.get("id", "")
        
        if not event_id:
            continue
        
        market_id = market.get("marketId", "")
        market_name = market.get("marketName", "")
        market_type = market.get("marketType", "")
        
        # Get market definition from catalogue
        market_def = market.get("marketDefinition", {})
        catalogue_in_play = market_def.get("inPlay", False)
        catalogue_status = market_def.get("status", "N/A")
        market_time = market_def.get("marketTime", "")
        
        if event_id not in unique_events:
            competition = market.get("competition", {})
            unique_events[event_id] = {
                "event_id": event_id,
                "event_name": event.get("name", "N/A"),
                "competition_name": competition.get("name", "N/A"),
                "competition_id": competition.get("id", "N/A"),
                "markets": []
            }
        
        unique_events[event_id]["markets"].append({
            "market_id": market_id,
            "market_name": market_name,
            "market_type": market_type,
            "catalogue_in_play": catalogue_in_play,
            "catalogue_status": catalogue_status,
            "market_time": market_time
        })
    
    print(f"✓ Found {len(unique_events)} unique events")
    
    # Step 3: Get MarketBook for each market to verify actual status
    print(f"\n📊 Step 3: Checking MarketBook for actual inPlay status...")
    
    all_market_ids = [m.get("marketId", "") for m in match_markets if m.get("marketId")]
    
    if not all_market_ids:
        print("⚠ No market IDs found")
        return
    
    try:
        # Get market book data (limit to first 50 to avoid too much data)
        market_ids_to_check = all_market_ids[:50]
        print(f"  → Checking {len(market_ids_to_check)} markets (limited to 50 for performance)...")
        
        # Request market book with proper projection to get status
        market_books = market_service.list_market_book(
            market_ids=market_ids_to_check,
            price_projection={
                "priceData": ["EX_BEST_OFFERS"]  # Minimal data to check status
            }
        )
        
        print(f"✓ Retrieved {len(market_books)} market books")
        
        # Create mapping: market_id -> market_book
        market_book_map = {}
        for mb in market_books:
            market_id = mb.get("marketId", "")
            if market_id:
                market_book_map[market_id] = mb
        
        # Step 4: Analyze and display results
        print_section("Analysis Results")
        
        verified_inplay_events = {}
        not_inplay_events = {}
        
        for event_id, event_data in unique_events.items():
            event_has_inplay = False
            event_markets_detail = []
            
            for market_info in event_data["markets"]:
                market_id = market_info["market_id"]
                market_book = market_book_map.get(market_id)
                
                if market_book:
                    # Get actual status from market book
                    market_def_book = market_book.get("marketDefinition", {})
                    actual_in_play = market_def_book.get("inPlay", False)
                    actual_status = market_def_book.get("status", "")
                    total_matched = market_book.get("totalMatched", 0)
                    
                    # Also check market status directly (not just from marketDefinition)
                    market_status = market_book.get("status", "")
                    if not market_status and actual_status:
                        market_status = actual_status
                    elif not actual_status and market_status:
                        actual_status = market_status
                    
                    # Get market time to check if it's scheduled for now
                    market_time_str = market_def_book.get("marketTime", "")
                    market_time = None
                    is_scheduled_now = False
                    
                    if market_time_str:
                        try:
                            # Parse ISO format datetime
                            market_time = datetime.fromisoformat(market_time_str.replace('Z', '+00:00'))
                            # Check if market time is within last 3 hours (likely in play)
                            time_diff = (current_time - market_time).total_seconds()
                            is_scheduled_now = -3600 <= time_diff <= 10800  # Between 1 hour ago and 3 hours from now
                        except:
                            pass
                    
                    # Check if market is actually open and in play
                    # Criteria: status is OPEN, inPlay is True, OR has matched volume and is scheduled now
                    is_actually_live = False
                    if actual_status == "OPEN" and actual_in_play:
                        is_actually_live = True
                    elif actual_status == "OPEN" and total_matched > 0 and is_scheduled_now:
                        # Market is open, has volume, and is scheduled for now
                        is_actually_live = True
                    elif market_status == "OPEN" and total_matched > 0:
                        # Fallback: if status is OPEN and has volume
                        is_actually_live = True
                    
                    if is_actually_live:
                        event_has_inplay = True
                    
                    event_markets_detail.append({
                        **market_info,
                        "actual_in_play": actual_in_play,
                        "actual_status": actual_status or market_status or "N/A",
                        "market_status": market_status or "N/A",
                        "total_matched": total_matched,
                        "market_time": market_time_str,
                        "is_scheduled_now": is_scheduled_now,
                        "is_actually_live": is_actually_live
                    })
                else:
                    # Market book not available - use catalogue data
                    market_time_str = market_info.get("market_time", "")
                    market_time = None
                    is_scheduled_now = False
                    
                    if market_time_str:
                        try:
                            market_time = datetime.fromisoformat(market_time_str.replace('Z', '+00:00'))
                            time_diff = (current_time - market_time).total_seconds()
                            is_scheduled_now = -3600 <= time_diff <= 10800
                        except:
                            pass
                    
                    event_markets_detail.append({
                        **market_info,
                        "actual_in_play": market_info["catalogue_in_play"],
                        "actual_status": market_info["catalogue_status"],
                        "market_status": "N/A",
                        "total_matched": 0,
                        "market_time": market_time_str,
                        "is_scheduled_now": is_scheduled_now,
                        "is_actually_live": market_info["catalogue_in_play"] and market_info["catalogue_status"] == "OPEN"
                    })
            
            if event_has_inplay:
                verified_inplay_events[event_id] = {
                    **event_data,
                    "markets": event_markets_detail
                }
            else:
                not_inplay_events[event_id] = {
                    **event_data,
                    "markets": event_markets_detail
                }
        
        # Display verified InPlay matches
        print(f"\n✅ VERIFIED InPlay Matches (actually live): {len(verified_inplay_events)}")
        if verified_inplay_events:
            for idx, (event_id, event_data) in enumerate(verified_inplay_events.items(), 1):
                print(f"\n{idx}. {event_data['event_name']}")
                print(f"   Event ID: {event_id}")
                print(f"   Competition: {event_data['competition_name']}")
                print(f"   Markets ({len(event_data['markets'])}):")
                for m in event_data['markets']:
                    if m.get('is_actually_live'):
                        print(f"     ✓ {m['market_name']} ({m['market_type']})")
                        print(f"       Status: {m['actual_status']}, InPlay: {m['actual_in_play']}, Matched: {m['total_matched']}")
                        if m.get('market_time'):
                            print(f"       Market Time: {m['market_time']}")
        else:
            print("   ⚠ No matches are actually in play")
        
        # Display matches that are NOT actually in play
        print(f"\n⚠ NOT InPlay (but returned by filter): {len(not_inplay_events)}")
        if not_inplay_events:
            for idx, (event_id, event_data) in enumerate(not_inplay_events.items(), 1):
                print(f"\n{idx}. {event_data['event_name']}")
                print(f"   Event ID: {event_id}")
                print(f"   Competition: {event_data['competition_name']}")
                print(f"   Markets ({len(event_data['markets'])}):")
                for m in event_data['markets']:
                    print(f"     - {m['market_name']} ({m['market_type']})")
                    print(f"       Catalogue: InPlay={m['catalogue_in_play']}, Status={m['catalogue_status']}")
                    print(f"       MarketBook: InPlay={m['actual_in_play']}, Status={m['actual_status']}, Matched={m['total_matched']}")
                    if m.get('market_time'):
                        print(f"       Market Time: {m['market_time']} (Scheduled now: {m.get('is_scheduled_now', False)})")
                    # Show why it's not considered live
                    reasons = []
                    if m['actual_status'] != "OPEN":
                        reasons.append(f"Status={m['actual_status']} (not OPEN)")
                    if not m['actual_in_play']:
                        reasons.append("InPlay=False")
                    if m['total_matched'] == 0:
                        reasons.append("No matched volume")
                    if reasons:
                        print(f"       Not live because: {', '.join(reasons)}")
        
        # Summary
        print_section("Summary")
        print(f"Total markets from catalogue (inPlay filter): {len(markets)}")
        print(f"Match-specific markets: {len(match_markets)}")
        print(f"Unique events: {len(unique_events)}")
        print(f"✅ Actually InPlay events: {len(verified_inplay_events)}")
        print(f"⚠ Not actually InPlay events: {len(not_inplay_events)}")
        
        if len(not_inplay_events) > 0:
            print(f"\n⚠ WARNING: {len(not_inplay_events)} event(s) were returned by inPlay filter")
            print(f"   but are NOT actually in play according to MarketBook!")
            print(f"   This might be a timing issue or API inconsistency.")
        
    except Exception as e:
        print(f"❌ Error checking market books: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_verify_inplay_matches()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

