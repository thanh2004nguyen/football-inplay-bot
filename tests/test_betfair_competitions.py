"""
Test script to get all competitions from Betfair API
This script authenticates and retrieves all available football competitions
"""
import sys
from pathlib import Path
import json
import requests
import time
from datetime import datetime
from collections import OrderedDict

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService


def test_betfair_competitions():
    """Test function to get all competitions from Betfair"""
    print("=" * 60)
    print("Betfair Competitions List Test")
    print("=" * 60)
    
    try:
        # Load configuration
        print("\n[1/4] Loading configuration...")
        config = load_config()
        betfair_config = config["betfair"]
        print("✓ Configuration loaded")
        
        # Initialize authenticator
        print("\n[2/4] Authenticating with Betfair...")
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config.get("password") or input("Enter Betfair password: "),
            cert_path=betfair_config["certificate_path"],
            key_path=betfair_config["key_path"],
            login_endpoint=betfair_config["login_endpoint"]
        )
        
        success, error = authenticator.login()
        if not success:
            print(f"✗ Login failed: {error}")
            return 1
        
        session_token = authenticator.get_session_token()
        print("✓ Login successful")
        
        # Initialize market service
        print("\n[3/4] Initializing market service...")
        market_service = MarketService(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            api_endpoint=betfair_config["api_endpoint"]
        )
        print("✓ Market service initialized")
        
        # Get all competitions using listMarketCatalogue with time windows
        # Strategy: Loop through monthly windows, extract competitions from markets, dedupe
        print("\n[4/4] Fetching competitions from Betfair API...")
        print("   Using listMarketCatalogue with time windows (2024-2030)...")
        print("   This method extracts competitions from markets for better coverage")
        event_type_ids = [1]  # 1 = Soccer/Football
        
        headers = {
            'X-Application': betfair_config["app_key"],
            'X-Authentication': session_token,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Use OrderedDict to dedupe competitions by ID while preserving order
        competitions_map = OrderedDict()
        
        # Generate monthly windows from 2024 to 2030
        start_year = 2024
        end_year = 2030
        total_windows = (end_year - start_year + 1) * 12
        current_window = 0
        
        print(f"   Processing {total_windows} monthly windows...")
        
        url = f"{betfair_config['api_endpoint']}/listMarketCatalogue/"
        
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                current_window += 1
                
                # Create time window (start of month to start of next month)
                from_date = datetime(year, month, 1)
                if month == 12:
                    to_date = datetime(year + 1, 1, 1)
                else:
                    to_date = datetime(year, month + 1, 1)
                
                from_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                to_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                
                try:
                    payload = {
                        "filter": {
                            "eventTypeIds": event_type_ids,
                            "marketStartTime": {
                                "from": from_str,
                                "to": to_str
                            }
                        },
                        "maxResults": 1000,
                        "marketProjection": ["COMPETITION"]
                    }
                    
                    response = requests.post(url, json=payload, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    result = response.json()
                    markets = result if isinstance(result, list) else []
                    
                    # Extract competitions from markets
                    for market in markets:
                        comp = None
                        
                        # Try to get competition from market.event.competition
                        if market.get("event") and market["event"].get("competition"):
                            comp = market["event"]["competition"]
                        # Try to get competition from market.competition
                        elif market.get("competition"):
                            comp = market["competition"]
                        
                        if comp and comp.get("id"):
                            comp_id = comp.get("id")
                            comp_name = comp.get("name", "Unknown")
                            
                            # Store competition (dedupe by ID)
                            if comp_id not in competitions_map:
                                competitions_map[comp_id] = {
                                    "competition": {
                                        "id": comp_id,
                                        "name": comp_name
                                    },
                                    "marketCount": 0
                                }
                            
                            # Increment market count
                            competitions_map[comp_id]["marketCount"] += 1
                    
                    # Progress update every 12 months (1 year)
                    if month == 1:
                        print(f"   Processed {current_window}/{total_windows} windows ({year}) - Found {len(competitions_map)} unique competitions so far...")
                    
                    # Throttle to avoid rate limit (500ms between requests)
                    time.sleep(0.5)
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 400:
                        # No markets in this window, skip
                        continue
                    else:
                        print(f"   ⚠ Error on window {from_str} to {to_str}: {e.response.status_code}")
                        # Continue to next window
                        time.sleep(1)
                        continue
                except Exception as e:
                    print(f"   ⚠ Error on window {from_str} to {to_str}: {str(e)[:100]}")
                    time.sleep(1)
                    continue
        
        # Convert to list format
        competitions = list(competitions_map.values())
        
        if not competitions:
            print("⚠ No competitions found or error occurred")
            return 1
        
        print(f"\n✓ Successfully fetched {len(competitions)} unique competitions from {total_windows} time windows")
        
        # Display competitions
        print("\n" + "=" * 60)
        print("BETFAIR COMPETITIONS LIST")
        print("=" * 60)
        
        # Sort by name for easier reading
        sorted_competitions = sorted(competitions, key=lambda x: x.get("competition", {}).get("name", "") if isinstance(x.get("competition"), dict) else str(x.get("competition", "")))
        
        for idx, comp in enumerate(sorted_competitions, 1):
            # Betfair competition structure
            comp_info = comp.get("competition", {})
            if isinstance(comp_info, dict):
                comp_id = comp_info.get("id", "N/A")
                comp_name = comp_info.get("name", "N/A")
                region = comp_info.get("region", "N/A")
            else:
                comp_id = comp.get("id", "N/A")
                comp_name = comp.get("name", "N/A")
                region = comp.get("region", "N/A")
            
            market_count = comp.get("marketCount", 0)
            
            print(f"{idx:4d}. ID: {comp_id:8s} | {comp_name:40s} | Region: {region:15s} | Markets: {market_count}")
        
        print("=" * 60)
        print(f"\n✅ Total: {len(competitions)} competitions")
        
        # Save to file (optional)
        project_root = Path(__file__).parent.parent
        output_file = project_root / "competitions" / "betfair_competitions.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(competitions, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Competitions data saved to: {output_file}")
        
        # Also save as simple text list
        txt_file = project_root / "competitions" / "betfair_competitions_list.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("Betfair API - Competitions List (Football/Soccer)\n")
            f.write("=" * 60 + "\n\n")
            for comp in sorted_competitions:
                comp_info = comp.get("competition", {})
                if isinstance(comp_info, dict):
                    comp_id = comp_info.get("id", "N/A")
                    comp_name = comp_info.get("name", "N/A")
                    region = comp_info.get("region", "N/A")
                else:
                    comp_id = comp.get("id", "N/A")
                    comp_name = comp.get("name", "N/A")
                    region = comp.get("region", "N/A")
                
                market_count = comp.get("marketCount", 0)
                f.write(f"ID: {comp_id:8s} | {comp_name:40s} | Region: {region:15s} | Markets: {market_count}\n")
        
        print(f"💾 Text list saved to: {txt_file}")
        
        # Show summary by region
        print("\n📊 Summary by Region:")
        region_counts = {}
        for comp in competitions:
            comp_info = comp.get("competition", {})
            if isinstance(comp_info, dict):
                region = comp_info.get("region", "Unknown")
            else:
                region = comp.get("region", "Unknown")
            region_counts[region] = region_counts.get(region, 0) + 1
        
        for region, count in sorted(region_counts.items()):
            print(f"  - {region}: {count} competitions")
        
        print("\n" + "=" * 60)
        print("✅ Test completed successfully!")
        print("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = test_betfair_competitions()
    sys.exit(exit_code)

