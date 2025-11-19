"""
Setup utilities for initializing services and building checklist
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple, Optional

logger = logging.getLogger("BetfairBot")


def initialize_all_services(config: dict, session_token: str, service_factory: Any, 
                            authenticator: Any, use_password_login: bool) -> Tuple[Dict[str, Any], List[str]]:
    """
    Initialize all services and build setup checklist
    
    Args:
        config: Bot configuration
        session_token: Betfair session token
        service_factory: ServiceFactory instance
        authenticator: BetfairAuthenticator instance
        use_password_login: Whether password login is being used
    
    Returns:
        Tuple of (services_dict, checklist_items)
    """
    from utils import create_session_expired_handler
    from notifications.sound_notifier import SoundNotifier
    from notifications.email_notifier import EmailNotifier
    from notifications.telegram_notifier import TelegramNotifier
    from tracking.bet_tracker import BetTracker
    from tracking.excel_writer import ExcelWriter
    from tracking.skipped_matches_writer import SkippedMatchesWriter
    from football_api.matcher import MatchMatcher
    from logic.match_tracker import MatchTrackerManager
    from config.competition_mapper import (get_competition_ids_from_excel, 
                                          get_competitions_with_zero_zero_exception,
                                          get_live_api_competition_ids_from_excel)
    from auth.keep_alive import KeepAliveManager
    
    services = {}
    checklist_items = []
    betfair_config = config["betfair"]
    
    # Initialize market service
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
    
    # Initialize keep-alive
    keep_alive_interval = config["session"].get("keep_alive_interval_seconds", 300)
    keep_alive_manager = KeepAliveManager(
        app_key=betfair_config["app_key"],
        session_token=session_token,
        keep_alive_interval=keep_alive_interval
    )
    
    # Create callback for session expiry
    handle_session_expired = create_session_expired_handler(
        use_password_login=use_password_login,
        authenticator=authenticator,
        market_service=market_service,
        keep_alive_manager=keep_alive_manager,
        betting_service=None  # Will be updated after betting_service is created
    )
    
    keep_alive_manager.on_session_expired = handle_session_expired
    keep_alive_manager.start()
    services['keep_alive_manager'] = keep_alive_manager
    
    # Get account funds
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
    
    # Add login status to checklist
    login_method_str = "Password" if use_password_login else "Certificate"
    checklist_items.append(f"  ✓ Login ({login_method_str}): Success - Account balance: {account_balance_str}")
    
    # Initialize Live Score API client
    live_score_config = config.get("live_score_api", {})
    live_api_rate_limit = "N/A"
    if not live_score_config:
        services['live_score_client'] = None
        services['match_matcher'] = None
        services['match_tracker_manager'] = None
        services['zero_zero_exception_competitions'] = set()
    else:
        # Get rate limit from config
        api_plan = live_score_config.get("api_plan", "trial")
        rate_limit = live_score_config.get("rate_limit_per_day")
        
        if rate_limit is None:
            rate_limit = 14500 if api_plan == "paid" else 1500
        
        live_api_rate_limit = f"{rate_limit}/day"
        
        # Create Live Score client
        live_score_client = service_factory.create_live_score_client(
            api_key=live_score_config.get("api_key", ""),
            api_secret=live_score_config.get("api_secret", ""),
            base_url=live_score_config.get("base_url", "https://livescore-api.com/api-client"),
            rate_limit_per_day=rate_limit
        )
        services['live_score_client'] = live_score_client
        services['match_matcher'] = MatchMatcher()
        services['match_tracker_manager'] = MatchTrackerManager()
        
        # Load 0-0 exception competitions from Excel
        project_root = Path(__file__).parent.parent.parent
        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
        if excel_path.exists():
            services['zero_zero_exception_competitions'] = get_competitions_with_zero_zero_exception(str(excel_path))
            # Load Live API competition IDs for filtering
            live_api_competition_ids = get_live_api_competition_ids_from_excel(str(excel_path))
            services['live_api_competition_ids'] = live_api_competition_ids
        else:
            services['zero_zero_exception_competitions'] = set()
            services['live_api_competition_ids'] = []
    
    # Initialize Bet Tracking
    bet_tracking_config = config.get("bet_tracking", {})
    if bet_tracking_config.get("track_outcomes", True):
        excel_path = bet_tracking_config.get("excel_path", "competitions/Competitions_Results_Odds_Stake.xlsx")
        project_root = Path(__file__).parent.parent.parent
        excel_path_full = project_root / excel_path
        
        # Try to load bankroll from Excel (last Updated_Bankroll value from settled bets)
        # Per client requirement: Bankroll should be updated automatically in Excel when bet result is known
        # and used as the base for future liability calculations
        excel_writer_temp = ExcelWriter(str(excel_path_full))
        bankroll_from_excel = None
        try:
            all_bets = excel_writer_temp.get_all_bets()
            if not all_bets.empty and 'Updated_Bankroll' in all_bets.columns:
                # Get last Updated_Bankroll from settled bets (Won/Lost/VOID)
                # This represents the most recent bankroll after settlement
                settled_bets = all_bets[all_bets['Outcome'].isin(['Won', 'Lost', 'VOID'])]
                if not settled_bets.empty:
                    # Get the last row's Updated_Bankroll
                    last_bankroll = settled_bets['Updated_Bankroll'].dropna()
                    if not last_bankroll.empty:
                        try:
                            bankroll_from_excel = float(last_bankroll.iloc[-1])
                            logger.info(f"Loaded bankroll from Excel (last settled bet): {bankroll_from_excel:.2f}")
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            logger.debug(f"Could not load bankroll from Excel: {str(e)}")
        
        # Use bankroll from Excel if available, otherwise use account balance
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
    
    # Initialize Skipped Matches Writer
    project_root = Path(__file__).parent.parent.parent
    skipped_matches_path = project_root / "competitions" / "Skipped Matches.xlsx"
    services['skipped_matches_writer'] = SkippedMatchesWriter(str(skipped_matches_path))
    checklist_items.append(f"  ✓ Skipped matches writer: {skipped_matches_path.name}")
    
    # 0-0 Exception Competitions
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
    
    # Initialize Betting Service
    bet_execution_config = config.get("bet_execution", {})
    if bet_execution_config:
        betting_service = service_factory.create_betting_service(
            app_key=betfair_config.get("app_key", ""),
            session_token=session_token,
            api_endpoint=betfair_config.get("api_endpoint", "")
        )
        services['betting_service'] = betting_service
        
        # Update session expired handler with betting_service
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
    
    # Initialize Sound Notifications
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
    
    # Initialize Telegram Notifier
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
    
    # Setup monitoring config and competition mapping
    monitoring_config = config["monitoring"]
    event_type_ids = monitoring_config.get("event_type_ids", [1])
    competition_ids = monitoring_config.get("competition_ids", [])
    
    project_root = Path(__file__).parent.parent.parent
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    if excel_path.exists():
        checklist_items.append(f"  ✓ Reading competitions from Excel: {excel_path.name}")
    else:
        checklist_items.append(f"  ⚠ Reading competitions from Excel: File not found")
    
    # Try to map competitions from Excel
    if not competition_ids and excel_path.exists():
        betfair_competitions = market_service.list_competitions(event_type_ids)
        
        if betfair_competitions:
            mapped_ids = get_competition_ids_from_excel(str(excel_path), betfair_competitions)
            if mapped_ids:
                competition_ids = mapped_ids
    
    services['event_type_ids'] = event_type_ids
    services['competition_ids'] = competition_ids
    
    # Rate limits
    betfair_rate_limit = f"Max data weight: {max_data_weight_points} points"
    checklist_items.append(f"  ✓ Rate limits: Live API: {live_api_rate_limit}, Betfair: {betfair_rate_limit}")
    
    # Polling intervals
    monitoring_config = config.get("monitoring", {})
    betfair_polling_interval = monitoring_config.get("polling_interval_seconds", 10)
    live_api_polling_interval = live_score_config.get("polling_interval_seconds", 60) if live_score_config else 60
    checklist_items.append(f"  ✓ Polling intervals: Live API: {live_api_polling_interval}s/request - Betfair: {betfair_polling_interval}s/request")
    
    # Logging status
    checklist_items.append(f"  ✓ Logging initialized successfully")
    
    # Mapped competitions (at the end)
    if competition_ids and excel_path.exists():
        try:
            import pandas as pd
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
            # Fallback
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
    
    # Add stop instruction at the end
    checklist_items.append("")
    checklist_items.append(f"  ℹ Press Ctrl + C to stop the program")
    
    return services, checklist_items

