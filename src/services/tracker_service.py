"""
Tracker Service
Handles tracker updates and state management
"""
import logging
from pathlib import Path
from typing import List, Dict, Any
from logic.match_tracker import MatchTrackerManager, MatchState
from services.live import parse_match_score, parse_match_minute, parse_goals_timeline

logger = logging.getLogger("BetfairBot")


class TrackerService:
    """Service for updating and managing trackers"""
    
    def __init__(self, match_tracker_manager: MatchTrackerManager, live_score_client):
        """
        Initialize Tracker Service
        
        Args:
            match_tracker_manager: Match tracker manager
            live_score_client: Live Score API client
        """
        self.match_tracker_manager = match_tracker_manager
        self.live_score_client = live_score_client
        
        # Get Excel path
        project_root = Path(__file__).parent.parent.parent
        self.excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    
    def update_trackers(self, live_matches: List[Dict[str, Any]], 
                       fetch_goals_for_states: List[MatchState] = None) -> List[Dict[str, Any]]:
        """
        Update all trackers with latest Live API data
        
        Args:
            live_matches: List of live matches from cache or API
            fetch_goals_for_states: List of states that need fresh goals data
        
        Returns:
            List of trackers that changed state
        """
        if not self.match_tracker_manager or not live_matches:
            return []
        
        if fetch_goals_for_states is None:
            fetch_goals_for_states = [MatchState.MONITORING_60_74, MatchState.QUALIFIED, MatchState.READY_FOR_BET]
        
        all_trackers = self.match_tracker_manager.get_all_trackers()
        state_changes = []
        
        if all_trackers:
            for tracker in all_trackers:
                try:
                    # Find matching live match from cache
                    live_match = None
                    for lm in live_matches:
                        if str(lm.get("id", "")) == tracker.live_match_id:
                            live_match = lm
                            break
                    
                    if live_match:
                        # Update match data from cached live_match
                        score = parse_match_score(live_match)
                        minute = parse_match_minute(live_match)
                        
                        # Get goals - fetch fresh if in important states
                        goals = []
                        if tracker.state in fetch_goals_for_states:
                            # Fetch events to get goals timeline
                            if self.live_score_client:
                                events_data = self.live_score_client.get_match_details(tracker.live_match_id)
                                if events_data:
                                    goals = parse_goals_timeline(events_data)
                                else:
                                    goals = parse_goals_timeline(live_match)
                        else:
                            # Use cached goals from live_match
                            goals = parse_goals_timeline(live_match)
                        
                        # Update tracker with cached data
                        old_state = tracker.state
                        tracker.update_match_data(score, minute, goals)
                        
                        # Update state
                        excel_path_str = str(self.excel_path) if self.excel_path.exists() else None
                        if not excel_path_str:
                            logger.warning(f"⚠️ Excel path not available for tracker '{tracker.betfair_event_name}' - discard logic will not run")
                        tracker.update_state(excel_path=excel_path_str)
                        
                        # Log status changes
                        if tracker.state == MatchState.QUALIFIED and old_state != MatchState.QUALIFIED:
                            logger.info(f"✓ QUALIFIED: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score}) - {tracker.qualification_reason}")
                            print(f"  ✓ QUALIFIED: {tracker.betfair_event_name} - {tracker.qualification_reason}")
                            state_changes.append({
                                "tracker": tracker,
                                "old_state": old_state,
                                "new_state": tracker.state
                            })
                        elif tracker.state == MatchState.READY_FOR_BET and old_state != MatchState.READY_FOR_BET:
                            logger.info(f"🎯 READY FOR BET: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score})")
                            print(f"  🎯 READY FOR BET: {tracker.betfair_event_name}")
                            state_changes.append({
                                "tracker": tracker,
                                "old_state": old_state,
                                "new_state": tracker.state
                            })
                except Exception as e:
                    logger.warning(f"Error updating tracker '{tracker.betfair_event_name}': {str(e)}")
        
        return state_changes

