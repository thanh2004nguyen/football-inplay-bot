"""
Betfair Italy Bot - Main Entry Point
Milestone 1: Authentication & Market Detection
"""
import sys
import time
import requests
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.loader import load_config, validate_config
from config.competition_mapper import get_competition_ids_from_excel
from core.logging_setup import setup_logging
from auth.cert_login import BetfairAuthenticator
from auth.keep_alive import KeepAliveManager
from betfair.market_service import MarketService


def main():
    """Main function for Milestone 1"""
    print("=" * 60)
    print("Betfair Italy Bot - Milestone 1")
    print("Authentication & Market Detection")
    print("=" * 60)
    
    try:
        # Load configuration
        print("\n[1/5] Loading configuration...")
        config = load_config()
        validate_config(config)
        print("✓ Configuration loaded and validated")
        
        # Setup logging
        print("\n[2/5] Setting up logging...")
        logger = setup_logging(config["logging"])
        logger.info("=" * 60)
        logger.info("Betfair Italy Bot - Milestone 1 Started")
        logger.info("=" * 60)
        print("✓ Logging initialized")
        
        # Initialize authenticator
        print("\n[3/5] Initializing authentication...")
        betfair_config = config["betfair"]
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config["password"],
            cert_path=betfair_config["certificate_path"],
            key_path=betfair_config["key_path"],
            login_endpoint=betfair_config["login_endpoint"]
        )
        print("✓ Authenticator initialized")
        
        # Perform login
        print("\n[4/5] Logging in to Betfair Italy Exchange...")
        success, error = authenticator.login()
        
        if not success:
            logger.error(f"Login failed: {error}")
            print(f"✗ Login failed: {error}")
            print("\nPlease check:")
            print("  - Certificate files exist and are correct")
            print("  - Username and password are correct")
            print("  - App Key is valid")
            print("  - Certificate is uploaded to your Betfair account")
            return 1
        
        session_token = authenticator.get_session_token()
        logger.info("Login successful - proceeding to market detection")
        print("✓ Login successful!")
        
        # Initialize market service first (needed for callback)
        print("\n[Market Detection] Initializing market service...")
        market_service = MarketService(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            api_endpoint=betfair_config["api_endpoint"]
        )
        print("✓ Market service initialized")
        
        # Initialize keep-alive (callback will be set after creation)
        print("\n[5/5] Starting keep-alive manager...")
        keep_alive_interval = config["session"].get("keep_alive_interval_seconds", 300)
        keep_alive_manager = KeepAliveManager(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            keep_alive_interval=keep_alive_interval
        )
        
        # Define callback for session expiry detected by keep-alive
        def handle_session_expired():
            """Callback when keep-alive detects session expiry"""
            logger.warning("Session expiry detected by keep-alive, attempting re-login...")
            try:
                success, error = authenticator.login()
                if success:
                    new_token = authenticator.get_session_token()
                    market_service.update_session_token(new_token)
                    keep_alive_manager.update_session_token(new_token)
                    logger.info("Re-login successful after keep-alive detected expiry")
                else:
                    logger.warning(f"Re-login failed after keep-alive expiry: {error}")
            except Exception as e:
                logger.error(f"Error during re-login from keep-alive callback: {str(e)}")
        
        # Set callback after keep_alive_manager is created
        keep_alive_manager.on_session_expired = handle_session_expired
        keep_alive_manager.start()
        print("✓ Keep-alive manager started")
        
        # Get account funds (test API connection)
        print("\n[Test] Retrieving account funds...")
        account_funds = market_service.get_account_funds()
        if account_funds:
            available_balance = account_funds.get("availableToBetBalance", "N/A")
            logger.info(f"Account balance: {available_balance}")
            print(f"✓ Account balance retrieved: {available_balance}")
        else:
            print("⚠ Could not retrieve account balance (non-critical)")
        
        # Market Detection
        print("\n" + "=" * 60)
        print("MARKET DETECTION")
        print("=" * 60)
        
        monitoring_config = config["monitoring"]
        event_type_ids = monitoring_config.get("event_type_ids", [1])
        competition_ids = monitoring_config.get("competition_ids", [])
        in_play_only = monitoring_config.get("in_play_only", True)
        polling_interval = monitoring_config.get("polling_interval_seconds", 10)
        
        # Try to map competitions from Excel file if competition_ids is empty
        if not competition_ids:
            # Get project root (parent of src directory)
            project_root = Path(__file__).parent.parent
            excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
            if excel_path.exists():
                print(f"\n[Competition Mapping] Reading competitions from Excel file...")
                logger.info("Attempting to map competitions from Excel file")
                
                # Get all competitions from Betfair
                betfair_competitions = market_service.list_competitions(event_type_ids)
                
                if betfair_competitions:
                    # Map Excel competitions to Betfair IDs
                    mapped_ids = get_competition_ids_from_excel(
                        str(excel_path),
                        betfair_competitions
                    )
                    
                    if mapped_ids:
                        competition_ids = mapped_ids
                        logger.info(f"Mapped {len(competition_ids)} competitions from Excel to Betfair IDs")
                        print(f"✓ Mapped {len(competition_ids)} competitions from Excel file")
                    else:
                        logger.warning("No competitions matched from Excel file, monitoring all competitions")
                        print("⚠ No competitions matched from Excel, monitoring all competitions")
                else:
                    logger.warning("Could not retrieve competitions from Betfair API")
                    print("⚠ Could not retrieve competitions from Betfair, monitoring all competitions")
            else:
                logger.info("Excel file not found, monitoring all competitions")
                print("ℹ Excel file not found, monitoring all competitions")
        
        logger.info(f"Monitoring configuration:")
        logger.info(f"  - Event Type IDs: {event_type_ids}")
        logger.info(f"  - Competition IDs: {competition_ids if competition_ids else 'All'}")
        logger.info(f"  - In-play only: {in_play_only}")
        logger.info(f"  - Polling interval: {polling_interval}s")
        
        print(f"\nMonitoring settings:")
        print(f"  - Event Types: {event_type_ids}")
        print(f"  - Competitions: {len(competition_ids) if competition_ids else 'All'} competition(s)")
        if competition_ids:
            print(f"    IDs: {competition_ids[:10]}{'...' if len(competition_ids) > 10 else ''}")
        print(f"  - In-play only: {in_play_only}")
        print(f"  - Polling interval: {polling_interval} seconds")
        
        # Main detection loop
        print(f"\n[Market Detection] Starting detection loop...")
        print("Press Ctrl+C to stop\n")
        
        iteration = 0
        retry_delay = 5
        consecutive_errors = 0
        max_consecutive_errors = 10  # Log warning after 10 consecutive errors
        
        while True:
            iteration += 1
            logger.info(f"--- Detection iteration #{iteration} ---")
            
            try:
                # Get market catalogue
                markets = market_service.list_market_catalogue(
                    event_type_ids=event_type_ids,
                    competition_ids=competition_ids if competition_ids else None,
                    in_play_only=in_play_only
                )
                
                if markets:
                    logger.info(f"Found {len(markets)} in-play markets")
                    print(f"\n[{iteration}] Found {len(markets)} in-play market(s):")
                    
                    # Log details of each market
                    for i, market in enumerate(markets[:10], 1):  # Show first 10
                        market_id = market.get("marketId", "N/A")
                        market_name = market.get("marketName", "N/A")
                        event_name = market.get("event", {}).get("name", "N/A")
                        competition_name = market.get("competition", {}).get("name", "N/A")
                        
                        logger.info(f"  Market {i}:")
                        logger.info(f"    ID: {market_id}")
                        logger.info(f"    Name: {market_name}")
                        logger.info(f"    Event: {event_name}")
                        logger.info(f"    Competition: {competition_name}")
                        
                        print(f"  [{i}] {event_name} - {market_name}")
                        print(f"      Market ID: {market_id}")
                        print(f"      Competition: {competition_name}")
                    
                    if len(markets) > 10:
                        print(f"  ... and {len(markets) - 10} more markets")
                        logger.info(f"  ... and {len(markets) - 10} more markets (not shown)")
                else:
                    logger.info("No in-play markets found")
                    print(f"[{iteration}] No in-play markets found")
                
                # Reset error counter on success
                consecutive_errors = 0
                
                # Wait before next iteration
                try:
                    time.sleep(polling_interval)
                except KeyboardInterrupt:
                    logger.info("Interrupted by user during polling wait")
                    print("\n\nStopping...")
                    break
                
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                print("\n\nStopping...")
                break
            except requests.exceptions.RequestException as e:
                # Network/connection errors - retry indefinitely
                consecutive_errors += 1
                error_msg = str(e)
                
                # Check if it's a network connectivity issue (no internet)
                is_no_internet = any(keyword in error_msg for keyword in [
                    "getaddrinfo failed",
                    "NameResolutionError",
                    "Failed to resolve",
                    "unreachable host",
                    "Connection refused"
                ])
                
                if is_no_internet:
                    logger.warning(f"No internet connection (attempt {consecutive_errors}): {error_msg[:100]}")
                    print(f"⚠ No internet connection (attempt {consecutive_errors}), waiting for connection...")
                else:
                    logger.warning(f"Network error in detection loop (attempt {consecutive_errors}): {error_msg[:100]}")
                    print(f"⚠ Network error (attempt {consecutive_errors}), attempting to reconnect...")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(f"Multiple consecutive network errors ({consecutive_errors}). Bot will keep retrying...")
                    if is_no_internet:
                        print(f"⚠ No internet connection ({consecutive_errors} attempts). Bot will keep retrying until connection is restored...")
                    else:
                        print(f"⚠ Multiple connection errors ({consecutive_errors}). Bot will keep retrying until connection is restored...")
                
                # Only try re-login if we have internet (not a DNS/connection error)
                # If no internet, re-login will also fail, so skip it
                if not is_no_internet:
                    try:
                        success, error = authenticator.login()
                        if success:
                            new_token = authenticator.get_session_token()
                            market_service.update_session_token(new_token)
                            keep_alive_manager.update_session_token(new_token)
                            logger.info("Re-login successful, continuing...")
                            print("✓ Reconnected successfully")
                            consecutive_errors = 0  # Reset on successful re-login
                        else:
                            logger.warning(f"Re-login failed (will retry): {error}")
                            print(f"⚠ Re-login failed, will retry in {retry_delay}s...")
                    except Exception as login_error:
                        # If re-login also fails with network error, treat as no internet
                        login_error_msg = str(login_error)
                        if any(keyword in login_error_msg for keyword in [
                            "getaddrinfo failed", "NameResolutionError", "Failed to resolve", "unreachable host"
                        ]):
                            logger.warning(f"No internet connection - skipping re-login attempt")
                            print(f"⚠ No internet - will retry when connection is restored...")
                        else:
                            logger.warning(f"Re-login attempt failed (will retry): {login_error_msg[:100]}")
                            print(f"⚠ Re-login failed, will retry in {retry_delay}s...")
                
                # Wait before retry (bot will keep retrying indefinitely)
                try:
                    time.sleep(retry_delay)
                except KeyboardInterrupt:
                    logger.info("Interrupted by user during retry wait")
                    print("\n\nStopping...")
                    break
                
            except Exception as e:
                # Check if it's an authentication error (401)
                error_str = str(e)
                if "401" in error_str or "INVALID_SESSION" in error_str or "UNAUTHORIZED" in error_str:
                    consecutive_errors += 1
                    logger.warning(f"Session expired (attempt {consecutive_errors}), attempting re-login...")
                    print(f"⚠ Session expired, re-login (attempt {consecutive_errors})...")
                    
                    # Re-login
                    try:
                        success, error = authenticator.login()
                        if success:
                            new_token = authenticator.get_session_token()
                            market_service.update_session_token(new_token)
                            keep_alive_manager.update_session_token(new_token)
                            logger.info("Re-login successful after session expiry")
                            print("✓ Re-login successful")
                            consecutive_errors = 0
                        else:
                            logger.warning(f"Re-login failed (will retry): {error}")
                            print(f"⚠ Re-login failed, will retry in {retry_delay}s...")
                    except Exception as login_error:
                        logger.warning(f"Re-login attempt failed (will retry): {str(login_error)}")
                        print(f"⚠ Re-login failed, will retry in {retry_delay}s...")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during session re-login wait")
                        print("\n\nStopping...")
                        break
                else:
                    logger.error(f"Error in detection loop: {str(e)}", exc_info=True)
                    print(f"Error: {str(e)}")
                    consecutive_errors += 1
                    try:
                        time.sleep(polling_interval)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during error recovery")
                        print("\n\nStopping...")
                        break
        
        # Cleanup
        print("\n[Cleanup] Stopping keep-alive manager...")
        keep_alive_manager.stop()
        logger.info("Milestone 1 completed successfully")
        print("✓ Done")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease ensure:")
        print("  1. config/config.json exists and is properly configured")
        print("  2. Certificate files exist at specified paths")
        return 1
    except ValueError as e:
        print(f"\n✗ Configuration validation error: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        if 'logger' in locals():
            logger.exception("Unexpected error in main")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

