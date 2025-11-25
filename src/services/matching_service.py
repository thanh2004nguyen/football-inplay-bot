"""
Matching Service
Handles matching between Betfair events and LiveScore matches
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set
from datetime import datetime

from logic.match_tracker import MatchTracker, MatchTrackerManager, MatchState
from services.live import parse_match_score, parse_match_minute, parse_match_teams, parse_match_competition, parse_goals_timeline
from config.competition_mapper import get_betfair_to_live_competition_mapping

logger = logging.getLogger("BetfairBot")


class MatchingService:
    """Service for matching Betfair events with LiveScore matches"""
    
    def __init__(self, live_score_client, match_matcher, match_tracker_manager,
                 config: Dict[str, Any], zero_zero_exception_competitions: Set[str]):
        """
        Initialize Matching Service
        
        Args:
            live_score_client: LiveScore API client
            match_matcher: Match matcher instance
            match_tracker_manager: Match tracker manager
            config: Bot configuration
            zero_zero_exception_competitions: Set of competitions with 0-0 exception
        """
        self.live_score_client = live_score_client
        self.match_matcher = match_matcher
        self.match_tracker_manager = match_tracker_manager
        self.config = config
        self.zero_zero_exception_competitions = zero_zero_exception_competitions
        self._logged_skipped_events: Set[str] = set()
        
        # Load mapping from Excel
        project_root = Path(__file__).parent.parent.parent
        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
        self.betfair_to_live_mapping = {}
        if excel_path.exists():
            self.betfair_to_live_mapping = get_betfair_to_live_competition_mapping(str(excel_path))
    
    def perform_matching(self, unique_events: Dict[str, Dict[str, Any]], 
                        live_matches: List[Dict[str, Any]],
                        iteration: int, is_refresh: bool = False,
                        matching_refresh_interval: int = 3600) -> Tuple[int, int, List[Dict], List[Dict], List[Dict]]:
        """
        Perform matching between Betfair events and LiveScore matches
        
        Args:
            unique_events: Dictionary of Betfair events
            live_matches: List of live matches from LiveScore API
            iteration: Current iteration number
            is_refresh: Whether this is a refresh matching
            matching_refresh_interval: Matching refresh interval in seconds
        
        Returns:
            Tuple of (matched_count, total_events, new_tracked_matches, skipped_matches_list, unmatched_events)
        """
        matched_count = 0
        total_events = len(unique_events)
        new_tracked_matches = []
        skipped_matches_list = []
        unmatched_events = []
        
        # Log refresh message if this is a refresh
        if is_refresh:
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
            tracker = self.match_tracker_manager.get_tracker(event_id)
            if tracker:
                # Update existing tracker - handled by TrackerService
                continue
            else:
                # Try to match with Live API
                betfair_event_with_comp = betfair_event.copy()
                
                # Get competition ID
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
                if competition_id and competition_obj:
                    if isinstance(competition_obj, dict):
                        if "id" not in competition_obj or competition_obj.get("id") != competition_id:
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
                                    betfair_event_with_comp["competition"] = {
                                        "id": competition_id,
                                        "name": market_comp.get("name", competition_name)
                                    }
                                    break
                                except (ValueError, TypeError):
                                    continue
                
                # Skip if no competition ID
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
                
                live_match = self.match_matcher.match_betfair_to_live_api(
                    betfair_event_with_comp, live_matches, competition_name, self.betfair_to_live_mapping
                )
                
                if live_match:
                    matched_count += 1
                    live_match_id = str(live_match.get("id", ""))
                    live_home, live_away = parse_match_teams(live_match)
                    live_comp = parse_match_competition(live_match)
                    live_event_name = f"{live_home} v {live_away}"
                    
                    # Get match tracking config
                    match_tracking_config = self.config.get("match_tracking", {})
                    goal_window = match_tracking_config.get("goal_detection_window", {})
                    start_minute = goal_window.get("start_minute", 60)
                    end_minute = goal_window.get("end_minute", 74)
                    var_check_enabled = match_tracking_config.get("var_check_enabled", True)
                    target_over = match_tracking_config.get("target_over", None)
                    early_discard_enabled = match_tracking_config.get("early_discard_enabled", True)
                    
                    # Get competition name from Live API
                    live_competition_name = parse_match_competition(live_match)
                    tracker_competition_name = live_competition_name if live_competition_name else competition_name
                    
                    # Parse initial match data
                    score = parse_match_score(live_match)
                    minute = parse_match_minute(live_match)
                    
                    # Check if match is too late to start tracking
                    if minute > 74:
                        if event_id not in self._logged_skipped_events:
                            project_root = Path(__file__).parent.parent.parent
                            excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                            target_scores = []
                            if excel_path.exists():
                                from logic.qualification import get_competition_targets
                                comp_id = event_data["competition"].get("id", "")
                                comp_id_str = str(comp_id) if comp_id else None
                                targets = get_competition_targets(tracker_competition_name, str(excel_path), competition_id=comp_id_str)
                                if targets:
                                    target_scores = sorted(list(targets))
                            
                            reason = f"minute {minute} > 74 (not qualified)"
                            logger.info(f"✘ {betfair_event_name}: DISQUALIFIED - {reason}")
                            self._logged_skipped_events.add(event_id)
                        continue
                    
                    # Get strict_discard_at_60 and discard_delay_minutes from config
                    strict_discard_at_60 = match_tracking_config.get("strict_discard_at_60", False)
                    discard_delay_minutes = match_tracking_config.get("discard_delay_minutes", 4)
                    
                    # Create tracker
                    tracker = MatchTracker(
                        betfair_event_id=event_id,
                        betfair_event_name=betfair_event.get("name", "N/A"),
                        live_match_id=live_match_id,
                        competition_name=tracker_competition_name,
                        start_minute=start_minute,
                        end_minute=end_minute,
                        zero_zero_exception_competitions=self.zero_zero_exception_competitions,
                        var_check_enabled=var_check_enabled,
                        target_over=target_over,
                        early_discard_enabled=early_discard_enabled,
                        strict_discard_at_60=strict_discard_at_60,
                        discard_delay_minutes=discard_delay_minutes,
                        live_event_name=live_event_name
                    )
                    
                    # Get goals from events endpoint if match is in monitoring window
                    goals = []
                    if minute >= start_minute or minute >= 60:
                        if self.live_score_client:
                            events_data = self.live_score_client.get_match_details(live_match_id)
                            if events_data:
                                goals = parse_goals_timeline(events_data)
                            else:
                                goals = parse_goals_timeline(live_match)
                    else:
                        goals = parse_goals_timeline(live_match)
                    
                    tracker.update_match_data(score, minute, goals)
                    
                    # Get Excel path for early discard check
                    project_root = Path(__file__).parent.parent.parent
                    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
                    
                    tracker.update_state(excel_path=str(excel_path) if excel_path.exists() else None)
                    
                    # Check if tracker was immediately disqualified
                    if tracker.state == MatchState.DISQUALIFIED:
                        continue
                    
                    # Add to manager
                    self.match_tracker_manager.add_tracker(tracker)
                    
                    # Collect match info for batch logging
                    new_tracked_matches.append({
                        "name": tracker.betfair_event_name,
                        "live_name": tracker.live_event_name,
                        "minute": minute,
                        "score": score,
                        "competition": tracker_competition_name,
                        "excel_path": str(excel_path) if excel_path.exists() else None
                    })
                else:
                    # Analyze rejection reason
                    rejection_reason = "Unknown reason"
                    if self.match_matcher and live_matches:
                        rejection_reason = self.match_matcher.analyze_rejection_reason(
                            betfair_event_with_comp, live_matches, competition_name, self.betfair_to_live_mapping
                        )
                    elif not live_matches:
                        rejection_reason = "No Live API matches available"
                    
                    logger.info(f"⏭️  Skipping: No Live API match - {betfair_event_name} ({competition_name}) - {rejection_reason}")
                    
                    unmatched_events.append({
                        "event_name": betfair_event_name,
                        "competition": competition_name,
                        "reason": rejection_reason
                    })
        
        return matched_count, total_events, new_tracked_matches, skipped_matches_list, unmatched_events

