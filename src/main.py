"""
Betfair Italy Bot - Main Entry Point
Milestone 2: Authentication, Market Detection & Live Data Integration
"""
import sys
import time
import requests
import socket
import ssl
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.loader import load_config, validate_config
from core.logging_setup import setup_logging
from auth.cert_login import BetfairAuthenticator
from auth.keep_alive import KeepAliveManager
from services.live import (parse_match_score, parse_match_minute, parse_goals_timeline,
                                 parse_match_teams, parse_match_competition)
from services.betfair import get_live_markets_from_stream_api
from services.tracking import log_tracking_list
from services.market_detector import MarketDetector
from services.live_score_poller import LiveScorePoller
from services.matching_service import MatchingService
from services.tracker_service import TrackerService
from services.bet_orchestrator import BetOrchestrator
from services.polling_interval_service import PollingIntervalService
from logic.match_tracker import MatchTrackerManager, MatchTracker, MatchState
from logic.bet_executor import execute_lay_bet
from notifications.email_notifier import EmailNotifier
from services.util import (perform_login_with_retry, initialize_all_services)
from config.competition_mapper import get_competition_ids_from_excel
import logging
from datetime import datetime

logger = logging.getLogger("BetfairBot")


def perform_matching(unique_events: Dict[str, Dict[str, Any]], 
                    live_matches: List[Dict[str, Any]],
                    live_score_client, match_matcher, match_tracker_manager,
                    config, zero_zero_exception_competitions,
                    market_service, betting_service, bet_tracker, excel_writer,
                    skipped_matches_writer, sound_notifier, telegram_notifier,
                    iteration: int, is_refresh: bool = False,
                    matching_refresh_interval: int = 3600) -> tuple:
    """
    Perform matching between Betfair events and LiveScore matches
    
        Args:
        unique_events: Dictionary of Betfair events
        live_matches: List of live matches from LiveScore API
        live_score_client: LiveScore API client
        match_matcher: Match matcher instance
        match_tracker_manager: Match tracker manager
        config: Bot configuration
        zero_zero_exception_competitions: Set of competitions with 0-0 exception
        market_service: Market service
        betting_service: Betting service
        bet_tracker: Bet tracker
        excel_writer: Excel writer
        skipped_matches_writer: Skipped matches writer
        sound_notifier: Sound notifier
        telegram_notifier: Telegram notifier
        iteration: Current iteration number
        is_refresh: Whether this is a refresh matching
        matching_refresh_interval: Matching refresh interval in seconds
    
        Returns:
        Tuple of (matched_count, total_events, new_tracked_matches, skipped_matches_list, unmatched_events)
    """
    from logic.bet_executor import execute_lay_bet
    from logic.match_tracker import MatchState
    from config.competition_mapper import get_betfair_to_live_competition_mapping
    
    matched_count = 0
    total_events = len(unique_events)
    new_tracked_matches = []  # Collect newly matched matches for batch logging
    skipped_matches_list = []  # Collect skipped matches for console display
    unmatched_events = []
    
    # Track events that have been logged as "Skipping" to avoid duplicate logs
    # Use a module-level set to persist across function calls
    if not hasattr(perform_matching, '_logged_skipped_events'):
        perform_matching._logged_skipped_events = set()  # Collect unmatched events with rejection reasons
    
    # Load mapping from Excel: Betfair competition ID -> Live API competition ID
    project_root = Path(__file__).parent.parent
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    betfair_to_live_mapping = {}
    if excel_path.exists():
        betfair_to_live_mapping = get_betfair_to_live_competition_mapping(str(excel_path))
    
    # Log refresh message if this is a refresh
    if is_refresh:
        # Get refresh interval from config for logging
        refresh_interval_minutes = (matching_refresh_interval // 60) if matching_refresh_interval >= 60 else (matching_refresh_interval / 60)
        if matching_refresh_interval >= 60:
            interval_str = f"{refresh_interval_minutes} minute{'s' if refresh_interval_minutes > 1 else ''}"
        else:
            interval_str = f"{matching_refresh_interval} second{'s' if matching_refresh_interval > 1 else ''}"
        logger.info(f"\n[{iteration}] 🔄 Refreshing Betfair ↔ LiveScore matching (every {interval_str})...")
    
    for event_id, event_data in unique_events.items():
        betfair_event = event_data["event"]
        competition_obj = event_data.get("competition", {})
        competition_name = competition_obj.get("name", "") if isinstance(competition_obj, dict) else ""
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
                    logger.info(f"✓ QUALIFIED: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score}) - {tracker.qualification_reason}")
                    print(f"  ✓ QUALIFIED: {tracker.betfair_event_name} - {tracker.qualification_reason}")
                elif tracker.state == MatchState.READY_FOR_BET and old_state != MatchState.READY_FOR_BET:
                    logger.info(f"🎯 READY FOR BET: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score})")
                    print(f"  🎯 READY FOR BET: {tracker.betfair_event_name}")
                
                # Milestone 3: Execute lay bet if conditions are met
                # Entry window: full 75th minute (75:00 to 75:59)
                # Check continuously during minute 75, place bet as soon as all conditions are true
                # Never place bet after minute 75 has passed (minute > 75)
                # Only attempt if bet not placed and not already skipped
                if (tracker.state == MatchState.READY_FOR_BET and 
                    betting_service and 
                    75 <= tracker.current_minute < 76 and  # Only during minute 75
                    not tracker.bet_placed and
                    not getattr(tracker, 'bet_skipped', False)):
                    match_tracking_config = config.get("match_tracking", {})
                    target_over = match_tracking_config.get("target_over", 2.5)
                    
                    # Get bet execution config
                    bet_execution_config = config.get("bet_execution", {})
                    
                    logger.info(f"🎲 ATTEMPTING BET: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score}, competition: {tracker.competition_name})")
                    
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
                        
                        # Record bet in BetTracker with all required data
                        if bet_tracker:
                            # Get Excel data for target_score_used and reference_odds
                            from logic.qualification import get_competition_targets, normalize_score
                            target_score_used = tracker.current_score  # Current score is the target score used
                            reference_odds_under_x5 = None
                            liability_percent = None
                            
                            if excel_path:
                                # Get reference odds and stake % from Excel
                                from logic.qualification import load_competition_map_from_excel
                                competition_map = load_competition_map_from_excel(str(excel_path))
                                if tracker.competition_name in competition_map:
                                    comp_data = competition_map[tracker.competition_name]
                                    # Get min_odds and stake for this specific score
                                    normalized_score = normalize_score(tracker.current_score)
                                    # Find the row in Excel that matches this competition and score
                                    import pandas as pd
                                    try:
                                        df = pd.read_excel(excel_path)
                                        # Find row matching competition and score
                                        for idx, row in df.iterrows():
                                            comp_name = None
                                            if 'Competition-Live' in df.columns:
                                                comp_name = str(row.get('Competition-Live', '')).strip()
                                            elif 'Competition' in df.columns:
                                                comp_name = str(row.get('Competition', '')).strip()
                                            
                                            if comp_name == tracker.competition_name:
                                                result = str(row.get('Result', '')).strip()
                                                if normalize_score(result) == normalized_score:
                                                    # Found matching row
                                                    if 'Min_Odds' in df.columns or 'Min Odds' in df.columns:
                                                        min_odds_col = 'Min_Odds' if 'Min_Odds' in df.columns else 'Min Odds'
                                                        ref_odds = row.get(min_odds_col)
                                                        if pd.notna(ref_odds):
                                                            reference_odds_under_x5 = float(ref_odds)
                                                    if 'Stake' in df.columns:
                                                        stake_val = row.get('Stake')
                                                        if pd.notna(stake_val):
                                                            liability_percent = float(stake_val)
                                                    break
                                    except Exception as e:
                                        logger.warning(f"Error reading Excel for bet record: {str(e)}")
                            
                            bet_record = bet_tracker.record_bet(
                                bet_id=bet_result.get("betId", ""),
                                match_id=tracker.betfair_event_id,
                                competition=tracker.competition_name,
                                market_name=bet_result.get("marketName", ""),
                                selection=bet_result.get("runnerName", ""),
                                odds=bet_result.get("layPrice", 0.0),
                                stake=bet_result.get("stake", 0.0),
                                match_name=tracker.betfair_event_name,
                                minute_of_entry=tracker.current_minute,
                                live_score_at_entry=tracker.current_score,
                                target_score_used=target_score_used,
                                best_back_under_x5=bet_result.get("bestBackPrice"),
                                reference_odds_under_x5=reference_odds_under_x5,
                                best_lay_over_x5=bet_result.get("bestLayPrice"),
                                final_lay_price=bet_result.get("layPrice"),
                                spread_ticks=bet_result.get("spread_ticks"),
                                liability_percent=liability_percent,
                                liability_amount=bet_result.get("liability")
                            )
                            
                            # Write to Excel if enabled
                            if excel_writer:
                                excel_writer.write_bet_record(bet_record)
                        
                        # Console output - detailed format per client requirements
                        print(f"\n[BET PLACED]")
                        print(f"Match: {tracker.betfair_event_name}")
                        print(f"Competition: {tracker.competition_name}")
                        print(f"Minute: {tracker.current_minute}'")
                        print(f"Score: {tracker.current_score}")
                        print(f"Market: {bet_result.get('marketName', 'N/A')} (LAY)")
                        lay_price = bet_result.get('layPrice', 0.0)
                        best_lay = bet_result.get('bestLayPrice', 0.0)
                        print(f"Lay price: {lay_price:.2f} (best lay {best_lay:.2f} + 2 ticks)")
                        liability = bet_result.get('liability', 0.0)
                        liability_percent = bet_record.liability_percent if bet_record else None
                        if liability_percent:
                            print(f"Liability: {liability:.2f} ({liability_percent:.1f}% of bankroll)")
                        else:
                            print(f"Liability: {liability:.2f}")
                        print(f"Lay stake: {bet_result.get('stake', 0.0):.2f}")
                        spread_ticks = bet_result.get('spread_ticks', 0)
                        print(f"Spread: {spread_ticks} ticks")
                        best_back_under = bet_result.get('bestBackPrice', 0.0)
                        reference_odds = bet_record.reference_odds_under_x5 if bet_record else None
                        if reference_odds:
                            print(f"Condition: Under back {best_back_under:.2f} >= reference {reference_odds:.2f} → OK")
                        else:
                            print(f"Condition: Under back {best_back_under:.2f} (reference N/A)")
                        print(f"BetId: {bet_result.get('betId', 'N/A')}\n")
                        
                        logger.info(f"✅ BET PLACED SUCCESSFULLY: {tracker.betfair_event_name} - BetId={bet_result.get('betId')}, Stake={bet_result.get('stake')}, Liability={bet_result.get('liability')}, LayPrice={bet_result.get('layPrice')}")
                        
                        # Play sound notification for bet placed
                        if sound_notifier:
                            sound_notifier.play_bet_placed_sound()
                        
                        # Send Telegram notification for bet placed
                        if telegram_notifier:
                            try:
                                bankroll_before = bet_record.bankroll_before if bet_record else 0.0
                                # Add additional info to bet_result for notification
                                bet_result_with_info = bet_result.copy()
                                bet_result_with_info["eventName"] = tracker.betfair_event_name
                                bet_result_with_info["referenceOdds"] = bet_record.reference_odds_under_x5 if bet_record else None
                                bet_result_with_info["liabilityPercent"] = bet_record.liability_percent if bet_record else None
                                telegram_notifier.send_bet_placed_notification(
                                    bet_result_with_info,
                                    competition=tracker.competition_name,
                                    minute=tracker.current_minute,
                                    score=tracker.current_score,
                                    bankroll_before=bankroll_before
                                )
                            except Exception as e:
                                logger.error(f"Failed to send Telegram bet placed notification: {str(e)}")
                        
                        # Check if bet is matched and play matched sound + send notification
                        size_matched = bet_result.get("sizeMatched", 0.0)
                        if size_matched and size_matched > 0:
                            if sound_notifier:
                                sound_notifier.play_bet_matched_sound()
                            
                            # Send Telegram notification for bet matched
                            if telegram_notifier:
                                try:
                                    bet_result_with_info = bet_result.copy()
                                    bet_result_with_info["eventName"] = tracker.betfair_event_name
                                    telegram_notifier.send_bet_matched_notification(bet_result_with_info)
                                except Exception as e:
                                    logger.error(f"Failed to send Telegram bet matched notification: {str(e)}")
                            
                            logger.info(f"Bet matched immediately: BetId={bet_result.get('betId')}, SizeMatched={size_matched}")
                    else:
                        # Mark as skipped to prevent retry
                        tracker.bet_skipped = True
                        
                        # Record skipped match (only once)
                        skip_reason = "Unknown reason"
                        if bet_result and isinstance(bet_result, dict):
                            skip_reason = bet_result.get("reason", bet_result.get("skip_reason", "Unknown reason"))
                        
                        logger.warning(f"❌ BET SKIPPED: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score}) - Reason: {skip_reason}")
                        # Collect skipped match for console display
                        
                        skipped_matches_list.append({
                            "match_name": tracker.betfair_event_name,
                            "reason": skip_reason
                        })
                        
                        if skipped_matches_writer:
                            # Get targets list from Excel
                            targets_list = set()
                            if excel_path:
                                from logic.qualification import get_competition_targets
                                # Note: tracker doesn't store competition_id, so we can't use ID matching here
                                # But we can try to get it from the event if available
                                targets_list = get_competition_targets(tracker.competition_name, str(excel_path))
                            
                            # Prepare skipped match data
                            skipped_data = {
                                "match_name": tracker.betfair_event_name,
                                "competition": tracker.competition_name,
                                "minute": tracker.current_minute if tracker.current_minute >= 0 else "N/A",
                                "minute_75_score": tracker.current_score,
                                "targets_list": targets_list,
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
            # Competition should already be in event_data with ID (set when creating unique_events)
            betfair_event_with_comp = betfair_event.copy()
            competition_obj = event_data.get("competition", {})
            
            # Get competition ID - should already be in competition_obj since it was set when creating unique_events
            competition_id = None
            if competition_obj and isinstance(competition_obj, dict):
                competition_id = competition_obj.get("id")
                if competition_id is not None:
                    try:
                        competition_id = int(competition_id)
                    except (ValueError, TypeError):
                        competition_id = None
            
            # If competition_obj doesn't have ID, try to get from markets (fallback)
            if not competition_id and event_data.get("markets"):
                for market in event_data["markets"]:
                    market_comp = market.get("competition", {})
                    if market_comp and isinstance(market_comp, dict):
                        market_comp_id = market_comp.get("id")
                        if market_comp_id is not None:
                            try:
                                competition_id = int(market_comp_id)
                                competition_obj = market_comp
                                break
                            except (ValueError, TypeError):
                                continue
            
            # Set competition in betfair_event_with_comp
            # IMPORTANT: Ensure competition object has "id" field before passing to match_betfair_to_live_api
            if competition_id and competition_obj:
                # Ensure competition object has the ID field
                if isinstance(competition_obj, dict):
                    if "id" not in competition_obj or competition_obj.get("id") != competition_id:
                        # Create a new competition dict with ID
                        betfair_event_with_comp["competition"] = {
                            "id": competition_id,
                            "name": competition_obj.get("name", competition_name)
                        }
                    else:
                        betfair_event_with_comp["competition"] = competition_obj
                else:
                    betfair_event_with_comp["competition"] = {
                        "id": competition_id,
                        "name": competition_name
                    }
            elif event_data.get("markets"):
                # Last resort: try to get from any market
                for market in event_data["markets"]:
                        market_comp = market.get("competition", {})
                        if market_comp and isinstance(market_comp, dict):
                            market_comp_id = market_comp.get("id")
                        if market_comp_id is not None:
                            try:
                                competition_id = int(market_comp_id)
                                # Ensure competition has ID field
                                betfair_event_with_comp["competition"] = {
                                    "id": competition_id,
                                    "name": market_comp.get("name", competition_name)
                                }
                                break
                            except (ValueError, TypeError):
                                continue
            
            # Skip if no competition ID (cannot match without it)
            if not competition_id:
                logger.info(f"⏭️  Skipping: No competition ID - {betfair_event_name}")
                continue
            
            # Double-check: Ensure betfair_event_with_comp has competition with ID
            if "competition" not in betfair_event_with_comp or not betfair_event_with_comp["competition"].get("id"):
                logger.warning(f"⚠️  Competition ID {competition_id} found but not set in betfair_event_with_comp for '{betfair_event_name}' - setting it now")
                betfair_event_with_comp["competition"] = {
                    "id": competition_id,
                    "name": competition_name
                }
            
            live_match = match_matcher.match_betfair_to_live_api(
                betfair_event_with_comp, live_matches, competition_name, betfair_to_live_mapping
            )
            
            if live_match:
                matched_count += 1
                live_match_id = str(live_match.get("id", ""))
                # Get match details for logging
                live_home, live_away = parse_match_teams(live_match)
                live_comp = parse_match_competition(live_match)
                live_event_name = f"{live_home} v {live_away}"  # Format: "Team A v Team B"
                
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
                    # Only log "Skipping" once per event (use event_id as key)
                    if event_id not in perform_matching._logged_skipped_events:
                        # Get target scores from Excel for logging
                        project_root = Path(__file__).parent.parent
                        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                        target_scores = []
                        if excel_path.exists():
                            from logic.qualification import get_competition_targets
                            # Get competition ID from event_data for ID-based matching
                            comp_id = event_data["competition"].get("id", "")
                            comp_id_str = str(comp_id) if comp_id else None
                            targets = get_competition_targets(tracker_competition_name, str(excel_path), competition_id=comp_id_str)
                            if targets:
                                target_scores = sorted(list(targets))
                        
                        targets_str = ", ".join(target_scores) if target_scores else "N/A"
                        match_status = live_match.get("status", "N/A")
                        reason = f"minute {minute} > 74 (not qualified)"
                        logger.info(f"✘ {betfair_event_name}: DISQUALIFIED - {reason}")
                        # Mark this event as logged
                        perform_matching._logged_skipped_events.add(event_id)
                    continue
                
                # Get strict_discard_at_60 and discard_delay_minutes from config
                strict_discard_at_60 = match_tracking_config.get("strict_discard_at_60", False)
                discard_delay_minutes = match_tracking_config.get("discard_delay_minutes", 4)
                
                # Create tracker (only if minute <= 74)
                # Get Live API event name for tracking list display
                live_event_name = f"{live_home} v {live_away}"  # Format: "Team A v Team B"
                
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
                    early_discard_enabled=early_discard_enabled,
                    strict_discard_at_60=strict_discard_at_60,
                    discard_delay_minutes=discard_delay_minutes,
                    live_event_name=live_event_name  # Add Live API event name
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
                
                # Check if tracker was immediately disqualified (early discard)
                # Log is already handled in match_tracker.py, so skip adding to manager
                if tracker.state == MatchState.DISQUALIFIED:
                    continue
                
                # Add to manager (create link and start tracking)
                match_tracker_manager.add_tracker(tracker)
                
                # Collect match info for batch logging
                new_tracked_matches.append({
                    "name": tracker.betfair_event_name,
                    "live_name": tracker.live_event_name,  # Add Live API event name
                    "minute": minute,
                    "score": score,
                    "competition": tracker_competition_name,
                    "excel_path": str(excel_path) if excel_path.exists() else None
                })
            else:
                # Analyze rejection reason
                # IMPORTANT: Use betfair_event_with_comp (has competition with ID) instead of betfair_event
                rejection_reason = "Unknown reason"
                if match_matcher and live_matches:
                    rejection_reason = match_matcher.analyze_rejection_reason(
                        betfair_event_with_comp, live_matches, competition_name, betfair_to_live_mapping
                    )
                elif not live_matches:
                    rejection_reason = "No Live API matches available"
                
                # Log unmatched event
                logger.info(f"⏭️  Skipping: No Live API match - {betfair_event_name} ({competition_name}) - {rejection_reason}")
                
                unmatched_events.append({
                    "event_name": betfair_event_name,
                    "competition": competition_name,
                    "reason": rejection_reason
                })
    
    return matched_count, total_events, new_tracked_matches, skipped_matches_list, unmatched_events


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
        
        # Initialize Service Factory
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
        live_api_competition_ids = services.get('live_api_competition_ids', [])
        bet_tracker = services.get('bet_tracker')
        excel_writer = services.get('excel_writer')
        skipped_matches_writer = services['skipped_matches_writer']
        betting_service = services.get('betting_service')
        sound_notifier = services.get('sound_notifier')
        telegram_notifier = services.get('telegram_notifier')
        event_type_ids = services['event_type_ids']
        competition_ids = services['competition_ids']
        
        # Debug: Log competition_ids type and sample values
        if competition_ids:
            sample_ids = list(competition_ids)[:5]
            logger.debug(f"competition_ids loaded: type={type(competition_ids)}, length={len(competition_ids)}, sample={sample_ids}, sample_types={[type(cid) for cid in sample_ids]}")
        
        # Get monitoring config
        monitoring_config = config["monitoring"]
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
        
        # Polling intervals from config (shared between Betfair and Live API)
        default_polling_interval = live_score_config.get("default_polling_interval_seconds", 60) if live_score_config else 60  # 60s for 0-60 and 60-74 without QUALIFIED
        intensive_polling_interval = live_score_config.get("intensive_polling_interval_seconds", 10) if live_score_config else 10  # 10s for 60-74 with QUALIFIED
        
        # Fast polling config for Betfair API (74-76 with QUALIFIED)
        fast_polling_enabled = monitoring_config.get("fast_polling_enabled", True)
        fast_polling_interval = monitoring_config.get("fast_polling_interval_seconds", 1)  # 1s for Betfair 74-76 with QUALIFIED
        fast_polling_window = monitoring_config.get("fast_polling_window", {"start_minute": 74, "end_minute": 76})
        fast_polling_start = fast_polling_window.get("start_minute", 74)
        fast_polling_end = fast_polling_window.get("end_minute", 76)
        cached_betfair_markets = []  # Cache Betfair markets to avoid losing data when Stream API temporarily fails
        
        # Initialize services
        market_detector = MarketDetector(market_service, betfair_config, competition_ids)
        live_score_poller = LiveScorePoller(live_score_client, live_api_competition_ids)
        polling_interval_service = PollingIntervalService(
            default_interval=default_polling_interval,
            intensive_interval=intensive_polling_interval,
            fast_interval=fast_polling_interval,
            fast_polling_enabled=fast_polling_enabled
        )
        matching_service = MatchingService(
            live_score_client=live_score_client,
            match_matcher=match_matcher,
            match_tracker_manager=match_tracker_manager,
            config=config,
            zero_zero_exception_competitions=zero_zero_exception_competitions
        )
        tracker_service = TrackerService(match_tracker_manager, live_score_client)
        bet_orchestrator = BetOrchestrator(
            market_service=market_service,
            betting_service=betting_service,
            bet_tracker=bet_tracker,
            excel_writer=excel_writer,
            skipped_matches_writer=skipped_matches_writer,
            sound_notifier=sound_notifier,
            telegram_notifier=telegram_notifier,
            config=config
        )
        
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
                # Step 1: Detect Betfair markets using MarketDetector service
                unique_events = market_detector.detect_markets()
                market_detector.log_markets(unique_events)
                
                # Step 2: Poll Live Score API using LiveScorePoller service
                if live_score_client and match_matcher and match_tracker_manager:
                    # Calculate polling interval
                    current_live_api_polling_interval = polling_interval_service.calculate_live_api_interval(match_tracker_manager)
                    
                    # Poll Live API
                    live_matches = live_score_poller.poll(current_live_api_polling_interval)
                    live_score_poller.log_matches(live_matches)
                    
                    # Step 3: Perform matching using MatchingService
                    if unique_events and live_matches:
                        matched_count, total_events, new_tracked_matches, skipped_matches_list, unmatched_events = matching_service.perform_matching(
                            unique_events=unique_events,
                            live_matches=live_matches,
                            iteration=iteration,
                            is_refresh=False,
                            matching_refresh_interval=3600
                            )
                        
                    # Step 4: Update trackers using TrackerService
                    if live_matches:
                        state_changes = tracker_service.update_trackers(live_matches)
                        
                        # Step 5: Attempt bets using BetOrchestrator
                        all_trackers = match_tracker_manager.get_all_trackers()
                        for tracker in all_trackers:
                            bet_orchestrator.attempt_bet(tracker)
                    
                # Log tracking list EVERY 15s (real-time updates)
                # Log AFTER Betfair and Live API logs, showing current state with latest data
                project_root = Path(__file__).parent.parent
                excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                log_tracking_list(match_tracker_manager, excel_path=str(excel_path) if excel_path.exists() else None)
                
                # Note: Log for Betfair matches is already shown above (line 752), even when 0 matches
                
                # Reset error counter on success
                consecutive_errors = 0
                
                # Step 6: Calculate Betfair polling interval using PollingIntervalService
                current_betfair_polling_interval = polling_interval_service.calculate_betfair_interval(match_tracker_manager)
                
                # Wait before next iteration (check stop event during sleep)
                try:
                    # Sleep in small chunks to check stop event more frequently
                    sleep_chunks = max(1, int(current_betfair_polling_interval / 2))  # Check every 0.5s or 1s
                    for _ in range(sleep_chunks):
                        time.sleep(current_betfair_polling_interval / sleep_chunks)
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
