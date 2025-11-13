"""
Match Tracker Module
Tracks match state and updates match data from Live Score API
"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class MatchState(Enum):
    """Match tracking states"""
    WAITING_60 = "WAITING_60"              # Waiting for minute 60
    MONITORING_60_74 = "MONITORING_60_74"  # Monitoring minutes 60-74
    QUALIFIED = "QUALIFIED"                # Match qualified (goal in 60-74 or 0-0 exception)
    DISQUALIFIED = "DISQUALIFIED"          # Match disqualified (no goal, no 0-0 exception)
    READY_FOR_BET = "READY_FOR_BET"        # Ready to place bet (minute 75+)
    FINISHED = "FINISHED"                  # Match finished


class MatchTracker:
    """Tracks a single match's state and data"""
    
    def __init__(self, betfair_event_id: str, betfair_event_name: str,
                 live_match_id: str, competition_name: str,
                 start_minute: int = 60, end_minute: int = 74,
                 zero_zero_exception_competitions: set = None,
                 var_check_enabled: bool = True,
                 target_over: float = None,
                 early_discard_enabled: bool = True):
        """
        Initialize match tracker
        
        Args:
            betfair_event_id: Betfair event ID
            betfair_event_name: Betfair event name (e.g., "Team A v Team B")
            live_match_id: Live Score API match ID
            competition_name: Competition name
            start_minute: Start of goal detection window (default: 60)
            end_minute: End of goal detection window (default: 74)
            zero_zero_exception_competitions: Set of competitions with 0-0 exception
            var_check_enabled: Whether to check for cancelled goals (VAR)
        """
        self.betfair_event_id = betfair_event_id
        self.betfair_event_name = betfair_event_name
        self.live_match_id = live_match_id
        self.competition_name = competition_name
        self.start_minute = start_minute
        self.end_minute = end_minute
        self.zero_zero_exception_competitions = zero_zero_exception_competitions or set()
        self.var_check_enabled = var_check_enabled
        self.target_over = target_over
        self.early_discard_enabled = early_discard_enabled
        
        # Match data
        self.current_score = "0-0"
        self.current_minute = -1
        self.goals: List[Dict[str, Any]] = []
        self.last_goal_count = 0
        
        # State
        self.state = MatchState.WAITING_60
        self.qualified = False
        self.qualification_reason = ""
        
        # Timestamps
        self.created_at = datetime.now()
        self.last_update = datetime.now()
        self.qualified_at: Optional[datetime] = None
        
        # Bet placement tracking (Milestone 3)
        self.bet_placed = False
        self.bet_id: Optional[str] = None
        
        logger.info(f"Match tracker created: {betfair_event_name} (Betfair ID: {betfair_event_id}, Live ID: {live_match_id})")
    
    def update_match_data(self, score: str, minute: int, goals: List[Dict[str, Any]]):
        """
        Update match data from Live Score API
        
        Args:
            score: Current score (e.g., "2-1")
            minute: Current match minute
            goals: List of goals (may include cancelled)
        """
        self.current_score = score
        self.current_minute = minute
        self.goals = goals
        self.last_update = datetime.now()
        
        # Check for new goals
        current_goal_count = len([g for g in goals if not g.get('cancelled', False)])
        if current_goal_count > self.last_goal_count:
            new_goals = current_goal_count - self.last_goal_count
            logger.info(f"Match {self.betfair_event_name}: {new_goal_count} new goal(s) detected (total: {current_goal_count})")
            self.last_goal_count = current_goal_count
    
    def update_state(self, excel_path: Optional[str] = None):
        """
        Update match state based on current data
        
        Args:
            excel_path: Path to Excel file (for early discard check based on Excel targets)
        """
        from logic.qualification import is_qualified
        
        # Check if match is finished
        if self.current_minute < 0 or self.current_minute > 90:
            if self.state != MatchState.FINISHED:
                self.state = MatchState.FINISHED
                logger.info(f"Match {self.betfair_event_name}: Finished")
            return
        
        # State transitions
        if self.state == MatchState.WAITING_60:
            if self.current_minute >= self.start_minute:
                self.state = MatchState.MONITORING_60_74
                logger.info(f"Match {self.betfair_event_name}: Started monitoring (minute {self.current_minute})")
        
        elif self.state == MatchState.MONITORING_60_74:
            # Check qualification
            if not self.qualified:
                qualified, reason = is_qualified(
                    score=self.current_score,
                    goals=self.goals,
                    current_minute=self.current_minute,
                    start_minute=self.start_minute,
                    end_minute=self.end_minute,
                    competition_name=self.competition_name,
                    zero_zero_exception_competitions=self.zero_zero_exception_competitions,
                    var_check_enabled=self.var_check_enabled,
                    target_over=self.target_over,
                    early_discard_enabled=self.early_discard_enabled,
                    excel_path=excel_path
                )
                
                # If out of target at minute 60, immediately disqualify
                if not qualified and "Out of target" in reason:
                    self.state = MatchState.DISQUALIFIED
                    logger.info(f"Match {self.betfair_event_name}: DISQUALIFIED - {reason}")
                    return
                
                if qualified:
                    self.qualified = True
                    self.qualification_reason = reason
                    self.qualified_at = datetime.now()
                    self.state = MatchState.QUALIFIED
                    logger.info(f"Match {self.betfair_event_name}: QUALIFIED - {reason}")
            
            # Check if window passed
            if self.current_minute > self.end_minute:
                if self.qualified:
                    self.state = MatchState.READY_FOR_BET
                    logger.info(f"Match {self.betfair_event_name}: Ready for bet (minute {self.current_minute})")
                else:
                    self.state = MatchState.DISQUALIFIED
                    logger.info(f"Match {self.betfair_event_name}: Disqualified (no goal in {self.start_minute}-{self.end_minute}, no 0-0 exception)")
        
        elif self.state == MatchState.QUALIFIED:
            # Check if ready for bet (minute 75+)
            if self.current_minute >= 75:
                self.state = MatchState.READY_FOR_BET
                logger.info(f"Match {self.betfair_event_name}: Ready for bet (minute {self.current_minute})")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current match status
        
        Returns:
            Dictionary with match status information
        """
        return {
            "betfair_event_id": self.betfair_event_id,
            "betfair_event_name": self.betfair_event_name,
            "live_match_id": self.live_match_id,
            "competition": self.competition_name,
            "current_score": self.current_score,
            "current_minute": self.current_minute,
            "state": self.state.value,
            "qualified": self.qualified,
            "qualification_reason": self.qualification_reason,
            "goals_count": len([g for g in self.goals if not g.get('cancelled', False)]),
            "last_update": self.last_update.isoformat(),
            "qualified_at": self.qualified_at.isoformat() if self.qualified_at else None
        }
    
    def is_ready_for_bet(self) -> bool:
        """Check if match is ready for bet placement"""
        return self.state == MatchState.READY_FOR_BET and self.qualified


class MatchTrackerManager:
    """Manages multiple match trackers"""
    
    def __init__(self):
        """Initialize match tracker manager"""
        self.trackers: Dict[str, MatchTracker] = {}  # Key: betfair_event_id
        logger.info("Match tracker manager initialized")
    
    def add_tracker(self, tracker: MatchTracker):
        """
        Add a match tracker
        
        Args:
            tracker: MatchTracker instance
        """
        self.trackers[tracker.betfair_event_id] = tracker
        logger.info(f"Added tracker for match: {tracker.betfair_event_name}")
    
    def get_tracker(self, betfair_event_id: str) -> Optional[MatchTracker]:
        """
        Get tracker for a match
        
        Args:
            betfair_event_id: Betfair event ID
        
        Returns:
            MatchTracker instance, or None if not found
        """
        return self.trackers.get(betfair_event_id)
    
    def remove_tracker(self, betfair_event_id: str):
        """
        Remove tracker for a match
        
        Args:
            betfair_event_id: Betfair event ID
        """
        if betfair_event_id in self.trackers:
            tracker = self.trackers.pop(betfair_event_id)
            logger.info(f"Removed tracker for match: {tracker.betfair_event_name}")
    
    def get_all_trackers(self) -> List[MatchTracker]:
        """Get all active trackers"""
        return list(self.trackers.values())
    
    def get_ready_for_bet(self) -> List[MatchTracker]:
        """Get all trackers ready for bet placement"""
        return [t for t in self.trackers.values() if t.is_ready_for_bet()]
    
    def cleanup_finished(self):
        """Remove trackers for finished matches"""
        finished = [event_id for event_id, tracker in self.trackers.items() 
                   if tracker.state == MatchState.FINISHED]
        for event_id in finished:
            self.remove_tracker(event_id)

