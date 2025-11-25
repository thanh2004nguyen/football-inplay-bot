"""
Polling Interval Service
Calculates dynamic polling intervals based on match states
"""
import logging
from typing import List
from logic.match_tracker import MatchState, MatchTrackerManager

logger = logging.getLogger("BetfairBot")


class PollingIntervalService:
    """Service for calculating polling intervals"""
    
    def __init__(self, default_interval: int = 60, intensive_interval: int = 10, 
                 fast_interval: int = 1, fast_polling_enabled: bool = True):
        """
        Initialize Polling Interval Service
        
        Args:
            default_interval: Default polling interval in seconds (60s)
            intensive_interval: Intensive polling interval in seconds (10s)
            fast_interval: Fast polling interval in seconds (1s)
            fast_polling_enabled: Whether fast polling is enabled
        """
        self.default_interval = default_interval
        self.intensive_interval = intensive_interval
        self.fast_interval = fast_interval
        self.fast_polling_enabled = fast_polling_enabled
    
    def calculate_live_api_interval(self, match_tracker_manager: MatchTrackerManager) -> int:
        """
        Calculate Live API polling interval based on match states
        
        Rules:
        - 0-60: 60s
        - 60-74 (all matches, regardless of QUALIFIED): 10s
        - 74-76 with QUALIFIED/READY_FOR_BET: 10s
        
        Args:
            match_tracker_manager: Match tracker manager
        
        Returns:
            Polling interval in seconds
        """
        if not match_tracker_manager:
            return self.default_interval
        
        all_trackers = match_tracker_manager.get_all_trackers()
        
        # Check for matches in 60-74 range (MONITORING_60_74 or QUALIFIED)
        matches_in_60_74 = [
            t for t in all_trackers
            if 60 <= t.current_minute < 74
            and (t.state == MatchState.MONITORING_60_74 or t.state == MatchState.QUALIFIED)
            and t.state != MatchState.FINISHED
            and t.state != MatchState.DISQUALIFIED
        ]
        
        # Check for QUALIFIED/READY_FOR_BET matches in 74-76 range
        qualified_in_74_76 = [
            t for t in all_trackers
            if 74 <= t.current_minute < 76
            and (t.state == MatchState.QUALIFIED or t.state == MatchState.READY_FOR_BET)
            and t.state != MatchState.FINISHED
            and t.state != MatchState.DISQUALIFIED
        ]
        
        # Determine Live API polling interval
        if matches_in_60_74 or qualified_in_74_76:
            # Has matches in 60-74 (all states) or QUALIFIED/READY_FOR_BET in 74-76: use 10s
            if matches_in_60_74:
                logger.debug(f"Intensive polling active: {len(matches_in_60_74)} match(es) in 60'-74' window (MONITORING_60_74 or QUALIFIED) - using 10s interval")
            if qualified_in_74_76:
                logger.debug(f"Intensive polling active: {len(qualified_in_74_76)} QUALIFIED/READY_FOR_BET match(es) in 74'-76' window - using 10s interval")
            return self.intensive_interval
        else:
            # No matches in 60-74 or QUALIFIED/READY_FOR_BET in 74-76: use 60s
            return self.default_interval
    
    def calculate_betfair_interval(self, match_tracker_manager: MatchTrackerManager) -> int:
        """
        Calculate Betfair polling interval based on match states
        
        Rules:
        - 0-60: 60s
        - 60-74 without QUALIFIED: 60s
        - 60-74 with QUALIFIED: 10s
        - 74-76 with QUALIFIED: 1s
        
        Args:
            match_tracker_manager: Match tracker manager
        
        Returns:
            Polling interval in seconds
        """
        if not match_tracker_manager:
            return self.default_interval
        
        all_trackers = match_tracker_manager.get_all_trackers()
        
        # Check for QUALIFIED matches in different minute ranges
        qualified_in_60_74 = [
            t for t in all_trackers
            if 60 <= t.current_minute < 74
            and t.state == MatchState.QUALIFIED
            and t.state != MatchState.FINISHED
        ]
        
        qualified_in_74_76 = [
            t for t in all_trackers
            if 74 <= t.current_minute < 76
            and (t.state == MatchState.QUALIFIED or t.state == MatchState.READY_FOR_BET)
            and t.state != MatchState.FINISHED
            and not t.bet_placed
            and not getattr(t, 'bet_skipped', False)
        ]
        
        if qualified_in_74_76 and self.fast_polling_enabled:
            # Has QUALIFIED in 74-76: use 1s for Betfair
            logger.debug(f"Fast polling active: {len(qualified_in_74_76)} QUALIFIED match(es) in 74'-76' window")
            return self.fast_interval
        elif qualified_in_60_74:
            # Has QUALIFIED in 60-74: use 10s for Betfair
            logger.debug(f"Intensive polling active: {len(qualified_in_60_74)} QUALIFIED match(es) in 60'-74' window")
            return self.intensive_interval
        else:
            # No QUALIFIED: use 60s for Betfair (0-60 or 60-74 without QUALIFIED)
            return self.default_interval

