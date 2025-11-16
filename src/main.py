"""
Betfair Italy Bot - Main Entry Point
Milestone 2: Authentication, Market Detection & Live Data Integration
"""
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any, Set, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.loader import load_config, validate_config
from config.competition_mapper import get_competition_ids_from_excel, get_competitions_with_zero_zero_exception
from betfair.market_filter import filter_match_specific_markets
from core.logging_setup import setup_logging
from auth.cert_login import BetfairAuthenticator
from auth.keep_alive import KeepAliveManager
from betfair.market_service import MarketService
from football_api.live_score_client import LiveScoreClient
from football_api.parser import parse_match_score, parse_match_minute, parse_goals_timeline, parse_match_teams, parse_match_competition
from football_api.matcher import MatchMatcher
from logic.match_tracker import MatchTrackerManager, MatchTracker, MatchState
from logic.bet_executor import execute_lay_bet
from tracking.bet_tracker import BetTracker
from tracking.excel_writer import ExcelWriter
from tracking.skipped_matches_writer import SkippedMatchesWriter
from betfair.betting_service import BettingService
from notifications.sound_notifier import SoundNotifier
from notifications.email_notifier import EmailNotifier
from notifications.telegram_notifier import TelegramNotifier
import logging
from datetime import datetime

logger = logging.getLogger("BetfairBot")


def format_boxed_message(message: str) -> str:
    """
    Format a message with a box border
    
    Args:
        message: Message to display in box
    
    Returns:
        Formatted string with box border
    """
    # Calculate box width (minimum 60, or message length + 4 for padding)
    width = max(60, len(message) + 4)
    
    # Create box
    top_border = "┌" + "─" * (width - 2) + "┐"
    bottom_border = "└" + "─" * (width - 2) + "┘"
    
    # Center message in box
    padding = (width - len(message) - 2) // 2
    left_padding = " " * padding
    right_padding = " " * (width - len(message) - 2 - padding)
    content = f"│{left_padding}{message}{right_padding}│"
    
    return f"{top_border}\n{content}\n{bottom_border}"


def determine_bet_outcome(final_score: str, selection: str, target_over: Optional[float] = None) -> str:
    """
    Determine bet outcome from final score for Over/Under markets
    
    Args:
        final_score: Final match score (e.g., "2-1", "0-0")
        selection: Bet selection (e.g., "Under 2.5", "Over 2.5")
        target_over: Target Over X.5 value (e.g., 2.5 for Over 2.5)
    
    Returns:
        "Won", "Lost", or "Void"
    """
    try:
        # Parse final score
        parts = final_score.split("-")
        if len(parts) != 2:
            logger.warning(f"Invalid score format: {final_score}")
            return "Void"
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        total_goals = home_goals + away_goals
        
        # Extract target from selection if target_over not provided
        if target_over is None:
            # Try to extract from selection (e.g., "Over 2.5" -> 2.5)
            import re
            match = re.search(r'(\d+\.?\d*)', selection)
            if match:
                target_over = float(match.group(1))
            else:
                logger.warning(f"Could not extract target from selection: {selection}")
                return "Void"
        
        # Determine outcome based on selection type
        selection_lower = selection.lower()
        
        if "over" in selection_lower:
            # Over X.5: Won if total_goals > target_over
            if total_goals > target_over:
                return "Won"
            else:
                return "Lost"
        elif "under" in selection_lower:
            # Under X.5: Won if total_goals < target_over
            if total_goals < target_over:
                return "Won"
            else:
                return "Lost"
        else:
            logger.warning(f"Unknown selection type: {selection}")
            return "Void"
            
    except (ValueError, IndexError) as e:
        logger.warning(f"Error determining bet outcome: {str(e)}")
        return "Void"


def process_finished_matches(match_tracker_manager: MatchTrackerManager,
                             bet_tracker: Optional[BetTracker],
                             excel_writer: Optional[ExcelWriter],
                             target_over: Optional[float] = None,
                             telegram_notifier: Optional[Any] = None):
    """
    Process finished matches: settle bets and export to Excel
    
    Args:
        match_tracker_manager: Match tracker manager
        bet_tracker: Bet tracker instance (None if not initialized)
        excel_writer: Excel writer instance (None if not initialized)
        target_over: Target Over X.5 value for determining bet outcomes
    """
    if not bet_tracker or not excel_writer:
        return
    
    # Get all finished trackers
    all_trackers = match_tracker_manager.get_all_trackers()
    finished_trackers = [t for t in all_trackers if t.state == MatchState.FINISHED]
    
    for tracker in finished_trackers:
        # Get final score
        final_score = tracker.current_score
        
        # Find bets for this match
        bets = bet_tracker.get_bets_by_match_id(tracker.betfair_event_id)
        
        if bets:
            logger.info(f"Processing {len(bets)} bet(s) for finished match: {tracker.betfair_event_name} (Final: {final_score})")
            
            for bet_record in bets:
                # Skip if already settled
                if bet_record.outcome is not None:
                    continue
                
                # Determine outcome
                outcome = determine_bet_outcome(
                    final_score=final_score,
                    selection=bet_record.selection,
                    target_over=target_over
                )
                
                # Settle bet
                settled_bet = bet_tracker.settle_bet(bet_record.bet_id, outcome)
                
                if settled_bet:
                    # Send Telegram notification for Won/Lost bets only
                    if telegram_notifier and outcome in ["Won", "Lost"]:
                        try:
                            telegram_notifier.send_bet_settled_notification(
                                bet_record=settled_bet,
                                outcome=outcome,
                                profit_loss=settled_bet.profit_loss,
                                final_score=final_score,
                                event_name=tracker.betfair_event_name
                            )
                        except Exception as e:
                            logger.error(f"Failed to send Telegram bet settled notification: {str(e)}")
                    
                    # Export to Excel
                    try:
                        bet_dict = settled_bet.to_dict()
                        excel_writer.append_bet_record(bet_dict)
                        logger.info(f"Bet {settled_bet.bet_id} settled and exported: {outcome}, P/L: {settled_bet.profit_loss:.2f}")
                    except Exception as e:
                        logger.error(f"Error exporting bet {settled_bet.bet_id} to Excel: {str(e)}")


def main():
    """Main function for Milestone 2"""
    print("=" * 60)
    print("Betfair Italy Bot - Milestone 2")
    print("Authentication, Market Detection & Live Data Integration")
    print("=" * 60)
    
    try:
        # Load configuration
        print("\n[1/6] Loading configuration...")
        config = load_config()
        validate_config(config)
        print("✓ Configuration loaded and validated")
        
        # Setup logging
        print("\n[2/6] Setting up logging...")
        logger = setup_logging(config["logging"])
        logger.info("=" * 60)
        logger.info("Betfair Italy Bot - Milestone 2 Started")
        logger.info("=" * 60)
        print("✓ Logging initialized")
        
        # Initialize authenticator
        print("\n[3/6] Initializing authentication...")
        betfair_config = config["betfair"]
        use_password_login = betfair_config.get("use_password_login", False)
        
        # Certificate paths are optional for password login
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
        
        login_method = "Password-based" if use_password_login else "Certificate-based"
        print(f"✓ Authenticator initialized ({login_method} login)")
        
        # Initialize Email Notifier (Milestone 4) - before login to detect login issues
        email_notifier = None
        notifications_config = config.get("notifications", {})
        if notifications_config.get("email_enabled", False):
            try:
                email_notifier = EmailNotifier(notifications_config)
                logger.info("Email notifier initialized")
                print("✓ Email notifications enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize email notifier: {str(e)}")
                print("⚠ Email notifications disabled (initialization failed)")
        
        # Perform login with retry logic
        print("\n[4/6] Logging in to Betfair Italy Exchange...")
        retry_delay = config.get("session", {}).get("retry_delay_seconds", 10)
        max_login_attempts = 999999  # Infinite retry
        login_attempt = 0
        session_token = None
        # Email flags: Track if email already sent to avoid sending multiple times
        # These flags persist for the entire bot session (even if re-login happens later)
        email_sent_for_maintenance = False  # Track if email already sent for maintenance
        email_sent_for_terms = False  # Track if email already sent for terms
        
        while login_attempt < max_login_attempts:
            try:
                login_attempt += 1
                
                # Use password login or certificate login based on config
                if use_password_login:
                    success, error = authenticator.login_with_password()
                else:
                    success, error = authenticator.login()
                
                if success:
                    session_token = authenticator.get_session_token()
                    logger.info("Login successful - proceeding to market detection")
                    print("✓ Login successful!")
                    break
                else:
                    # Check if it's a maintenance/regulator error
                    is_maintenance_error = "UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT" in str(error)
                    
                    # Check if it's a connectivity/regulator error (should retry)
                    is_retryable_error = is_maintenance_error or any(keyword in str(error) for keyword in [
                        "UNAVAILABLE_CONNECTIVITY",
                        "CONNECTION",
                        "TIMEOUT",
                        "NETWORK"
                    ])
                    
                    # Only show retry message on first attempt and every 10 attempts (1, 11, 21, 31...)
                    should_show_retry = (login_attempt == 1) or (login_attempt % 10 == 1)
                    
                    if is_maintenance_error:
                        # Maintenance error - show maintenance message only once
                        if login_attempt == 1:
                            print(f"⚠ Betfair Italy Exchange is under maintenance. Check status: https://www.betfair.it")
                            logger.warning(f"Betfair maintenance detected: {error}")
                            logger.info("Check service status at: https://www.betfair.it")
                            
                            # Send email notification for maintenance (only once per bot session)
                            # Check both conditions: first attempt AND email not sent yet
                            if login_attempt == 1 and email_notifier and not email_sent_for_maintenance:
                                try:
                                    email_notifier.send_betfair_maintenance_alert(str(error))
                                    email_sent_for_maintenance = True  # Set flag to prevent sending again
                                    logger.info("Email alert sent for Betfair maintenance (will not send again this session)")
                                except Exception as e:
                                    logger.error(f"Failed to send maintenance email: {str(e)}")
                        
                        # Only show retry message on first attempt and every 10 attempts
                        if should_show_retry:
                            print(f"   Retrying in {retry_delay} seconds... (attempt {login_attempt})")
                        
                        try:
                            time.sleep(retry_delay)
                        except KeyboardInterrupt:
                            logger.info("Interrupted by user during login retry")
                            print("\n\nStopping...")
                            return 1
                    elif is_retryable_error:
                        # Other retryable errors - only show on first attempt
                        if login_attempt == 1:
                            print(f"⚠ Login failed: {error}")
                        
                        # Only show retry message on first attempt and every 10 attempts
                        if should_show_retry:
                            print(f"   Retrying in {retry_delay} seconds... (attempt {login_attempt})")
                        
                        try:
                            time.sleep(retry_delay)
                        except KeyboardInterrupt:
                            logger.info("Interrupted by user during login retry")
                            print("\n\nStopping...")
                            return 1
                    else:
                        # Non-retryable error (e.g., invalid credentials, contract acceptance)
                        # Check if it's a terms/conditions error
                        error_str = str(error).upper()
                        is_terms_error = any(keyword in error_str for keyword in [
                            "TERMS", "CONDITIONS", "ACCEPT", "CONFIRMATION", "CONTRACT",
                            "AGREEMENT", "ACCEPTANCE", "REQUIRED"
                        ])
                        
                        # Only log to file for retry attempts, print to console only on first attempt
                        if login_attempt == 1:
                            logger.error(f"Login failed: {error}")
                            print(f"✗ Login failed: {error}")
                            print(f"\nPlease check: https://www.betfair.it/ app_key, Username, password.")
                            
                            # Send email notification for terms/conditions (only once per bot session)
                            # Check both conditions: first attempt AND email not sent yet AND is terms error
                            if login_attempt == 1 and is_terms_error and email_notifier and not email_sent_for_terms:
                                try:
                                    email_notifier.send_betfair_terms_confirmation_alert(str(error))
                                    email_sent_for_terms = True  # Set flag to prevent sending again
                                    logger.info("Email alert sent for Betfair terms confirmation (will not send again this session)")
                                except Exception as e:
                                    logger.error(f"Failed to send terms confirmation email: {str(e)}")
                        # For subsequent attempts, already logged above with logger.debug()
                        
                        # Only show retry message on first attempt and every 10 attempts
                        if should_show_retry:
                            print(f"\nRetrying in {retry_delay} seconds... (attempt {login_attempt}) (Press Ctrl+C to stop)")
                        
                        try:
                            time.sleep(retry_delay)
                        except KeyboardInterrupt:
                            logger.info("Interrupted by user during login retry")
                            print("\n\nStopping...")
                            return 1
            except KeyboardInterrupt:
                # Handle Ctrl+C even when it happens during HTTP request
                logger.info("Interrupted by user during login attempt")
                print("\n\nStopping...")
                return 1
        
        if not session_token:
            logger.error("Failed to obtain session token after all retry attempts")
            print("✗ Failed to login after multiple attempts")
            return 1
        
        # Initialize Service Factory (for test mode support)
        from core.service_factory import ServiceFactory
        service_factory = ServiceFactory(config)
        
        # Initialize market service first (needed for callback)
        print("\n[Market Detection] Initializing market service...")
        # Get max data weight points from config (default 190)
        betfair_api_config = config.get("betfair_api", {})
        max_data_weight_points = betfair_api_config.get("max_data_weight_points", 190)
        
        # Use factory to create market service (real or mock)
        market_service = service_factory.create_market_service(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            api_endpoint=betfair_config["api_endpoint"],
            account_endpoint=betfair_config.get("account_endpoint", "https://api.betfair.com/exchange/account/rest/v1.0")
        )
        
        # Set max_data_weight_points for real MarketService (mock service doesn't need it)
        if not service_factory.is_test_mode and hasattr(market_service, 'max_data_weight_points'):
            market_service.max_data_weight_points = max_data_weight_points
        
        if service_factory.is_test_mode:
            print("✓ Market service initialized (TEST MODE)")
        else:
            print("✓ Market service initialized")
        
        # Initialize keep-alive (callback will be set after creation)
        print("\n[5/6] Starting keep-alive manager...")
        keep_alive_interval = config["session"].get("keep_alive_interval_seconds", 300)
        keep_alive_manager = KeepAliveManager(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            keep_alive_interval=keep_alive_interval
        )
        
        # Define callback for session expiry detected by keep-alive
        def handle_session_expired():
            """Callback when keep-alive detects session expiry"""
            # Note: We do NOT send email notifications here to avoid spam.
            # Email notifications are only sent during initial login (first attempt).
            # Re-login failures are logged but do not trigger email alerts.
            logger.warning("Session expiry detected by keep-alive, attempting re-login...")
            try:
                # Use password login or certificate login based on config
                if use_password_login:
                    success, error = authenticator.login_with_password()
                else:
                    success, error = authenticator.login()
                if success:
                    new_token = authenticator.get_session_token()
                    market_service.update_session_token(new_token)
                    keep_alive_manager.update_session_token(new_token)
                    # Update betting service if it exists (Milestone 3)
                    if betting_service:
                        betting_service.update_session_token(new_token)
                    logger.info("Re-login successful after keep-alive detected expiry")
                else:
                    logger.warning(f"Re-login failed after keep-alive expiry: {error}")
            except Exception as e:
                logger.error(f"Error during re-login from keep-alive callback: {str(e)}")
        
        # Set callback after keep_alive_manager is created
        keep_alive_manager.on_session_expired = handle_session_expired
        keep_alive_manager.start()
        print("✓ Keep-alive manager started")
        
        # Initialize Live Score API client
        print("\n[6/6] Initializing Live Score API client...")
        live_score_config = config.get("live_score_api", {})
        if not live_score_config:
            logger.warning("Live Score API config not found, skipping Live Score integration")
            print("⚠ Live Score API config not found")
            live_score_client = None
            match_matcher = None
            match_tracker_manager = None
            zero_zero_exception_competitions: Set[str] = set()
        else:
            # Get rate limit from config, or auto-set based on plan
            api_plan = live_score_config.get("api_plan", "trial")
            rate_limit = live_score_config.get("rate_limit_per_day")
            
            # If not specified in config, auto-set based on plan
            if rate_limit is None:
                if api_plan == "paid":
                    rate_limit = 14500
                else:
                    rate_limit = 1500
                logger.info(f"Rate limit not specified in config, auto-set to {rate_limit} based on plan: {api_plan}")
            else:
                logger.info(f"Using rate limit from config: {rate_limit}/day")
            
            # Use factory to create Live Score client (real or mock)
            live_score_client = service_factory.create_live_score_client(
                api_key=live_score_config.get("api_key", ""),
                api_secret=live_score_config.get("api_secret", ""),
                base_url=live_score_config.get("base_url", "https://livescore-api.com/api-client"),
                rate_limit_per_day=rate_limit
            )
            match_matcher = MatchMatcher()
            match_tracker_manager = MatchTrackerManager()
            
            # Load 0-0 exception competitions from Excel
            project_root = Path(__file__).parent.parent
            excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
            if excel_path.exists():
                zero_zero_exception_competitions = get_competitions_with_zero_zero_exception(str(excel_path))
                logger.info(f"Loaded {len(zero_zero_exception_competitions)} competition(s) with 0-0 exception")
            else:
                zero_zero_exception_competitions = set()
                logger.warning("Excel file not found, no 0-0 exception competitions loaded")
            
            print(f"✓ Live Score API client initialized (plan: {api_plan}, rate limit: {rate_limit}/day)")
            print(f"✓ Match matcher initialized")
            print(f"✓ Match tracker manager initialized")
            if zero_zero_exception_competitions:
                print(f"✓ Loaded {len(zero_zero_exception_competitions)} competition(s) with 0-0 exception")
        
        # Get account funds (test API connection)
        print("\n[Test] Retrieving account funds...")
        account_funds = market_service.get_account_funds()
        initial_bankroll = 0.0
        if account_funds:
            available_balance = account_funds.get("availableToBetBalance", "N/A")
            try:
                initial_bankroll = float(available_balance) if isinstance(available_balance, (int, float, str)) else 0.0
            except (ValueError, TypeError):
                initial_bankroll = 0.0
            logger.info(f"Account balance: {available_balance}")
            print(f"✓ Account balance retrieved: {available_balance}")
        else:
            print("⚠ Could not retrieve account balance (non-critical)")
        
        # Initialize Bet Tracking (Phase 5)
        bet_tracker = None
        excel_writer = None
        skipped_matches_writer = None
        bet_tracking_config = config.get("bet_tracking", {})
        if bet_tracking_config.get("track_outcomes", True):
            excel_path = bet_tracking_config.get("excel_path", "competitions/Competitions_Results_Odds_Stake.xlsx")
            project_root = Path(__file__).parent.parent
            excel_path_full = project_root / excel_path
            
            bet_tracker = BetTracker(initial_bankroll=initial_bankroll)
            excel_writer = ExcelWriter(str(excel_path_full))
            logger.info("Bet tracking initialized")
            print("✓ Bet tracking initialized")
        
        # Initialize Skipped Matches Writer
        project_root = Path(__file__).parent.parent
        skipped_matches_path = project_root / "competitions" / "Skipped Matches.xlsx"
        skipped_matches_writer = SkippedMatchesWriter(str(skipped_matches_path))
        logger.info("Skipped matches writer initialized")
        print("✓ Skipped matches writer initialized")
        
        # Initialize Betting Service (Milestone 3)
        betting_service = None
        bet_execution_config = config.get("bet_execution", {})
        if bet_execution_config:
            betfair_config = config.get("betfair", {})
            # Use factory to create betting service (real or mock)
            betting_service = service_factory.create_betting_service(
                app_key=betfair_config.get("app_key", ""),
                session_token=session_token,
                api_endpoint=betfair_config.get("api_endpoint", "")
            )
            # Note: Token will be updated automatically when session expires and re-login happens
            # via handle_session_expired callback (line 219-235)
            if service_factory.is_test_mode:
                logger.info("Betting service initialized (TEST MODE)")
                print("✓ Betting service initialized (TEST MODE)")
            else:
                logger.info("Betting service initialized")
                print("✓ Betting service initialized (Milestone 3)")
        
        # Initialize Sound Notifier (Milestone 4)
        sound_notifier = None
        notifications_config = config.get("notifications", {})
        if notifications_config.get("sound_enabled", False):
            try:
                sound_notifier = SoundNotifier(notifications_config)
                logger.info("Sound notifier initialized")
                print("✓ Sound notifications enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize sound notifier: {str(e)}")
                print("⚠ Sound notifications disabled (initialization failed)")
        
        # Initialize Telegram Notifier (Milestone 4)
        telegram_notifier = None
        if notifications_config.get("telegram_enabled", False):
            try:
                telegram_notifier = TelegramNotifier(notifications_config)
                logger.info("Telegram notifier initialized")
                print("✓ Telegram notifications enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram notifier: {str(e)}")
                print("⚠ Telegram notifications disabled (initialization failed)")
        
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
        
        # Live Score API polling interval (separate from Betfair polling)
        # Use live_score_config that was already loaded above (line 401)
        live_api_polling_interval = live_score_config.get("polling_interval_seconds", 60) if live_score_config else 60
        last_live_api_call_time = None  # None means never called before
        cached_live_matches = []  # Cache live matches between API calls
        
        logger.info(f"Live Score API polling interval: {live_api_polling_interval}s")
        
        while True:
            # Check if stop was requested from web interface
            try:
                from web.shared_state import should_stop
                if should_stop():
                    logger.info("Stop requested from web interface")
                    print("\n\nStop requested from web interface. Shutting down...")
                    break
            except ImportError:
                # If web interface not used, ignore
                pass
            
            iteration += 1
            logger.debug(f"--- Detection iteration #{iteration} ---")
            
            try:
                # Get market catalogue
                markets = market_service.list_market_catalogue(
                    event_type_ids=event_type_ids,
                    competition_ids=competition_ids if competition_ids else None,
                    in_play_only=in_play_only
                )
                
                # Filter to only keep match-specific markets (exclude Winner/Champion)
                if markets:
                    markets = filter_match_specific_markets(markets)
                    logger.debug(f"After filtering: {len(markets)} match-specific market(s)")
                
                if markets:
                    logger.debug(f"Found {len(markets)} in-play match-specific market(s)")
                    print(f"\n[{iteration}] Found {len(markets)} in-play match-specific market(s):")
                    
                    # Get unique events from markets
                    unique_events: Dict[str, Dict[str, Any]] = {}
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
                    
                    logger.debug(f"Found {len(unique_events)} unique event(s)")
                    
                    # Log details of first few markets
                    for i, market in enumerate(markets[:5], 1):  # Show first 5
                        market_id = market.get("marketId", "N/A")
                        market_name = market.get("marketName", "N/A")
                        event_name = market.get("event", {}).get("name", "N/A")
                        competition_name = market.get("competition", {}).get("name", "N/A")
                        
                        logger.debug(f"  Market {i}: {event_name} - {market_name}")
                        print(f"  [{i}] {event_name} - {market_name}")
                    
                    if len(markets) > 5:
                        print(f"  ... and {len(markets) - 5} more markets")
                    
                    # Milestone 2: Match with Live API and start tracking
                    if live_score_client and match_matcher and match_tracker_manager:
                        # Get live matches from Live Score API (only every N seconds to respect rate limit)
                        current_time = time.time()
                        
                        # Check if we need to call API (first call or enough time has passed)
                        should_call_api = False
                        if last_live_api_call_time is None:
                            # First call - always call API
                            should_call_api = True
                            logger.info(f"Calling Live Score API (first call, interval: {live_api_polling_interval}s)")
                        else:
                            time_since_last_call = current_time - last_live_api_call_time
                            if time_since_last_call >= live_api_polling_interval:
                                should_call_api = True
                                logger.info(f"Calling Live Score API (last call was {time_since_last_call:.1f}s ago, interval: {live_api_polling_interval}s)")
                            else:
                                # Use cached matches
                                remaining_time = live_api_polling_interval - time_since_last_call
                                logger.info(f"Using cached Live API data (last call: {time_since_last_call:.1f}s ago, next call in {remaining_time:.1f}s)")
                        
                        if should_call_api:
                            # Time to call Live API
                            try:
                                live_matches = live_score_client.get_live_matches()
                                last_live_api_call_time = current_time
                                # Only cache if we got valid data (list)
                                if isinstance(live_matches, list):
                                    cached_live_matches = live_matches
                                    logger.info(f"Live Score API called successfully (next call in {live_api_polling_interval}s)")
                                else:
                                    logger.warning(f"Live Score API returned invalid data type, using cached data")
                                    live_matches = cached_live_matches if cached_live_matches else []
                            except Exception as api_error:
                                # If API call fails, use cached data if available
                                logger.warning(f"Live Score API call failed, using cached data: {str(api_error)[:100]}")
                                live_matches = cached_live_matches if cached_live_matches else []
                                # Don't update last_live_api_call_time so we retry sooner
                        else:
                            # Use cached matches
                            live_matches = cached_live_matches
                        if live_matches:
                            logger.info(f"Live API: {len(live_matches)} live match(es) available")
                            # Log first few matches for visibility
                            from football_api.parser import parse_match_teams, parse_match_competition, parse_match_minute, parse_match_score
                            for i, lm in enumerate(live_matches[:3], 1):  # Log first 3
                                home, away = parse_match_teams(lm)
                                comp = parse_match_competition(lm)
                                minute = parse_match_minute(lm)
                                score = parse_match_score(lm)
                                status = lm.get("status", "N/A")
                                logger.info(f"  [{i}] {home} v {away} ({comp}) - {score} @ {minute}' [{status}]")
                            if len(live_matches) > 3:
                                logger.info(f"  ... and {len(live_matches) - 3} more live match(es)")
                        else:
                            # Log at info level but less verbose
                            logger.info("Live API: No live matches available")
                        
                        # Match Betfair events with Live API matches
                        matched_count = 0
                        total_events = len(unique_events)
                        for event_id, event_data in unique_events.items():
                            betfair_event = event_data["event"]
                            competition_name = event_data["competition"].get("name", "")
                            betfair_event_name = betfair_event.get("name", "N/A")
                            
                            logger.debug(f"Matching: {betfair_event_name}")
                            
                            # Check if already tracking
                            tracker = match_tracker_manager.get_tracker(event_id)
                            if tracker:
                                # Update existing tracker
                                live_match = None
                                for lm in live_matches:
                                    if str(lm.get("id", "")) == tracker.live_match_id:
                                        live_match = lm
                                        break
                                
                                if live_match:
                                    # Update match data from live match
                                    score = parse_match_score(live_match)
                                    minute = parse_match_minute(live_match)
                                    
                                    # Get goals from events endpoint if needed (to optimize rate limit)
                                    # Only fetch events when match is in monitoring window or qualified
                                    goals = []
                                    if tracker.state in [MatchState.MONITORING_60_74, MatchState.QUALIFIED, MatchState.READY_FOR_BET]:
                                        # Fetch events to get goals timeline
                                        if live_score_client:
                                            events_data = live_score_client.get_match_details(tracker.live_match_id)
                                            if events_data:
                                                goals = parse_goals_timeline(events_data)
                                            else:
                                                # Fallback: try to parse from live_match (may not have goals)
                                                goals = parse_goals_timeline(live_match)
                                    else:
                                        # For other states, try to parse from live_match (may be empty)
                                        goals = parse_goals_timeline(live_match)
                                    
                                    old_state = tracker.state
                                    tracker.update_match_data(score, minute, goals)
                                    
                                    # Get Excel path for early discard check
                                    project_root = Path(__file__).parent.parent
                                    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                                    
                                    tracker.update_state(excel_path=str(excel_path) if excel_path.exists() else None)
                                    
                                    # Log status changes
                                    if tracker.state == MatchState.QUALIFIED and old_state != MatchState.QUALIFIED:
                                        logger.info(f"Match QUALIFIED: {tracker.betfair_event_name} - {tracker.qualification_reason}")
                                        print(f"  ✓ QUALIFIED: {tracker.betfair_event_name} - {tracker.qualification_reason}")
                                    elif tracker.state == MatchState.READY_FOR_BET and old_state != MatchState.READY_FOR_BET:
                                        logger.info(f"Match READY FOR BET: {tracker.betfair_event_name}")
                                        print(f"  🎯 READY FOR BET: {tracker.betfair_event_name}")
                                    
                                    # Milestone 3: Execute lay bet if conditions are met
                                    # Check both when state changes to READY_FOR_BET and on subsequent updates
                                    # Only attempt if bet not placed and not already skipped
                                    if (tracker.state == MatchState.READY_FOR_BET and 
                                        betting_service and 
                                        tracker.current_minute >= 75 and 
                                        not tracker.bet_placed and
                                        not getattr(tracker, 'bet_skipped', False)):
                                        match_tracking_config = config.get("match_tracking", {})
                                        target_over = match_tracking_config.get("target_over", 2.5)
                                        
                                        logger.info(f"Attempting to place lay bet for {tracker.betfair_event_name} (minute {tracker.current_minute}, score: {tracker.current_score})")
                                        
                                        # Get Excel path
                                        project_root = Path(__file__).parent.parent
                                        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                                        
                                        bet_result = execute_lay_bet(
                                            market_service=market_service,
                                            betting_service=betting_service,
                                            event_id=tracker.betfair_event_id,
                                            event_name=tracker.betfair_event_name,
                                            target_over=target_over,
                                            bet_config=bet_execution_config,
                                            competition_name=tracker.competition_name,
                                            current_score=tracker.current_score,
                                            excel_path=str(excel_path)
                                        )
                                        
                                        if bet_result and bet_result.get("success"):
                                            # Mark bet as placed
                                            tracker.bet_placed = True
                                            tracker.bet_id = bet_result.get("betId", "")
                                            
                                            # Record bet in BetTracker
                                            if bet_tracker:
                                                bet_record = bet_tracker.record_bet(
                                                    bet_id=bet_result.get("betId", ""),
                                                    match_id=tracker.betfair_event_id,
                                                    competition=tracker.competition_name,
                                                    market_name=bet_result.get("marketName", ""),
                                                    selection=bet_result.get("runnerName", ""),
                                                    odds=bet_result.get("layPrice", 0.0),
                                                    stake=bet_result.get("stake", 0.0)
                                                )
                                                
                                                # Write to Excel if enabled
                                                if excel_writer:
                                                    excel_writer.write_bet_record(bet_record)
                                            
                                            # Console output
                                            print(f"  ✅ BET PLACED: {tracker.betfair_event_name}")
                                            print(f"     Market: {bet_result.get('marketName', 'N/A')}")
                                            print(f"     Lay @ {bet_result.get('layPrice', 0.0)}, Stake: {bet_result.get('stake', 0.0)} EUR, Liability: {bet_result.get('liability', 0.0)} EUR")
                                            print(f"     BetId: {bet_result.get('betId', 'N/A')}")
                                            
                                            logger.info(f"Bet placed successfully: BetId={bet_result.get('betId')}, Stake={bet_result.get('stake')}, Liability={bet_result.get('liability')}")
                                            
                                            # Play sound notification for bet placed
                                            if sound_notifier:
                                                sound_notifier.play_bet_placed_sound()
                                            
                                            # Check if bet is matched and play matched sound
                                            size_matched = bet_result.get("sizeMatched", 0.0)
                                            if size_matched and size_matched > 0:
                                                if sound_notifier:
                                                    sound_notifier.play_bet_matched_sound()
                                                
                                                # Send Telegram notification for bet matched
                                                if telegram_notifier:
                                                    try:
                                                        telegram_notifier.send_bet_matched_notification(bet_result)
                                                    except Exception as e:
                                                        logger.error(f"Failed to send Telegram bet matched notification: {str(e)}")
                                                
                                                logger.info(f"Bet matched immediately: BetId={bet_result.get('betId')}, SizeMatched={size_matched}")
                                        else:
                                            # Mark as skipped to prevent retry
                                            tracker.bet_skipped = True
                                            
                                            # Record skipped match (only once)
                                            logger.warning(f"Failed to place bet for {tracker.betfair_event_name}")
                                            print(f"  ⚠ Could not place bet for {tracker.betfair_event_name}")
                                            
                                            if skipped_matches_writer:
                                                # Prepare skipped match data
                                                skipped_data = {
                                                    "match_name": tracker.betfair_event_name,
                                                    "competition": tracker.competition_name,
                                                    "minute": tracker.current_minute if tracker.current_minute >= 0 else "N/A",
                                                    "status": tracker.state.value if hasattr(tracker.state, 'value') else str(tracker.state),
                                                    "timestamp": datetime.now()
                                                }
                                                
                                                # If bet_result is a dict with skip information, use it
                                                if bet_result and isinstance(bet_result, dict):
                                                    skipped_data["reason"] = bet_result.get("reason", bet_result.get("skip_reason", "Unknown reason"))
                                                    skipped_data["best_back"] = bet_result.get("bestBackPrice")
                                                    skipped_data["best_lay"] = bet_result.get("bestLayPrice")
                                                    skipped_data["spread_ticks"] = bet_result.get("spread_ticks")
                                                    skipped_data["current_odds"] = bet_result.get("bestLayPrice") or bet_result.get("calculatedLayPrice")
                                                else:
                                                    # bet_result is None or invalid
                                                    skipped_data["reason"] = "Bet execution failed (no details available)"
                                                    skipped_data["best_back"] = None
                                                    skipped_data["best_lay"] = None
                                                    skipped_data["spread_ticks"] = None
                                                    skipped_data["current_odds"] = None
                                                
                                                try:
                                                    skipped_matches_writer.write_skipped_match(skipped_data)
                                                    logger.info(f"Skipped match recorded: {tracker.betfair_event_name} - {skipped_data['reason']}")
                                                except Exception as e:
                                                    logger.error(f"Error writing skipped match: {str(e)}")
                            else:
                                # Try to match with Live API
                                live_match = match_matcher.match_betfair_to_live_api(
                                    betfair_event, live_matches, competition_name
                                )
                                
                                if live_match:
                                    matched_count += 1
                                    live_match_id = str(live_match.get("id", ""))
                                    # Get match details for logging
                                    from football_api.parser import parse_match_teams, parse_match_competition, parse_match_minute, parse_match_score
                                    live_home, live_away = parse_match_teams(live_match)
                                    live_comp = parse_match_competition(live_match)
                                    logger.info(f"Matched: {betfair_event_name} <-> {live_home} v {live_away} ({live_comp})")
                                    
                                    # Get match tracking config
                                    match_tracking_config = config.get("match_tracking", {})
                                    goal_window = match_tracking_config.get("goal_detection_window", {})
                                    start_minute = goal_window.get("start_minute", 60)
                                    end_minute = goal_window.get("end_minute", 74)
                                    var_check_enabled = match_tracking_config.get("var_check_enabled", True)
                                    target_over = match_tracking_config.get("target_over", None)
                                    early_discard_enabled = match_tracking_config.get("early_discard_enabled", True)
                                    
                                    # Get competition name from Live API (for Excel matching)
                                    live_competition_name = parse_match_competition(live_match)
                                    # Use Live API competition name if available, otherwise fallback to Betfair
                                    tracker_competition_name = live_competition_name if live_competition_name else competition_name
                                    
                                    # Create tracker
                                    tracker = MatchTracker(
                                        betfair_event_id=event_id,
                                        betfair_event_name=betfair_event.get("name", "N/A"),
                                        live_match_id=live_match_id,
                                        competition_name=tracker_competition_name,
                                        start_minute=start_minute,
                                        end_minute=end_minute,
                                        zero_zero_exception_competitions=zero_zero_exception_competitions,
                                        var_check_enabled=var_check_enabled,
                                        target_over=target_over,
                                        early_discard_enabled=early_discard_enabled
                                    )
                                    
                                    # Update with initial data
                                    score = parse_match_score(live_match)
                                    minute = parse_match_minute(live_match)
                                    
                                    # Get goals from events endpoint if match is in monitoring window
                                    goals = []
                                    if minute >= start_minute or minute >= 60:
                                        # Fetch events to get goals timeline
                                        if live_score_client:
                                            events_data = live_score_client.get_match_details(live_match_id)
                                            if events_data:
                                                goals = parse_goals_timeline(events_data)
                                            else:
                                                # Fallback: try to parse from live_match
                                                goals = parse_goals_timeline(live_match)
                                    else:
                                        # For early minutes, try to parse from live_match (may be empty)
                                        goals = parse_goals_timeline(live_match)
                                    
                                    tracker.update_match_data(score, minute, goals)
                                    # Get Excel path for early discard check
                                    project_root = Path(__file__).parent.parent
                                    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                                    
                                    tracker.update_state(excel_path=str(excel_path) if excel_path.exists() else None)
                                    
                                    # Add to manager
                                    match_tracker_manager.add_tracker(tracker)
                                    
                                    logger.info(f"Tracking: {tracker.betfair_event_name} (min {minute}, score {score})")
                                    print(f"  📊 Tracking: {tracker.betfair_event_name} (min {minute}, score {score})")
                                else:
                                    # Only log mismatch if there are live matches available (to reduce noise)
                                    if live_matches:
                                        logger.debug(f"No match found for: {betfair_event_name}")
                        
                        # Log matching summary
                        if total_events > 0:
                            if matched_count > 0:
                                # Show boxed message when matches are found
                                message = f"Matching: {matched_count}/{total_events} event(s) matched and started tracking"
                                boxed_message = format_boxed_message(message)
                                logger.info(message)
                                print(boxed_message)
                            elif live_matches:
                                # No box for 0 matches, just regular log
                                logger.info(f"Matching: 0/{total_events} event(s) matched (checking {len(live_matches)} live match(es))")
                            else:
                                # No box for no live matches, just regular log
                                logger.info(f"Matching: {total_events} Betfair event(s) found, but no live matches available")
                        
                        # Process finished matches (Phase 5: Bet Tracking)
                        if bet_tracker and excel_writer:
                            match_tracking_config = config.get("match_tracking", {})
                            target_over = match_tracking_config.get("target_over", None)
                            process_finished_matches(
                                match_tracker_manager=match_tracker_manager,
                                bet_tracker=bet_tracker,
                                excel_writer=excel_writer,
                                target_over=target_over,
                                telegram_notifier=telegram_notifier
                            )
                        
                        # Cleanup finished matches
                        match_tracker_manager.cleanup_finished()
                        
                        # Log tracking summary (only if there are trackers)
                        all_trackers = match_tracker_manager.get_all_trackers()
                        if all_trackers:
                            ready_for_bet = match_tracker_manager.get_ready_for_bet()
                            logger.info(f"Tracking: {len(all_trackers)} match(es), {len(ready_for_bet)} ready for bet")
                            if ready_for_bet:
                                print(f"  🎯 {len(ready_for_bet)} match(es) ready for bet placement")
                else:
                    logger.info("No in-play match-specific markets found")
                    print(f"[{iteration}] No in-play match-specific markets found")
                
                # Reset error counter on success
                consecutive_errors = 0
                
                # Wait before next iteration (check stop event during sleep)
                try:
                    # Sleep in small chunks to check stop event more frequently
                    sleep_chunks = max(1, int(polling_interval / 2))  # Check every 0.5s or 1s
                    for _ in range(sleep_chunks):
                        time.sleep(polling_interval / sleep_chunks)
                        # Check stop event during sleep
                        try:
                            from web.shared_state import should_stop
                            if should_stop():
                                logger.info("Stop requested from web interface during sleep")
                                print("\n\nStop requested from web interface. Shutting down...")
                                raise KeyboardInterrupt  # Break out of sleep and loop
                        except ImportError:
                            pass
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
                        # Use password login or certificate login based on config
                        if use_password_login:
                            success, error = authenticator.login_with_password()
                        else:
                            success, error = authenticator.login()
                        if success:
                            new_token = authenticator.get_session_token()
                            market_service.update_session_token(new_token)
                            keep_alive_manager.update_session_token(new_token)
                            # Update betting service if it exists (Milestone 3)
                            if betting_service:
                                betting_service.update_session_token(new_token)
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
                    
                    # Re-login (Note: We do NOT send email notifications here to avoid spam.
                    # Email notifications are only sent during initial login loop, first attempt only.)
                    try:
                        # Use password login or certificate login based on config
                        if use_password_login:
                            success, error = authenticator.login_with_password()
                        else:
                            success, error = authenticator.login()
                        if success:
                            new_token = authenticator.get_session_token()
                            market_service.update_session_token(new_token)
                            keep_alive_manager.update_session_token(new_token)
                            # Update betting service if it exists (Milestone 3)
                            if betting_service:
                                betting_service.update_session_token(new_token)
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
        logger.info("Milestone 2 completed successfully")
        print("✓ Done")
        
        return 0
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\n\n⚠ Bot stopped by user (Ctrl+C)")
        if 'logger' in locals():
            logger.info("Bot stopped by user (KeyboardInterrupt)")
        if 'keep_alive_manager' in locals():
            try:
                keep_alive_manager.stop()
            except:
                pass
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

