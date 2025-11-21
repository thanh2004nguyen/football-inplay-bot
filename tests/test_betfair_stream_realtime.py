# betfair_stream_realtime.py
# IMPORTANT: Betfair Stream API uses SSL socket, NOT WebSocket!
# Protocol: SSL socket with JSON messages terminated by CRLF
import ssl
import json
import time
import traceback
import socket
import requests
import sys
from pathlib import Path

# Add src to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from utils.auth_utils import perform_login_with_retry

# ---- CONFIG - Will be loaded in run() function ----
APP_KEY = None
SESSION_TOKEN = None
WS_URL = "wss://stream-api.betfair.com:443"
API_ENDPOINT = None

# Optional: path to your docs/screenshots (developer note)
DOC_SCREENSHOT = "file:///mnt/data/fdfe3f6d-d2a4-45df-b863-31c8c9722cd6.png"

# ---- Helper functions ----
def send_json(sock, obj):
    """Send a JSON message terminated with CRLF as required by Betfair stream protocol."""
    payload = json.dumps(obj) + "\r\n"
    sock.send(payload.encode('utf-8'))

def recv_message(sock, timeout=10):
    """
    Receive a message from socket (CRLF terminated JSON).
    Handles multiple messages in one buffer.
    """
    sock.settimeout(timeout)
    buffer = b""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                return None
            buffer += data
            
            # Check if we have at least one complete message (ends with CRLF)
            if b"\r\n" in buffer:
                # Split by CRLF and return first complete message
                parts = buffer.split(b"\r\n", 1)
                message = parts[0].decode('utf-8')
                # Keep remaining data in buffer for next call
                # Note: In a real implementation, you'd want to store buffer in a class variable
                # For now, we'll just return the first message
                return message
        except socket.timeout:
            # If we have data but no CRLF, might be incomplete - try to return it anyway
            if buffer:
                try:
                    # Try to decode what we have
                    message = buffer.decode('utf-8', errors='ignore')
                    # If it looks like valid JSON (starts with {), return it
                    if message.strip().startswith('{'):
                        return message.strip()
                except:
                    pass
            raise

def authenticate(sock):
    """Send authentication message."""
    auth_msg = {
        "op": "authentication",
        "appKey": APP_KEY,
        "session": SESSION_TOKEN
    }
    send_json(sock, auth_msg)

def get_inplay_market_ids(app_key, session_token, api_endpoint, max_results=200):
    """
    Get list of Under/Over market IDs using REST API (focused on Under/Over markets for faster execution).
    Also verify they are actually OPEN and in-play using MarketBook.
    
    Note: We don't filter by inPlay in catalogue because it may not be accurate.
    Instead, we get OPEN markets and verify in-play status using MarketBook.
    
    Returns:
        List of market IDs (strings) that are verified to be in-play and OPEN
    """
    print("  → Fetching Under/Over markets from REST API...")
    
    url = f"{api_endpoint}/listMarketCatalogue/"
    headers = {
        "X-Application": app_key,
        "X-Authentication": session_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Focus on Under/Over markets only (faster and more relevant for betting strategy)
    payload = {
        "filter": {
            "eventTypeIds": [1],  # Football (integer, not string)
            "marketTypeCodes": ["OVER_UNDER_05", "OVER_UNDER_15", "OVER_UNDER_25", "OVER_UNDER_35", "OVER_UNDER_45"],  # Under/Over markets only
            "inPlay": True  # Try to get in-play markets directly
        },
        "maxResults": max_results,  # Up to 200 to match Stream API limit
        "marketProjection": ["MARKET_DESCRIPTION"]  # Minimal projection to reduce data weight
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        # Check for errors
        if response.status_code != 200:
            error_text = response.text[:500] if response.text else "No error details"
            print(f"  ✗ HTTP {response.status_code}: {error_text}")
            return []
        
        response.raise_for_status()
        markets = response.json()
        
        # Betfair API returns a list directly (not wrapped in JSON-RPC)
        if not isinstance(markets, list):
            print(f"  ✗ Unexpected response format: {type(markets)}")
            print(f"  Response: {str(markets)[:200]}")
            return []
        
        # Extract market IDs and log some details
        market_ids = []
        market_details = []
        for m in markets:
            market_id = m.get("marketId")
            if market_id:
                market_ids.append(str(market_id))
                # Get event name for logging
                event = m.get("event", {})
                event_name = event.get("name", "unknown")
                market_details.append({
                    "id": str(market_id),
                    "event": event_name
                })
        
        print(f"  ✓ Found {len(market_ids)} Under/Over markets from catalogue (inPlay filter)")
        
        # Log sample matches for debugging
        if len(market_details) > 0:
            print(f"  → Sample: {market_details[0]['event']}")
            if len(market_details) > 1:
                print(f"  → Sample: {market_details[1]['event']}")
        
        # Return markets directly (inPlay filter from catalogue is sufficient)
        # No need to verify with MarketBook - it's too slow and causes TOO_MUCH_DATA errors
        return market_ids
        
    except requests.exceptions.HTTPError as e:
        error_text = e.response.text[:500] if e.response.text else "No error details"
        print(f"  ✗ HTTP Error: {e.response.status_code}")
        print(f"  Error details: {error_text}")
        return []
    except Exception as e:
        print(f"  ✗ Error fetching markets: {e}")
        import traceback
        traceback.print_exc()
        return []

def verify_markets_status(app_key, session_token, api_endpoint, market_ids):
    """
    Verify markets are actually OPEN and in-play using MarketBook.
    
    Returns:
        List of market IDs that are verified to be OPEN and in-play
    """
    if not market_ids:
        return []
    
    url = f"{api_endpoint}/listMarketBook/"
    headers = {
        "X-Application": app_key,
        "X-Authentication": session_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Verify in batches of 1 to avoid TOO_MUCH_DATA (with price data, need very small batches)
    # Note: Even with batch_size=1, some markets might still cause TOO_MUCH_DATA if they have many runners
    verified_ids = []
    batch_size = 1
    open_count = 0
    inplay_count = 0
    
    for i in range(0, len(market_ids), batch_size):
        batch = market_ids[i:i+batch_size]
        
        payload = {
            "marketIds": batch,
            "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}  # Need price data to get marketDefinition
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                market_books = response.json()
                if isinstance(market_books, list):
                    for book in market_books:
                        market_id = book.get("marketId")
                        md = book.get("marketDefinition")
                        
                        # Check if marketDefinition exists
                        if not md:
                            print(f"    ⚠ marketId={market_id} - No marketDefinition (may need price data)")
                            continue
                        
                        status = md.get("status", "")
                        in_play = md.get("inPlay", False)
                        event_name = md.get("eventName", "unknown")
                        
                        # Debug: count statuses
                        if status == "OPEN":
                            open_count += 1
                        if in_play:
                            inplay_count += 1
                        
                        # Only keep markets that are OPEN and in-play
                        if status == "OPEN" and in_play:
                            verified_ids.append(str(market_id))
                            print(f"    ✓ {event_name[:40]} - OPEN & in-play")
                        elif status == "OPEN" and not in_play:
                            # Debug: show markets that are OPEN but not in-play
                            print(f"    ⚠ {event_name[:40]} - OPEN but NOT in-play")
                        elif status and status != "OPEN":
                            print(f"    ⚠ {event_name[:40]} - status={status} (not OPEN)")
                else:
                    print(f"  ⚠ Batch {i//batch_size + 1}: Unexpected response format: {type(market_books)}")
            else:
                error_text = response.text[:200] if response.text else "No error details"
                print(f"  ⚠ Batch {i//batch_size + 1}: HTTP {response.status_code}: {error_text}")
        except Exception as e:
            print(f"  ⚠ Error verifying batch {i//batch_size + 1}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"  → Summary: {open_count} OPEN, {inplay_count} in-play, {len(verified_ids)} OPEN & in-play")
    return verified_ids

def get_market_details(app_key, session_token, api_endpoint, market_id):
    """
    Get detailed market information from REST API.
    
    Returns:
        Dict with event_id, event_name, competition_id, competition_name
    """
    url = f"{api_endpoint}/listMarketCatalogue/"
    headers = {
        "X-Application": app_key,
        "X-Authentication": session_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "filter": {
            "marketIds": [market_id]
        },
        "maxResults": 1,
        "marketProjection": ["COMPETITION", "EVENT", "MARKET_DESCRIPTION"]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            markets = response.json()
            if isinstance(markets, list) and len(markets) > 0:
                market = markets[0]
                event = market.get("event", {})
                competition = market.get("competition", {})
                
                return {
                    "event_id": event.get("id"),
                    "event_name": event.get("name"),
                    "competition_id": competition.get("id"),
                    "competition_name": competition.get("name"),
                    "market_name": market.get("marketName", "")
                }
    except Exception as e:
        pass
    
    return None

def subscribe_to_markets(sock, market_ids, subscription_id=1):
    """
    Subscribe to specific market IDs.
    
    Note: Betfair Stream API has a limit of 200 markets per subscription.
    
    Args:
        sock: SSL socket connection
        market_ids: List of market IDs to subscribe (max 200)
        subscription_id: Unique ID for this subscription
    """
    if len(market_ids) > 200:
        print(f"  ⚠ Warning: {len(market_ids)} markets requested, but limit is 200. Using first 200.")
        market_ids = market_ids[:200]
    
    sub_msg = {
      "op": "marketSubscription",
      "id": subscription_id,
      "marketFilter": {
        "marketIds": market_ids  # Subscribe to specific market IDs
      },
      "marketDataFilter": {
        "fields": ["EX_MARKET_DEF", "EX_ALL_OFFERS"]  # Get market definition and prices
      },
      "heartbeatMs": 5000,
      "conflateMs": 0
    }
    send_json(sock, sub_msg)
    print(f"  → Subscribed to {len(market_ids)} market(s) (subscription ID: {subscription_id})")

# Cache for market details to avoid repeated API calls
_market_details_cache = {}

def handle_message(raw):
    """
    Parse incoming message (JSON per CRLF). We look for 'op':'mcm' messages
    and ONLY print markets that are inPlay && status == 'OPEN'.
    """
    try:
        # Clean up the message - remove any trailing incomplete data
        raw_clean = raw.strip()
        # Try to find complete JSON (might have partial data at end)
        if raw_clean and not raw_clean.endswith('}'):
            # Try to find the last complete JSON object
            last_brace = raw_clean.rfind('}')
            if last_brace > 0:
                raw_clean = raw_clean[:last_brace + 1]
        
        msg = json.loads(raw_clean)
    except json.JSONDecodeError as e:
        # Log partial message for debugging (but don't spam)
        if len(raw) > 50:  # Only log if it's substantial
            print(f"⚠ Partial/invalid JSON (first 100 chars): {raw[:100]}...")
        return
    except Exception as e:
        print(f"⚠ Error parsing message: {e}")
        return

    op = msg.get("op")
    if op == "status" or op == "connection":
        print("SYSTEM:", msg)
        return

    if op == "mcm":  # MarketChangeMessage
        mc = msg.get("mc") or []
        for market in mc:
            mid = market.get("id")
            md = market.get("marketDefinition") or {}
            inplay = md.get("inPlay", False)
            status = md.get("status")
            
            # Try to get event info from various fields
            event_name = None
            event_id = None
            
            # Check event object first
            event_obj = md.get("event")
            if isinstance(event_obj, dict):
                event_name = event_obj.get("name")
                event_id = event_obj.get("id")
            
            # Fallback to other fields
            if not event_name:
                event_name = md.get("eventName")
            if not event_id:
                event_id = md.get("eventId")
            
            if not event_name:
                event_name = md.get("name") or "unknown"
            
            # Get competition info
            competition_name = None
            competition_id = None
            comp_obj = md.get("competition")
            if isinstance(comp_obj, dict):
                competition_name = comp_obj.get("name")
                competition_id = comp_obj.get("id")
            
            market_name = md.get("marketName") or md.get("name") or ""
            
            # ONLY print markets that are in-play and OPEN
            if inplay and status and status.upper() == "OPEN":
                # If we don't have event name, try to get it from REST API (with cache)
                if (not event_name or event_name == "unknown") and mid:
                    if mid not in _market_details_cache:
                        details = get_market_details(APP_KEY, SESSION_TOKEN, API_ENDPOINT, mid)
                        if details:
                            _market_details_cache[mid] = details
                        else:
                            _market_details_cache[mid] = {}  # Cache empty to avoid retry
                    
                    cached_details = _market_details_cache.get(mid, {})
                    if cached_details:
                        event_id = cached_details.get("event_id") or event_id
                        event_name = cached_details.get("event_name") or event_name
                        competition_id = cached_details.get("competition_id") or competition_id
                        competition_name = cached_details.get("competition_name") or competition_name
                        market_name = cached_details.get("market_name") or market_name
                
                # Build detailed display string
                info_parts = []
                if event_id:
                    info_parts.append(f"eventId={event_id}")
                if event_name and event_name != "unknown":
                    info_parts.append(f"event={event_name}")
                if competition_id:
                    info_parts.append(f"compId={competition_id}")
                if competition_name:
                    info_parts.append(f"comp={competition_name}")
                if market_name:
                    info_parts.append(f"market={market_name}")
                
                info_str = " | ".join(info_parts) if info_parts else "unknown"
                print(f"[LIVE][OPEN] marketId={mid} | {info_str} | inPlay={inplay} | status={status}")
            # Skip all other markets (not in-play or not OPEN)
            # Don't print them to reduce noise
    else:
        # Print other messages if you want (heartbeat, etc.)
        print("RECEIVED:", msg)

# ---- Main run loop with simple reconnect/backoff ----
def run():
    global APP_KEY, SESSION_TOKEN, API_ENDPOINT
    
    # Load config and login
    print("Loading configuration...")
    config = load_config()
    betfair_config = config["betfair"]
    APP_KEY = betfair_config["app_key"]
    API_ENDPOINT = betfair_config.get("api_endpoint", "https://api.betfair.com/exchange/betting/rest/v1.0")
    
    # Login to get session token
    use_password_login = betfair_config.get("use_password_login", False)
    cert_path = betfair_config.get("certificate_path") if not use_password_login else None
    key_path = betfair_config.get("key_path") if not use_password_login else None
    
    authenticator = BetfairAuthenticator(
        app_key=APP_KEY,
        username=betfair_config["username"],
        password=betfair_config.get("password", ""),
        cert_path=cert_path,
        key_path=key_path,
        login_endpoint=betfair_config.get("login_endpoint")
    )
    
    print("  → Logging in to get session token...")
    session_token, _ = perform_login_with_retry(config, authenticator, None)
    if not session_token:
        print("  ✗ Failed to login. Please check your credentials in config.json")
        return
    
    SESSION_TOKEN = session_token
    print(f"  ✓ Login successful (session token: {SESSION_TOKEN[:20]}...)")
    
    backoff = 1
    max_retries = 5
    
    print(f"Using App Key: {APP_KEY}")
    print(f"Session Token (first 20 chars): {SESSION_TOKEN[:20]}...")
    print(f"Connecting to Betfair Stream API (SSL socket, NOT WebSocket)")
    print(f"Host: stream-api.betfair.com:443")
    print("-" * 60)
    
    retry_count = 0
    while retry_count < max_retries:
        sock = None
        ssl_sock = None
        try:
            print(f"\n[Attempt {retry_count + 1}/{max_retries}] Connecting to stream-api.betfair.com:443")
            
            # Create SSL socket connection (NOT WebSocket!)
            # Step 1: Create TCP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            
            # Step 2: Connect to server
            print("  → Connecting TCP socket...")
            sock.connect(("stream-api.betfair.com", 443))
            print("  ✓ TCP connection established")
            
            # Step 3: Wrap with SSL
            print("  → Establishing SSL connection...")
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            ssl_sock = context.wrap_socket(sock, server_hostname="stream-api.betfair.com")
            print("  ✓ SSL connection established")
            
            # Step 4: Authenticate (must send within 15 seconds to avoid timeout)
            print("  → Authenticating...")
            authenticate(ssl_sock)
            
            # Step 5: Receive auth response
            print("  → Waiting for auth response...")
            auth_resp = recv_message(ssl_sock, timeout=10)
            if not auth_resp:
                raise Exception("No auth response received")
            
            print(f"  ✓ Auth response received: {auth_resp[:100]}...")
            
            # Parse auth response
            try:
                auth_data = json.loads(auth_resp.strip())
                if auth_data.get("op") == "status":
                    status_code = auth_data.get("statusCode")
                    if status_code != "SUCCESS":
                        error_msg = auth_data.get("error", "Unknown error")
                        print(f"  ✗ Authentication failed: {status_code} - {error_msg}")
                        raise Exception(f"Auth failed: {status_code}")
                    print("  ✓ Authentication successful")
            except json.JSONDecodeError as e:
                print(f"  ⚠ Could not parse auth response as JSON: {auth_resp[:200]}")
                print(f"  Error: {e}")

            # Step 6: Get in-play markets and subscribe
            print("  → Getting in-play markets from REST API...")
            print("  → Note: Stream API filter returns too many markets (11140), so we'll use market IDs")
            
            # Get markets with inPlay filter from REST API
            # This is more accurate and we can control the number
            market_ids = get_inplay_market_ids(APP_KEY, SESSION_TOKEN, API_ENDPOINT, max_results=200)
            
            if not market_ids:
                print("  ✗ No Under/Over markets found. Exiting.")
                print("  → Note: If you see matches on Betfair website, they may not be in-play yet or may not have Under/Over markets")
                return
            
            print(f"  → Found {len(market_ids)} Under/Over market(s) to subscribe")
            
            # Betfair Stream API limit: 200 markets per subscription
            # If we have more than 200, we can create multiple subscriptions
            max_markets_per_sub = 200
            if len(market_ids) <= max_markets_per_sub:
                # Single subscription
                print(f"  → Subscribing to {len(market_ids)} market(s)...")
                subscribe_to_markets(ssl_sock, market_ids, subscription_id=1)
            else:
                # Multiple subscriptions (batches)
                num_batches = (len(market_ids) + max_markets_per_sub - 1) // max_markets_per_sub
                print(f"  → Creating {num_batches} subscription(s) (200 markets each)...")
                
                for i in range(num_batches):
                    start_idx = i * max_markets_per_sub
                    end_idx = min(start_idx + max_markets_per_sub, len(market_ids))
                    batch = market_ids[start_idx:end_idx]
                    subscribe_to_markets(ssl_sock, batch, subscription_id=i+1)
                    if i < num_batches - 1:
                        time.sleep(0.5)  # Small delay between subscriptions
            
            print("  ✓ All subscriptions sent")

            # reset backoff after success
            backoff = 1
            retry_count = 0  # Reset retry count on success

            # Step 7: Main receive loop
            print("\n" + "="*60)
            print("Listening for market updates...")
            print("="*60 + "\n")
            
            # Use a buffer to handle partial messages and multiple messages in one recv
            message_buffer = b""
            
            while True:
                try:
                    # Receive data (may contain multiple messages or partial message)
                    ssl_sock.settimeout(30)
                    data = ssl_sock.recv(4096)
                    if not data:
                        continue
                    
                    message_buffer += data
                    
                    # Process all complete messages (separated by CRLF)
                    while b"\r\n" in message_buffer:
                        parts = message_buffer.split(b"\r\n", 1)
                        complete_message = parts[0].decode('utf-8', errors='ignore')
                        message_buffer = parts[1] if len(parts) > 1 else b""
                        
                        if complete_message.strip():
                            handle_message(complete_message)
                    
                except socket.timeout:
                    # Send heartbeat to keep connection alive
                    heartbeat_msg = {"op": "heartbeat", "id": 999}
                    send_json(ssl_sock, heartbeat_msg)
                    print("[Heartbeat sent]")
                except Exception as e:
                    print(f"Error receiving message: {e}")
                    raise

        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting.")
            if ssl_sock:
                try:
                    ssl_sock.close()
                except:
                    pass
            if sock:
                try:
                    sock.close()
                except:
                    pass
            return
        except socket.error as e:
            print(f"✗ Socket error: {str(e)}")
            if ssl_sock:
                try:
                    ssl_sock.close()
                except:
                    pass
            if sock:
                try:
                    sock.close()
                except:
                    pass
            retry_count += 1
            if retry_count >= max_retries:
                print(f"\n✗ Max retries ({max_retries}) reached. Exiting.")
                return
            print(f"Reconnecting after {backoff} seconds...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except ssl.SSLError as e:
            print(f"✗ SSL error: {str(e)}")
            if ssl_sock:
                try:
                    ssl_sock.close()
                except:
                    pass
            if sock:
                try:
                    sock.close()
                except:
                    pass
            retry_count += 1
            if retry_count >= max_retries:
                print(f"\n✗ Max retries ({max_retries}) reached. Exiting.")
            return
            print(f"Reconnecting after {backoff} seconds...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            print(f"✗ Connection error ({error_type}): {error_msg}")
            
            if ssl_sock:
                try:
                    ssl_sock.close()
                except:
                    pass
            if sock:
                try:
                    sock.close()
                except:
                    pass
            
            retry_count += 1
            if retry_count >= max_retries:
                print(f"\n✗ Max retries ({max_retries}) reached. Exiting.")
                print("\nTroubleshooting tips:")
                print("  1. Verify session token is fresh (run main bot to get new token)")
                print("  2. Check if App Key is activated for Stream API")
                print("  3. Check network connectivity to stream-api.betfair.com")
                print("  4. Ensure you're using SSL socket (not WebSocket)")
                return
            
            print(f"Reconnecting after {backoff} seconds... (attempt {retry_count + 1}/{max_retries})")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)  # exponential backoff, capped at 60s

if __name__ == "__main__":
    print("Doc screenshot (if needed):", DOC_SCREENSHOT)
    run()
