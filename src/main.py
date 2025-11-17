"""
Betfair Italy Bot - Main Entry Point
Milestone 2: Authentication, Market Detection & Live Data Integration
"""
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.loader import load_config, validate_config
from betfair.market_filter import filter_match_specific_markets
from core.logging_setup import setup_logging
from auth.cert_login import BetfairAuthenticator
from auth.keep_alive import KeepAliveManager
from football_api.parser import (parse_match_score, parse_match_minute, parse_goals_timeline,
                                 parse_match_teams, parse_match_competition)
from logic.match_tracker import MatchTrackerManager, MatchTracker, MatchState
from logic.bet_executor import execute_lay_bet
from notifications.email_notifier import EmailNotifier
from utils import (format_tracking_table, format_boxed_message, 
                   process_finished_matches, perform_login_with_retry, initialize_all_services)
import logging
from datetime import datetime

logger = logging.getLogger("BetfairBot")


def main():
    """Main function for Milestone 2"""
    # Track last live count to avoid duplicate logging (only for Live API, not Betfair)
    if not hasattr(main, '_last_live_count'):
        main._last_live_count = 0
    
    try:
        # Load configuration
        config = load_config()
        validate_config(config)
        
        # Setup logging
        logger = setup_logging(config["logging"])
        
        # Setup Checklist
        checklist_items = []
        
        # 1. Email Notifications
        email_notifier = None
        notifications_config = config.get("notifications", {})
        if notifications_config.get("email_enabled", False):
            try:
                email_notifier = EmailNotifier(notifications_config)
                email_config = notifications_config.get("email", {})
                sender = email_config.get("sender_email", "N/A")
                recipient = email_config.get("recipient_email", "N/A")
                checklist_items.append(f"  ✓ Email notifications: {sender} → {recipient}")
            except Exception as e:
                logger.warning(f"Failed to initialize email notifier: {str(e)}")
                checklist_items.append(f"  ✗ Email notifications: Disabled (initialization failed)")
        else:
            checklist_items.append(f"  ✗ Email notifications: Disabled")
        
        # Initialize authenticator
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
        
        # Perform login with retry logic
        session_token, email_flags = perform_login_with_retry(config, authenticator, email_notifier)
        
        if not session_token:
            logger.error("Failed to obtain session token")
            login_method_str = "Password" if use_password_login else "Certificate"
            checklist_items.append(f"  ✗ Login ({login_method_str}): Failed")
            # Print checklist before exiting
            max_width = max(len(item) for item in checklist_items) if checklist_items else 60
            box_width = max_width + 4
            logger.info("")
            logger.info("┌" + "─" * (box_width - 2) + "┐")
            logger.info("│" + " " * ((box_width - 16) // 2) + "Setup Checklist" + " " * ((box_width - 16 + 1) // 2) + "│")
            logger.info("├" + "─" * (box_width - 2) + "┤")
            for item in checklist_items:
                padded_item = item + " " * (box_width - len(item) - 3)
                logger.info(f"│{padded_item}│")
            logger.info("└" + "─" * (box_width - 2) + "┘")
            logger.info("")
            print("✗ Failed to login after multiple attempts")
            return 1
        
        # Initialize Service Factory (for test mode support)
        from core.service_factory import ServiceFactory
        service_factory = ServiceFactory(config)
        
        # Initialize all services and build checklist
        services, service_checklist = initialize_all_services(
            config, session_token, service_factory, authenticator, use_password_login
        )
        checklist_items.extend(service_checklist)
        
        # Extract services from dict
        market_service = services['market_service']
        keep_alive_manager = services['keep_alive_manager']
        live_score_client = services.get('live_score_client')
        match_matcher = services.get('match_matcher')
        match_tracker_manager = services.get('match_tracker_manager')
        zero_zero_exception_competitions = services.get('zero_zero_exception_competitions', set())
        bet_tracker = services.get('bet_tracker')
        excel_writer = services.get('excel_writer')
        skipped_matches_writer = services['skipped_matches_writer']
        betting_service = services.get('betting_service')
        sound_notifier = services.get('sound_notifier')
        telegram_notifier = services.get('telegram_notifier')
        event_type_ids = services['event_type_ids']
        competition_ids = services['competition_ids']
        
        # Get monitoring config
        monitoring_config = config["monitoring"]
        in_play_only = monitoring_config.get("in_play_only", True)
        polling_interval = monitoring_config.get("polling_interval_seconds", 10)
        live_score_config = config.get("live_score_api", {})
        
        # Print setup checklist in a box
        max_width = max(len(item) for item in checklist_items) if checklist_items else 60
        box_width = max_width + 4
        
        logger.info("")
        logger.info("┌" + "─" * (box_width - 2) + "┐")
        logger.info("│" + " " * ((box_width - 16) // 2) + "Setup Checklist" + " " * ((box_width - 16 + 1) // 2) + "│")
        logger.info("├" + "─" * (box_width - 2) + "┤")
        for item in checklist_items:
            if item == "":
                # Empty line
                logger.info("│" + " " * (box_width - 2) + "│")
            else:
                # Pad item to box width
                padded_item = item + " " * (box_width - len(item) - 3)
                logger.info(f"│{padded_item}│")
        logger.info("└" + "─" * (box_width - 2) + "┘")
        logger.info("")
        
        # Setup completed
        logger.info("Setup completed, starting bot...")
        logger.info("Monitoring phase started – tracking live matches...")
        
        iteration = 0
        retry_delay = 5
        consecutive_errors = 0
        max_consecutive_errors = 10  # Log warning after 10 consecutive errors
        
        # Live Score API polling interval (separate from Betfair polling)
        # Use live_score_config that was already loaded above (line 401)
        live_api_polling_interval = live_score_config.get("polling_interval_seconds", 60) if live_score_config else 60
        last_live_api_call_time = None  # None means never called before
        cached_live_matches = []  # Cache live matches between API calls
        
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
                    
                    # MỤC 6.1: Log Betfair events clearly - show ALL matches EVERY iteration
                    # Only use logger.info() - it already outputs to console via console_handler
                    logger.info(f"\n[{iteration}] Betfair: {len(unique_events)} live match(es) available")
                    
                    # MỤC 6.1: Show ALL events (not just first 5) - log every iteration
                    event_list = list(unique_events.values())
                    for i, event_data in enumerate(event_list, 1):
                        event = event_data["event"]
                        event_name = event.get("name", "N/A")
                        competition_name = event_data["competition"].get("name", "N/A")
                        market_count = len(event_data["markets"])
                        
                        logger.info(f"  [{i}] {event_name} ({competition_name}) - {market_count} market(s)")
                    
                    # Milestone 2: Match with Live API and start tracking
                    if live_score_client and match_matcher and match_tracker_manager:
                        # Get live matches from Live Score API (only every N seconds to respect rate limit)
                        current_time = time.time()
                        
                        # Check if we need to call API (first call or enough time has passed)
                        should_call_api = False
                        if last_live_api_call_time is None:
                            # First call - always call API
                            should_call_api = True
                        else:
                            time_since_last_call = current_time - last_live_api_call_time
                            if time_since_last_call >= live_api_polling_interval:
                                should_call_api = True
                            else:
                                # Use cached matches (don't log to reduce noise)
                                pass
                        
                        if should_call_api:
                            # Time to call Live API
                            try:
                                live_matches = live_score_client.get_live_matches()
                                last_live_api_call_time = current_time
                                # Only cache if we got valid data (list)
                                if isinstance(live_matches, list):
                                    cached_live_matches = live_matches
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
                        
                        # Log Live API results (only when calling API, not when using cache)
                        if should_call_api:
                            if live_matches:
                                # Only use logger.info() - it already outputs to console via console_handler
                                logger.info(f"Live API: {len(live_matches)} live match(es) available")
                                # Log ALL matches (not just first 5) - MỤC 6.1
                                # Filter out FINISHED matches before logging (double check, should already be filtered in get_live_matches)
                                actual_live = [lm for lm in live_matches if "FINISHED" not in str(lm.get("status", "")).upper()]
                                for i, lm in enumerate(actual_live, 1):  # Log ALL matches
                                    home, away = parse_match_teams(lm)
                                    comp = parse_match_competition(lm)
                                    minute = parse_match_minute(lm)
                                    score = parse_match_score(lm)
                                    status = lm.get("status", "N/A")
                                    logger.info(f"  [{i}] {home} v {away} ({comp}) - {score} @ {minute}' [{status}]")
                                
                                main._last_live_count = len(live_matches)
                            else:
                                # Log when no matches available (only when calling API)
                                logger.info(f"Live API: No live matches available")
                        
                        # Match Betfair events with Live API matches
                        matched_count = 0
                        total_events = len(unique_events)
                        new_tracked_matches = []  # Collect newly matched matches for batch logging
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
                                        
                                        # Get bet execution config
                                        bet_execution_config = config.get("bet_execution", {})
                                        
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
                                    live_home, live_away = parse_match_teams(live_match)
                                    live_comp = parse_match_competition(live_match)
                                    
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
                                    
                                    # Parse initial match data to check if we should start tracking
                                    score = parse_match_score(live_match)
                                    minute = parse_match_minute(live_match)
                                    
                                    # Check if match is too late to start tracking (must be <= 74 minutes)
                                    if minute > 74:
                                        # Get target scores from Excel for logging
                                        project_root = Path(__file__).parent.parent
                                        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                                        target_scores = []
                                        if excel_path.exists():
                                            from logic.qualification import get_competition_targets
                                            targets = get_competition_targets(tracker_competition_name, str(excel_path))
                                            if targets:
                                                target_scores = sorted(list(targets))
                                        
                                        targets_str = ", ".join(target_scores) if target_scores else "N/A"
                                        match_status = live_match.get("status", "N/A")
                                        reason = f"minute {minute} > 74"
                                        skip_message = f"⏭️  Skipping: {reason} - {tracker_competition_name} - {betfair_event_name} ({score}) [{targets_str}] {match_status}"
                                        logger.info(f"Skipping tracking for {betfair_event_name}: {reason} - Competition: {tracker_competition_name}, Score: {score}, Targets: [{targets_str}], Status: {match_status}")
                                        print(f"  {skip_message}")
                                        continue
                                    
                                    # Create tracker (only if minute <= 74)
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
                                    
                                    # Collect match info for batch logging
                                    new_tracked_matches.append({
                                        "name": tracker.betfair_event_name,
                                        "minute": minute,
                                        "score": score,
                                        "competition": tracker_competition_name,
                                        "excel_path": str(excel_path) if excel_path.exists() else None
                                    })
                                else:
                                    # Only log mismatch if there are live matches available (to reduce noise)
                                    if live_matches:
                                        logger.debug(f"No match found for: {betfair_event_name}")
                        
                        # Log tracking list for newly matched matches
                        if new_tracked_matches:
                            logger.info("📊 Tracking List")
                            logger.info("")
                            
                            # Get Excel path
                            project_root = Path(__file__).parent.parent
                            excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                            
                            for idx, match_info in enumerate(new_tracked_matches, 1):
                                # Get target scores from Excel for this competition
                                target_scores = []
                                if match_info["excel_path"]:
                                    from logic.qualification import get_competition_targets
                                    targets = get_competition_targets(match_info["competition"], match_info["excel_path"])
                                    if targets:
                                        target_scores = sorted(list(targets))
                                
                                # Format target scores
                                targets_str = ", ".join(target_scores) if target_scores else "N/A"
                                
                                log_line = f"{idx}. {match_info['name']} (min {match_info['minute']}, score {match_info['score']}) [{targets_str}]"
                                logger.info(log_line)
                            
                            logger.info("")
                        
                        # Log matching summary (only when count changes or first iteration)
                        if not hasattr(main, '_last_matched_summary'):
                            main._last_matched_summary = None
                        
                        current_summary = f"{matched_count}/{total_events}"
                        if total_events > 0 and (iteration == 1 or main._last_matched_summary != current_summary):
                            if matched_count > 0:
                                # Show boxed message when matches are found
                                message = f"Matched: {matched_count}/{total_events} event(s) matched and started tracking"
                                boxed_message = format_boxed_message(message)
                                logger.info(message)
                                print(boxed_message)  # Keep print for boxed message (special formatting)
                            elif live_matches:
                                # No box for 0 matches, just regular log
                                logger.info(f"Matched: 0/{total_events} Betfair event(s) matched (checking {len(live_matches)} Live API match(es))")
                            else:
                                # No box for no live matches, just regular log
                                logger.info(f"Matched: {total_events} Betfair event(s) found, but no Live API matches available")
                            
                            main._last_matched_summary = current_summary
                        
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
                        
                        # Cleanup discarded matches (MỤC 3.7)
                        match_tracker_manager.cleanup_discarded()
                        
                        # MỤC 6: Display tracking table with all matches from 60-74 (MỤC 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8)
                        # MỤC 6.3: Update and display minute + score from 60-74 every iteration
                        all_trackers = match_tracker_manager.get_all_trackers()
                        if all_trackers:
                            # Filter trackers from minute 60-74 for display (exclude discarded matches)
                            from logic.match_tracker import MatchState
                            trackers_60_74 = [t for t in all_trackers 
                                            if 60 <= t.current_minute <= 74 
                                            and t.state != MatchState.DISQUALIFIED]
                            
                            if trackers_60_74:
                                # Get Excel path for target scores
                                project_root = Path(__file__).parent.parent
                                excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                                
                                # MỤC 6.3: Format and display tracking table EVERY iteration (not just when count changes)
                                table = format_tracking_table(
                                    trackers_60_74,
                                    excel_path=str(excel_path) if excel_path.exists() else None
                                )
                                logger.info(f"\n[{iteration}] Tracking {len(trackers_60_74)} match(es) from minute 60-74:\n{table}")
                                
                                # Also show summary
                                ready_for_bet = match_tracker_manager.get_ready_for_bet()
                                if ready_for_bet:
                                    logger.info(f"  🎯 {len(ready_for_bet)} match(es) ready for bet placement")
                            else:
                                # No matches at 60-74 yet, just show count
                                ready_for_bet = match_tracker_manager.get_ready_for_bet()
                                logger.info(f"Tracking: {len(all_trackers)} match(es) (waiting for minute 60-74), {len(ready_for_bet)} ready for bet")
                                if ready_for_bet:
                                    logger.info(f"  🎯 {len(ready_for_bet)} match(es) ready for bet placement")
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
        logger.info("Bot stopped gracefully")
        print("✓ Bot stopped")
        
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

