"""
Utility Services Module
Consolidated utility functions: Auth, Setup, Formatters, Bet Utils, Session Utils
"""
import time
import logging
import re
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional, Any, List, Set, Dict
from datetime import datetime

logger = logging.getLogger("BetfairBot")


# ============================================================================
# AUTH UTILITIES
# ============================================================================

def perform_login_with_retry(config: dict, authenticator: Any, email_notifier: Optional[Any] = None) -> Tuple[Optional[str], dict]:
    """Perform login with retry logic and error handling"""
    betfair_config = config["betfair"]
    use_password_login = betfair_config.get("use_password_login", False)
    retry_delay = config.get("session", {}).get("retry_delay_seconds", 10)
    max_login_attempts = 999999
    login_attempt = 0
    session_token = None
    
    email_flags = {
        'email_sent_for_maintenance': False,
        'email_sent_for_terms': False
    }
    
    while login_attempt < max_login_attempts:
        try:
            login_attempt += 1
            
            if use_password_login:
                success, error = authenticator.login_with_password()
            else:
                success, error = authenticator.login()
            
            if success:
                session_token = authenticator.get_session_token()
                break
            else:
                error_str = str(error).upper()
                is_maintenance_error = (
                    "UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT" in error_str or
                    "HTTP 503" in error_str or
                    "SERVER UNDER MAINTENANCE" in error_str
                )
                
                is_retryable_error = is_maintenance_error or any(keyword in error_str for keyword in [
                    "UNAVAILABLE_CONNECTIVITY",
                    "CONNECTION",
                    "TIMEOUT",
                    "NETWORK"
                ])
                
                should_show_retry = (login_attempt == 1) or (login_attempt % 10 == 1)
                
                if is_maintenance_error:
                    if login_attempt == 1:
                        print(f"⚠ Server under maintenance. Check status: https://www.betfair.it")
                        logger.warning(f"Betfair maintenance detected: {error}")
                        logger.info("Check service status at: https://www.betfair.it")
                        
                        if login_attempt == 1 and email_notifier and not email_flags['email_sent_for_maintenance']:
                            try:
                                email_notifier.send_betfair_maintenance_alert(str(error))
                                email_flags['email_sent_for_maintenance'] = True
                                logger.info("Email alert sent for Betfair maintenance (will not send again this session)")
                            except Exception as e:
                                logger.error(f"Failed to send maintenance email: {str(e)}")
                    
                    if should_show_retry:
                        print(f"   Retrying in {retry_delay} seconds... (attempt {login_attempt})")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during login retry")
                        print("\n\nStopping...")
                        return None, email_flags
                elif is_retryable_error:
                    if login_attempt == 1:
                        print(f"⚠ Login failed: {error}")
                    
                    if should_show_retry:
                        print(f"   Retrying in {retry_delay} seconds... (attempt {login_attempt})")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during login retry")
                        print("\n\nStopping...")
                        return None, email_flags
                else:
                    error_str = str(error).upper()
                    is_terms_error = any(keyword in error_str for keyword in [
                        "TERMS", "CONDITIONS", "ACCEPT", "CONFIRMATION", "CONTRACT",
                        "AGREEMENT", "ACCEPTANCE", "REQUIRED"
                    ])
                    
                    if login_attempt == 1:
                        logger.error(f"Login failed: {error}")
                        print(f"✗ Login failed: {error}")
                        print(f"\nPlease check: https://www.betfair.it/ app_key, Username, password.")
                        
                        if login_attempt == 1 and is_terms_error and email_notifier and not email_flags['email_sent_for_terms']:
                            try:
                                email_notifier.send_betfair_terms_confirmation_alert(str(error))
                                email_flags['email_sent_for_terms'] = True
                                logger.info("Email alert sent for Betfair terms confirmation (will not send again this session)")
                            except Exception as e:
                                logger.error(f"Failed to send terms confirmation email: {str(e)}")
                    
                    if should_show_retry:
                        print(f"\nRetrying in {retry_delay} seconds... (attempt {login_attempt}) (Press Ctrl+C to stop)")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during login retry")
                        print("\n\nStopping...")
                        return None, email_flags
        except KeyboardInterrupt:
            logger.info("Interrupted by user during login attempt")
            print("\n\nStopping...")
            return None, email_flags
    
    return session_token, email_flags


# ============================================================================
# SESSION UTILITIES
# ============================================================================

def create_session_expired_handler(use_password_login: bool, authenticator, market_service, 
                                   keep_alive_manager, betting_service=None):
    """Create a callback function for handling session expiry"""
    def handle_session_expired():
        """Callback when keep-alive detects session expiry"""
        logger.warning("Session expiry detected by keep-alive, attempting re-login...")
        try:
            if use_password_login:
                success, error = authenticator.login_with_password()
            else:
                success, error = authenticator.login()
            if success:
                new_token = authenticator.get_session_token()
                market_service.update_session_token(new_token)
                keep_alive_manager.update_session_token(new_token)
                if betting_service:
                    betting_service.update_session_token(new_token)
                logger.info("Re-login successful after keep-alive detected expiry")
            else:
                logger.warning(f"Re-login failed after keep-alive expiry: {error}")
        except Exception as e:
            logger.error(f"Error during re-login from keep-alive callback: {str(e)}")
    
    return handle_session_expired


# ============================================================================
# FORMATTERS
# ============================================================================

def format_tracking_table(trackers: List[Any], excel_path: Optional[str] = None) -> str:
    """Format tracking matches as a table for console output"""
    from logic.qualification import get_competition_targets, normalize_score
    
    if not trackers:
        return "No matches being tracked"
    
    sorted_trackers = sorted(trackers, key=lambda t: (-t.current_minute if t.current_minute >= 0 else 999, t.competition_name))
    
    lines = []
    border = "=" * 108
    separator = "-" * 108
    lines.append(border)
    lines.append("Match | Min | Score | Targets | State")
    lines.append(separator)
    
    for tracker in sorted_trackers:
        target_scores = set()
        if excel_path:
            target_scores = get_competition_targets(tracker.competition_name, excel_path)
        
        if target_scores:
            targets_sorted = sorted(target_scores)
            targets_str = ", ".join(targets_sorted)
        else:
            targets_str = "No targets"
        
        is_target = False
        if target_scores and tracker.current_minute >= 60:
            normalized_score = normalize_score(tracker.current_score)
            normalized_targets = {normalize_score(t) for t in target_scores}
            is_target = normalized_score in normalized_targets
        
        should_show_green_dot = False
        if is_target:
            from logic.qualification import is_score_reached_in_window, normalize_score as norm_score, get_competition_targets
            
            is_zero_zero_at_60 = (tracker.current_minute == 60 and 
                                 tracker.current_score == "0-0" and
                                 excel_path and
                                 norm_score("0-0") in {norm_score(t) for t in get_competition_targets(tracker.competition_name, excel_path)})
            
            if is_zero_zero_at_60:
                should_show_green_dot = True
            elif tracker.qualified:
                score_reached_in_window = is_score_reached_in_window(
                    tracker.current_score,
                    tracker.score_at_minute_60,
                    tracker.goals,
                    tracker.start_minute,
                    tracker.end_minute,
                    tracker.var_check_enabled,
                    tracker.score_after_goal_in_window
                )
                should_show_green_dot = score_reached_in_window
        
        match_name = tracker.betfair_event_name
        minute_str = f"{tracker.current_minute}'" if tracker.current_minute >= 0 else "N/A"
        
        score_str = tracker.current_score
        if should_show_green_dot:
            score_str = f"🟢 {score_str}"
        
        if tracker.state.value == "DISQUALIFIED":
            state_str = f"DISCARDED({tracker.discard_reason or 'unknown'})"
        elif tracker.state.value == "READY_FOR_BET":
            state_str = "READY_FOR_BET"
        elif tracker.state.value == "QUALIFIED":
            state_str = "QUALIFIED"
        elif tracker.state.value == "MONITORING_60_74":
            state_str = "TRACKING"
        elif tracker.state.value == "WAITING_60":
            state_str = "WAITING_60"
        else:
            state_str = tracker.state.value
        
        time_diff = (datetime.now() - tracker.last_update).total_seconds()
        if time_diff > 120:
            state_str += " [STALE]"
        
        if should_show_green_dot:
            state_str = f"TARGET ({state_str})"
        
        line = f"{match_name} | {minute_str} | {score_str} | {targets_str} | {state_str}"
        lines.append(line)
    
    lines.append(border)
    return "\n".join(lines)


def format_skipped_matches_section(skipped_matches: List[Dict[str, Any]]) -> str:
    """Format skipped matches section for console output"""
    if not skipped_matches:
        return ""
    
    lines = []
    for skipped in skipped_matches:
        match_name = skipped.get("match_name", "N/A")
        reason = skipped.get("reason", "Unknown reason")
        lines.append(f"[SKIPPED] {match_name} – Reason: {reason}")
    
    return "\n".join(lines)


def format_boxed_message(message: str) -> str:
    """Format a message with a box border"""
    width = max(60, len(message) + 4)
    
    top_border = "┌" + "─" * (width - 2) + "┐"
    bottom_border = "└" + "─" * (width - 2) + "┘"
    
    padding = (width - len(message) - 2) // 2
    left_padding = " " * padding
    right_padding = " " * (width - len(message) - 2 - padding)
    content = f"│{left_padding}{message}{right_padding}│"
    
    return f"{top_border}\n{content}\n{bottom_border}"


# ============================================================================
# BET UTILITIES
# ============================================================================

def determine_bet_outcome(final_score: str, selection: str, target_over: Optional[float] = None) -> str:
    """Determine bet outcome from final score for Over/Under markets"""
    try:
        parts = final_score.split("-")
        if len(parts) != 2:
            logger.warning(f"Invalid score format: {final_score}")
            return "Void"
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        total_goals = home_goals + away_goals
        
        if target_over is None:
            match = re.search(r'(\d+\.?\d*)', selection)
            if match:
                target_over = float(match.group(1))
            else:
                logger.warning(f"Could not extract target from selection: {selection}")
                return "Void"
        
        selection_lower = selection.lower()
        
        if "over" in selection_lower:
            if total_goals > target_over:
                return "Won"
            else:
                return "Lost"
        elif "under" in selection_lower:
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


def process_finished_matches(match_tracker_manager, bet_tracker, excel_writer, 
                             target_over: Optional[float] = None,
                             telegram_notifier: Optional[Any] = None):
    """Process finished matches: settle bets and export to Excel"""
    from logic.match_tracker import MatchState
    
    if not bet_tracker or not excel_writer:
        return
    
    all_trackers = match_tracker_manager.get_all_trackers()
    finished_trackers = [t for t in all_trackers if t.state == MatchState.FINISHED]
    
    for tracker in finished_trackers:
        final_score = tracker.current_score
        
        bets = bet_tracker.get_bets_by_match_id(tracker.betfair_event_id)
        
        if bets:
            logger.info(f"Processing {len(bets)} bet(s) for finished match: {tracker.betfair_event_name} (Final: {final_score})")
            
            for bet_record in bets:
                if bet_record.outcome is not None:
                    continue
                
                outcome = determine_bet_outcome(
                    final_score=final_score,
                    selection=bet_record.selection,
                    target_over=target_over
                )
                
                settled_bet = bet_tracker.settle_bet(bet_record.bet_id, outcome)
                
                if settled_bet:
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
                    
                    try:
                        bet_dict = settled_bet.to_dict()
                        excel_writer.update_bet_record(
                            bet_id=settled_bet.bet_id,
                            updates={
                                "Outcome": bet_dict.get("Outcome", "Pending"),
                                "Profit_Loss": bet_dict.get("Profit_Loss", 0.0),
                                "Updated_Bankroll": bet_dict.get("Updated_Bankroll", settled_bet.bankroll_before),
                                "Status": bet_dict.get("Status", "Pending"),
                                "Settled_At": bet_dict.get("Settled_At")
                            }
                        )
                        logger.info(f"Bet {settled_bet.bet_id} settled and updated in Excel: {outcome}, P/L: {settled_bet.profit_loss:.2f}, Updated Bankroll: {bet_dict.get('Updated_Bankroll', 0.0):.2f}")
                    except Exception as e:
                        logger.error(f"Error updating bet {settled_bet.bet_id} in Excel: {str(e)}")


# ============================================================================
# SETUP UTILITIES
# ============================================================================

def initialize_all_services(config: dict, session_token: str, service_factory: Any, 
                            authenticator: Any, use_password_login: bool) -> Tuple[Dict[str, Any], List[str]]:
    """Initialize all services and build setup checklist"""
    # create_session_expired_handler is defined in this file, no need to import
    from notifications.sound_notifier import SoundNotifier
    from notifications.email_notifier import EmailNotifier
    from notifications.telegram_notifier import TelegramNotifier
    from services.tracking import BetTracker, ExcelWriter, SkippedMatchesWriter
    from services.live import MatchMatcher
    from logic.match_tracker import MatchTrackerManager
    from config.competition_mapper import (get_competition_ids_from_excel, 
                                          get_competitions_with_zero_zero_exception,
                                          get_live_api_competition_ids_from_excel)
    from auth.keep_alive import KeepAliveManager
    
    services = {}
    checklist_items = []
    betfair_config = config["betfair"]
    
    betfair_api_config = config.get("betfair_api", {})
    max_data_weight_points = betfair_api_config.get("max_data_weight_points", 190)
    
    market_service = service_factory.create_market_service(
        app_key=betfair_config["app_key"],
        session_token=session_token,
        api_endpoint=betfair_config["api_endpoint"],
        account_endpoint=betfair_config.get("account_endpoint", "https://api.betfair.com/exchange/account/rest/v1.0")
    )
    
    if hasattr(market_service, 'max_data_weight_points'):
        market_service.max_data_weight_points = max_data_weight_points
    
    services['market_service'] = market_service
    
    keep_alive_interval = config["session"].get("keep_alive_interval_seconds", 300)
    keep_alive_manager = KeepAliveManager(
        app_key=betfair_config["app_key"],
        session_token=session_token,
        keep_alive_interval=keep_alive_interval
    )
    
    handle_session_expired = create_session_expired_handler(
        use_password_login=use_password_login,
        authenticator=authenticator,
        market_service=market_service,
        keep_alive_manager=keep_alive_manager,
        betting_service=None
    )
    
    keep_alive_manager.on_session_expired = handle_session_expired
    keep_alive_manager.start()
    services['keep_alive_manager'] = keep_alive_manager
    
    account_funds = market_service.get_account_funds()
    initial_bankroll = 0.0
    account_balance_str = "N/A"
    if account_funds:
        available_balance = account_funds.get("availableToBetBalance", "N/A")
        account_balance_str = str(available_balance)
        try:
            initial_bankroll = float(available_balance) if isinstance(available_balance, (int, float, str)) else 0.0
        except (ValueError, TypeError):
            initial_bankroll = 0.0
    
    login_method_str = "Password" if use_password_login else "Certificate"
    checklist_items.append(f"  ✓ Login ({login_method_str}): Success - Account balance: {account_balance_str}")
    
    live_score_config = config.get("live_score_api", {})
    live_api_rate_limit = "N/A"
    if not live_score_config:
        services['live_score_client'] = None
        services['match_matcher'] = None
        services['match_tracker_manager'] = None
        services['zero_zero_exception_competitions'] = set()
    else:
        api_plan = live_score_config.get("api_plan", "trial")
        rate_limit = live_score_config.get("rate_limit_per_day")
        
        if rate_limit is None:
            rate_limit = 14500 if api_plan == "paid" else 1500
        
        live_api_rate_limit = f"{rate_limit}/day"
        
        live_score_client = service_factory.create_live_score_client(
            api_key=live_score_config.get("api_key", ""),
            api_secret=live_score_config.get("api_secret", ""),
            base_url=live_score_config.get("base_url", "https://livescore-api.com/api-client"),
            rate_limit_per_day=rate_limit
        )
        services['live_score_client'] = live_score_client
        services['match_matcher'] = MatchMatcher()
        services['match_tracker_manager'] = MatchTrackerManager()
        
        project_root = Path(__file__).parent.parent.parent
        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
        if excel_path.exists():
            services['zero_zero_exception_competitions'] = get_competitions_with_zero_zero_exception(str(excel_path))
            live_api_competition_ids = get_live_api_competition_ids_from_excel(str(excel_path))
            services['live_api_competition_ids'] = live_api_competition_ids
        else:
            services['zero_zero_exception_competitions'] = set()
            services['live_api_competition_ids'] = []
    
    bet_tracking_config = config.get("bet_tracking", {})
    if bet_tracking_config.get("track_outcomes", True):
        excel_path = bet_tracking_config.get("excel_path", "competitions/Competitions_Results_Odds_Stake.xlsx")
        project_root = Path(__file__).parent.parent.parent
        excel_path_full = project_root / excel_path
        
        excel_writer_temp = ExcelWriter(str(excel_path_full))
        bankroll_from_excel = None
        try:
            all_bets = excel_writer_temp.get_all_bets()
            if not all_bets.empty and 'Updated_Bankroll' in all_bets.columns:
                settled_bets = all_bets[all_bets['Outcome'].isin(['Won', 'Lost', 'VOID'])]
                if not settled_bets.empty:
                    last_bankroll = settled_bets['Updated_Bankroll'].dropna()
                    if not last_bankroll.empty:
                        try:
                            bankroll_from_excel = float(last_bankroll.iloc[-1])
                            logger.info(f"Loaded bankroll from Excel (last settled bet): {bankroll_from_excel:.2f}")
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            logger.debug(f"Could not load bankroll from Excel: {str(e)}")
        
        final_bankroll = bankroll_from_excel if bankroll_from_excel is not None else initial_bankroll
        if bankroll_from_excel is not None:
            logger.info(f"Using bankroll from Excel: {final_bankroll:.2f} (instead of account balance: {initial_bankroll:.2f})")
        
        services['bet_tracker'] = BetTracker(initial_bankroll=final_bankroll)
        services['excel_writer'] = ExcelWriter(str(excel_path_full))
        checklist_items.append(f"  ✓ Bet tracker: Initialized (bankroll: {final_bankroll:.2f})")
        checklist_items.append(f"  ✓ Excel writer: {excel_path_full.name}")
    else:
        services['bet_tracker'] = None
        services['excel_writer'] = None
        checklist_items.append(f"  ✗ Bet tracker: Disabled")
    
    project_root = Path(__file__).parent.parent.parent
    skipped_matches_path = project_root / "competitions" / "Skipped Matches.xlsx"
    services['skipped_matches_writer'] = SkippedMatchesWriter(str(skipped_matches_path))
    checklist_items.append(f"  ✓ Skipped matches writer: {skipped_matches_path.name}")
    
    excel_path_for_zero_zero = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    zero_zero_exception_competitions = services.get('zero_zero_exception_competitions', set())
    if excel_path_for_zero_zero.exists():
        zero_zero_count = len(zero_zero_exception_competitions)
        if zero_zero_count > 0:
            checklist_items.append(f"  ✓ 0-0 exception competitions: {zero_zero_count} competition(s)")
        else:
            checklist_items.append(f"  ✓ 0-0 exception competitions: None")
    else:
        checklist_items.append(f"  ⚠ 0-0 exception competitions: Excel file not found")
    
    bet_execution_config = config.get("bet_execution", {})
    if bet_execution_config:
        betting_service = service_factory.create_betting_service(
            app_key=betfair_config.get("app_key", ""),
            session_token=session_token,
            api_endpoint=betfair_config.get("api_endpoint", "")
        )
        services['betting_service'] = betting_service
        
        handle_session_expired = create_session_expired_handler(
            use_password_login=use_password_login,
            authenticator=authenticator,
            market_service=market_service,
            keep_alive_manager=keep_alive_manager,
            betting_service=betting_service
        )
        keep_alive_manager.on_session_expired = handle_session_expired
    else:
        services['betting_service'] = None
    
    notifications_config = config.get("notifications", {})
    if notifications_config.get("sound_enabled", False):
        try:
            sound_notifier = SoundNotifier(notifications_config)
            services['sound_notifier'] = sound_notifier
            sounds_config = notifications_config.get("sounds", {})
            bet_placed = sounds_config.get("bet_placed", "sounds/success.mp3")
            bet_matched = sounds_config.get("bet_matched", "sounds/ping.mp3")
            checklist_items.append(f"  ✓ Sound notifications: {bet_placed}, {bet_matched}")
        except Exception as e:
            logger.warning(f"Failed to initialize sound notifier: {str(e)}")
            services['sound_notifier'] = None
            checklist_items.append(f"  ✗ Sound notifications: Disabled (initialization failed)")
    else:
        services['sound_notifier'] = None
        checklist_items.append(f"  ✗ Sound notifications: Disabled")
    
    if notifications_config.get("telegram_enabled", False):
        try:
            telegram_notifier = TelegramNotifier(notifications_config)
            services['telegram_notifier'] = telegram_notifier
            telegram_config = notifications_config.get("telegram", {})
            chat_id = telegram_config.get("chat_id", "N/A")
            if telegram_notifier and telegram_notifier.enabled:
                checklist_items.append(f"  ✓ Telegram notifications: Chat ID {chat_id}")
            else:
                checklist_items.append(f"  ✗ Telegram notifications: Disabled (configuration incomplete)")
        except Exception as e:
            services['telegram_notifier'] = None
            checklist_items.append(f"  ✗ Telegram notifications: Disabled (initialization failed)")
    else:
        services['telegram_notifier'] = None
        checklist_items.append(f"  ✗ Telegram notifications: Disabled")
    
    monitoring_config = config["monitoring"]
    event_type_ids = monitoring_config.get("event_type_ids", [1])
    competition_ids = monitoring_config.get("competition_ids", [])
    
    project_root = Path(__file__).parent.parent.parent
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    if excel_path.exists():
        checklist_items.append(f"  ✓ Reading competitions from Excel: {excel_path.name}")
    else:
        checklist_items.append(f"  ⚠ Reading competitions from Excel: File not found")
    
    if not competition_ids and excel_path.exists():
        betfair_competitions = market_service.list_competitions(event_type_ids)
        
        if betfair_competitions:
            mapped_ids = get_competition_ids_from_excel(str(excel_path), betfair_competitions)
            if mapped_ids:
                competition_ids = [int(cid) for cid in mapped_ids if cid is not None]
    
    if competition_ids:
        competition_ids = [int(cid) for cid in competition_ids if cid is not None]
    
    services['event_type_ids'] = event_type_ids
    services['competition_ids'] = competition_ids
    
    betfair_rate_limit = f"Max data weight: {max_data_weight_points} points"
    checklist_items.append(f"  ✓ Rate limits: Live API: {live_api_rate_limit}, Betfair: {betfair_rate_limit}")
    
    monitoring_config = config.get("monitoring", {})
    betfair_polling_interval = monitoring_config.get("polling_interval_seconds", 10)
    live_api_polling_interval = live_score_config.get("polling_interval_seconds", 60) if live_score_config else 60
    checklist_items.append(f"  ✓ Polling intervals: Live API: {live_api_polling_interval}s/request - Betfair: {betfair_polling_interval}s/request")
    
    checklist_items.append(f"  ✓ Logging initialized successfully")
    
    if competition_ids and excel_path.exists():
        try:
            df = pd.read_excel(str(excel_path))
            betfair_competitions = market_service.list_competitions(event_type_ids)
            betfair_comp_dict = {str(c.get("id", "")): c.get("name", "N/A") for c in betfair_competitions} if betfair_competitions else {}
            
            has_live = 'Competition-Live' in df.columns
            has_betfair = 'Competition-Betfair' in df.columns
            
            checklist_items.append("")
            checklist_items.append(f"  ✓ Mapped competitions ({len(competition_ids)} total):")
            
            for betfair_id_str in competition_ids:
                live_id = live_name = "N/A"
                betfair_id = betfair_id_str
                betfair_name = betfair_comp_dict.get(betfair_id_str, "N/A")
                
                if has_live and has_betfair:
                    match = df[df['Competition-Betfair'].astype(str).str.contains(str(betfair_id), na=False, regex=False)]
                    if not match.empty:
                        row = match.iloc[0]
                        live_val = str(row.get('Competition-Live', '')).strip()
                        betfair_val = str(row.get('Competition-Betfair', '')).strip()
                        
                        if "_" in live_val:
                            live_id, live_name = live_val.split("_", 1)
                        else:
                            live_name = live_val
                        
                        if "_" in betfair_val:
                            betfair_id, betfair_name = betfair_val.split("_", 1)
                
                checklist_items.append(f"      • Live: [{live_id}] {live_name} | Betfair: [{betfair_id}] {betfair_name}")
        except:
            betfair_competitions = market_service.list_competitions(event_type_ids)
            comp_dict = {str(c.get("id", "")): c.get("name", "N/A") for c in betfair_competitions} if betfair_competitions else {}
            checklist_items.append("")
            checklist_items.append(f"  ✓ Mapped competitions ({len(competition_ids)} total):")
            for cid in competition_ids:
                checklist_items.append(f"      • Betfair: [{cid}] {comp_dict.get(str(cid), 'N/A')}")
    elif competition_ids:
        betfair_competitions = market_service.list_competitions(event_type_ids)
        comp_dict = {str(c.get("id", "")): c.get("name", "N/A") for c in betfair_competitions} if betfair_competitions else {}
        checklist_items.append("")
        checklist_items.append(f"  ✓ Mapped competitions ({len(competition_ids)} total):")
        for cid in competition_ids:
            checklist_items.append(f"      • Betfair: [{cid}] {comp_dict.get(str(cid), 'N/A')}")
    else:
        checklist_items.append("")
        checklist_items.append(f"  ⚠ Mapped competitions: None (monitoring all competitions)")
    
    checklist_items.append("")
    checklist_items.append(f"  ℹ Press Ctrl + C to stop the program")
    
    return services, checklist_items

