"""
Test script to get all Betfair matches with status InPlay
This script fetches and displays all matches that are currently in-play
"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService
from config.competition_mapper import get_competition_ids_from_excel


class TeeOutput:
    """Class to write to both console and file simultaneously"""
    def __init__(self, file_path):
        self.terminal = sys.stdout
        self.log_file = open(file_path, 'w', encoding='utf-8')
        self.log_file.write(f"Test Run Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_file.write("=" * 70 + "\n")
    
    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()
    
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
    
    def close(self):
        self.log_file.write("\n" + "=" * 70 + "\n")
        self.log_file.write(f"Test Run Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.log_file.close()


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_get_inplay_matches():
    """Test getting all matches with status InPlay from Betfair"""
    print_section("Testing Betfair API - Get All InPlay Matches")
    
    # Load config using config loader (handles environment variables)
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
        
        # Check if .env file exists
        env_path = project_root / ".env"
        if env_path.exists():
            print(f"✓ Found .env file at: {env_path}")
        else:
            print(f"⚠ .env file not found at: {env_path}")
        
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
    
    print(f"\n📋 Betfair Configuration:")
    print(f"  - App Key: {app_key}")
    print(f"  - Username: {username}")
    print(f"  - Password: {'*** (loaded)' if password else 'NOT SET (check BETFAIR_PASSWORD in .env file)'}")
    print(f"  - API Endpoint: {api_endpoint}")
    
    # Debug: Check environment variable directly
    import os
    env_password = os.getenv("BETFAIR_PASSWORD")
    if env_password:
        print(f"  - BETFAIR_PASSWORD from env: {'*** (found)'}")
    else:
        print(f"  - BETFAIR_PASSWORD from env: NOT FOUND")
    
    if not app_key or not username:
        print("\n⚠ Betfair configuration incomplete!")
        print("   Please check config.json for app_key and username")
        return
    
    if not password:
        print("\n⚠ Password not found!")
        print("   Please set BETFAIR_PASSWORD environment variable")
        print("   Example: set BETFAIR_PASSWORD=your_password (Windows)")
        print("   Or: export BETFAIR_PASSWORD=your_password (Linux/Mac)")
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
        print("✓ Authenticator initialized")
    except Exception as e:
        print(f"❌ Failed to initialize authenticator: {str(e)}")
        return
    
    # Login
    print(f"\n🔐 Attempting login...")
    try:
        # Try password login first
        success, error = authenticator.login_with_password()
        
        if not success:
            # Try certificate login if password login fails
            if cert_path and key_path:
                print("  → Password login failed, trying certificate login...")
                success, error = authenticator.login()
        
        if not success:
            print(f"❌ Login failed: {error}")
            return
        
        session_token = authenticator.get_session_token()
        if not session_token:
            print("❌ Login succeeded but no session token received")
            return
        
        print(f"✓ Login successful")
        print(f"\n📝 Session Information:")
        print(f"  - Session Token: {session_token}")
        print(f"  - App Key: {app_key}")
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
    
    # Load competitions from Excel and match with Betfair
    print(f"\n📋 Loading competitions from Excel...")
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    
    competition_ids_from_excel = []
    if excel_path.exists():
        try:
            # Get Betfair competitions first
            print("  → Fetching Betfair competitions...")
            betfair_competitions = market_service.list_competitions([1])  # Soccer
            print(f"  → Found {len(betfair_competitions)} Betfair competitions")
            
            # Match with Excel
            print(f"  → Matching with Excel: {excel_path.name}")
            competition_ids_from_excel = get_competition_ids_from_excel(
                str(excel_path),
                betfair_competitions
            )
            
            if competition_ids_from_excel:
                print(f"  ✅ Matched {len(competition_ids_from_excel)} competitions from Excel")
            else:
                print(f"  ⚠ No competitions matched from Excel (will show all matches)")
        except Exception as e:
            print(f"  ⚠ Error matching Excel competitions: {str(e)}")
            print(f"  → Will show all matches (not filtered by Excel)")
    else:
        print(f"  ⚠ Excel file not found: {excel_path}")
        print(f"  → Will show all matches (not filtered by Excel)")
    
    # Get all in-play matches (Soccer - event type ID 1)
    print(f"\n📊 Fetching all InPlay matches from Betfair...")
    print(f"  → Event Type: Soccer (ID: 1)")
    print(f"  → Filter: inPlay = true")
    if competition_ids_from_excel:
        print(f"  → Filter by Excel competitions: {len(competition_ids_from_excel)} competition(s)")
    
    try:
        # Get all in-play markets (filtered by Excel competitions if available)
        markets = market_service.list_market_catalogue(
            event_type_ids=[1],  # Soccer
            competition_ids=competition_ids_from_excel if competition_ids_from_excel else None,
            in_play_only=True,   # Only in-play markets
            max_results=1000     # Get as many as possible
        )
        
        if not markets:
            print("\n⚠ No InPlay matches found at this time")
            return
        
        print(f"✓ Successfully fetched {len(markets)} markets")
        
        # Filter out season-long markets (Winner markets)
        from betfair.market_filter import filter_match_specific_markets
        match_markets = filter_match_specific_markets(markets)
        print(f"  → After filtering match-specific markets: {len(match_markets)} markets")
        
        # Extract unique events (matches) and check inPlay status
        unique_events = {}
        for market in match_markets:
            event = market.get("event", {})
            event_id = event.get("id", "")
            
            if not event_id:
                continue
            
            # Get market definition to check inPlay status
            market_definition = market.get("marketDefinition", {})
            in_play = market_definition.get("inPlay", False)
            status = market_definition.get("status", "N/A")
            market_type = market.get("marketType", "N/A")
            market_name = market.get("marketName", "N/A")
            
            # Skip if this is a Winner market (season-long)
            if market_type.upper() == "WINNER" or "winner" in market_name.lower():
                continue
            
            if event_id not in unique_events:
                # Get competition info
                competition = market.get("competition", {})
                competition_name = competition.get("name", "N/A")
                competition_id = competition.get("id", "N/A")
                
                # Get event details
                event_name = event.get("name", "N/A")
                event_time = event.get("openDate", "")
                
                # Parse time if available
                event_time_str = "N/A"
                event_datetime = None
                time_info = "N/A"
                if event_time:
                    try:
                        # Parse ISO format datetime from Betfair (UTC time)
                        from datetime import timezone
                        event_datetime_utc = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                        if event_datetime_utc.tzinfo is None:
                            event_datetime_utc = event_datetime_utc.replace(tzinfo=timezone.utc)
                        
                        # Convert to local timezone (system timezone - automatically detected)
                        event_datetime = event_datetime_utc.astimezone(None)  # None = system local timezone
                        
                        # Format time string using local timezone
                        event_time_str = event_datetime.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Calculate time difference using local timezone
                        now_local = datetime.now(event_datetime.tzinfo)
                        time_diff = event_datetime - now_local
                        
                        if time_diff.total_seconds() < 0:
                            # Match has started or is in the past
                            hours_ago = abs(time_diff.total_seconds()) / 3600
                            if hours_ago < 3:  # Within 3 hours, likely live
                                minutes_ago = abs(time_diff.total_seconds()) / 60
                                time_info = f"Started {int(minutes_ago)} minutes ago"
                            else:
                                time_info = f"Started {int(hours_ago)} hours ago"
                        else:
                            # Match is in the future
                            hours_until = time_diff.total_seconds() / 3600
                            if hours_until < 24:
                                minutes_until = time_diff.total_seconds() / 60
                                time_info = f"Starts in {int(minutes_until)} minutes"
                            else:
                                time_info = f"Starts in {int(hours_until)} hours"
                    except Exception as e:
                        event_time_str = event_time
                        time_info = "Time parse error"
                
                unique_events[event_id] = {
                    "event_id": event_id,
                    "event_name": event_name,
                    "competition_name": competition_name,
                    "competition_id": competition_id,
                    "event_time": event_time_str,
                    "event_datetime": event_datetime.isoformat() if event_datetime else None,
                    "time_info": time_info,
                    "in_play": False,  # Will be set to True if any market is in play
                    "status": status,
                    "markets": []
                }
            
            # Add market to event
            market_info = {
                "market_id": market.get("marketId", "N/A"),
                "market_name": market_name,
                "market_type": market_type,
                "in_play": in_play,
                "status": status
            }
            unique_events[event_id]["markets"].append(market_info)
            
            # Update event inPlay status if any market is in play
            if in_play:
                unique_events[event_id]["in_play"] = True
                unique_events[event_id]["status"] = status
        
        # Filter to only show events with at least one in-play market
        inplay_events = {eid: event for eid, event in unique_events.items() if event["in_play"]}
        
        # Mark events that match Excel competitions
        competition_ids_set = set(competition_ids_from_excel) if competition_ids_from_excel else set()
        for event in unique_events.values():
            event_comp_id = event.get("competition_id")
            # Try to match as both int and str
            if event_comp_id and event_comp_id != "N/A":
                try:
                    comp_id_int = int(event_comp_id) if isinstance(event_comp_id, str) else event_comp_id
                    event["matched_excel"] = comp_id_int in competition_ids_set
                except (ValueError, TypeError):
                    event["matched_excel"] = False
            else:
                event["matched_excel"] = False
        
        # Sort all events by event time (most recent first)
        all_sorted_events = sorted(unique_events.values(), 
                                  key=lambda x: x.get("event_datetime") or "", 
                                  reverse=True)
        
        # Sort inPlay events by event name
        sorted_events = sorted(inplay_events.values(), key=lambda x: x["event_name"]) if inplay_events else []
        
        # Print all InPlay matches first
        print_section("🔴 LIVE MATCHES (InPlay)")
        
        if not inplay_events:
            print("⚠ No InPlay matches found (no markets with inPlay = true)")
        else:
            print(f"\n✅ Total LIVE Matches: {len(sorted_events)}\n")
            
            for idx, event in enumerate(sorted_events, 1):
                excel_match = "✅ Excel" if event.get("matched_excel", False) else "❌ Not in Excel"
                print(f"{idx:4d}. 🔴 LIVE: {event['event_name']} [{excel_match}]")
                print(f"      Competition: {event['competition_name']} (ID: {event['competition_id']})")
                print(f"      Event ID: {event['event_id']}")
                print(f"      ⏰ Live Time: {event['event_time']} | {event.get('time_info', 'N/A')}")
                print(f"      Status: {event['status']} | Markets: {len(event['markets'])}")
                
                # Show first few markets
                if event['markets']:
                    print(f"      Market Types:")
                    for market in event['markets'][:5]:  # Show first 5 markets
                        inplay_mark = "🔴" if market.get('in_play') else "⚪"
                        print(f"        {inplay_mark} {market['market_name']} ({market['market_type']})")
                    if len(event['markets']) > 5:
                        print(f"        ... and {len(event['markets']) - 5} more markets")
                
                print()  # Empty line between matches
        
        # Print all other events found (not inPlay but available)
        print_section("📋 ALL MATCHES FOUND (Including Non-Live)")
        
        if not all_sorted_events:
            print("⚠ No events found")
        else:
            print(f"\n📊 Total Events Found: {len(all_sorted_events)}")
            print(f"   🔴 Live: {len(inplay_events)} | ⚪ Not Live: {len(all_sorted_events) - len(inplay_events)}\n")
            
            for idx, event in enumerate(all_sorted_events, 1):
                live_indicator = "🔴 LIVE" if event["in_play"] else "⚪"
                excel_match = "✅ Excel" if event.get("matched_excel", False) else "❌ Not in Excel"
                print(f"{idx:4d}. {live_indicator} {event['event_name']} [{excel_match}]")
                print(f"      Competition: {event['competition_name']} (ID: {event['competition_id']})")
                print(f"      Event ID: {event['event_id']}")
                print(f"      ⏰ Time: {event['event_time']} | {event.get('time_info', 'N/A')}")
                print(f"      Status: {event['status']} | InPlay: {event['in_play']} | Markets: {len(event['markets'])}")
                print()  # Empty line between matches
        
        # Count matches with Excel
        inplay_matched_excel = sum(1 for e in sorted_events if e.get("matched_excel", False))
        all_matched_excel = sum(1 for e in all_sorted_events if e.get("matched_excel", False))
        
        print("=" * 70)
        print(f"\n📊 Summary:")
        print(f"   ✅ Total InPlay Matches: {len(sorted_events)}")
        if competition_ids_from_excel:
            print(f"      → Matched with Excel: {inplay_matched_excel} | Not in Excel: {len(sorted_events) - inplay_matched_excel}")
        print(f"   📋 Total Events Found: {len(all_sorted_events)}")
        if competition_ids_from_excel:
            print(f"      → Matched with Excel: {all_matched_excel} | Not in Excel: {len(all_sorted_events) - all_matched_excel}")
        print(f"   📈 Total Markets: {len(markets)}")
        if competition_ids_from_excel:
            print(f"   📝 Excel Competitions: {len(competition_ids_from_excel)} competition(s)")
        
        # Save to file (optional)
        output_file = project_root / "competitions" / "betfair_inplay_matches.json"
        output_file.parent.mkdir(exist_ok=True)
        
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "total_inplay_matches": len(sorted_events),
            "total_events": len(all_sorted_events),
            "total_markets": len(markets),
            "inplay_matches": sorted_events,
            "all_matches": all_sorted_events
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Data saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error fetching InPlay matches: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    # Setup logging to file
    project_root = Path(__file__).parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "test.log"
    
    # Create TeeOutput to write to both console and file
    tee = TeeOutput(log_file)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        # Redirect stdout and stderr to TeeOutput
        sys.stdout = tee
        sys.stderr = tee
        
        test_get_inplay_matches()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Write final message to log before closing
        tee.log_file.write(f"\n💾 Test output saved to: {log_file}\n")
        # Restore original stdout/stderr and close log file
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        tee.close()
        # Print to console after restoring stdout
        print(f"\n💾 Test output saved to: {log_file}")

