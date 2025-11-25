"""
Live Score Poller Service
Handles Live Score API polling with dynamic intervals and caching
"""
import time
import logging
from typing import List, Dict, Any, Optional
from services.live import parse_match_score, parse_match_minute, parse_match_teams, parse_match_competition

logger = logging.getLogger("BetfairBot")


class LiveScorePoller:
    """Service for polling Live Score API with dynamic intervals"""
    
    def __init__(self, live_score_client, live_api_competition_ids: Optional[List[int]] = None):
        """
        Initialize Live Score Poller
        
        Args:
            live_score_client: Live Score API client
            live_api_competition_ids: List of Live API competition IDs to filter
        """
        self.live_score_client = live_score_client
        self.live_api_competition_ids = live_api_competition_ids
        self.cached_matches: List[Dict[str, Any]] = []
        self.last_call_time: Optional[float] = None
    
    def poll(self, polling_interval: int) -> List[Dict[str, Any]]:
        """
        Poll Live Score API with caching
        
        Args:
            polling_interval: Polling interval in seconds
        
        Returns:
            List of live matches (from API or cache)
        """
        current_time = time.time()
        
        # Check if we need to call API (first call or enough time has passed)
        should_call_api = False
        if self.last_call_time is None:
            # First call - always call API
            should_call_api = True
        else:
            time_since_last_call = current_time - self.last_call_time
            if time_since_last_call >= polling_interval:
                should_call_api = True
        
        if should_call_api:
            # Time to call Live API
            api_unreachable = False
            try:
                # Pass Live API competition IDs to filter matches
                live_matches = self.live_score_client.get_live_matches(
                    competition_ids=self.live_api_competition_ids if self.live_api_competition_ids else None
                )
                
                # Check if API is not reachable (None means connection error after retries)
                if live_matches is None:
                    api_unreachable = True
                    # Use cached data if available
                    live_matches = self.cached_matches if self.cached_matches else []
                    # Don't update last_call_time so we retry sooner
                else:
                    # API call successful - update cache and timestamp
                    self.last_call_time = current_time
                    # Only cache if we got valid data (list)
                    if isinstance(live_matches, list):
                        self.cached_matches = live_matches
                    else:
                        logger.warning(f"Live Score API returned invalid data type, using cached data")
                        live_matches = self.cached_matches if self.cached_matches else []
            except Exception as api_error:
                # If API call fails with exception, use cached data if available
                logger.warning(f"Live Score API call failed, using cached data: {str(api_error)[:100]}")
                live_matches = self.cached_matches if self.cached_matches else []
                # Don't update last_call_time so we retry sooner
        else:
            # Use cached matches
            live_matches = self.cached_matches
            api_unreachable = False  # Not calling API, so not unreachable
        
        return live_matches
    
    def log_matches(self, live_matches: List[Dict[str, Any]]):
        """
        Log Live API matches
        
        Args:
            live_matches: List of live matches
        """
        if not live_matches:
            # Log when no matches available
            logger.info(f"Live API: 0 available matches after comparing with Excel.")
            return
        
        # Filter out FINISHED matches and matches at minute 90+ before logging
        actual_live = []
        for lm in live_matches:
            status = str(lm.get("status", "")).upper()
            minute = parse_match_minute(lm)
            # Skip if FINISHED or minute >= 90 (match finished or about to finish)
            if "FINISHED" not in status and minute >= 0 and minute < 90:
                actual_live.append(lm)
        
        # Format log message
        live_api_msg = f"Live API: {len(actual_live)} available matches after comparing with Excel."
        logger.info(live_api_msg)
        
        # Log ALL matches (not just first 5)
        for i, lm in enumerate(actual_live, 1):
            home, away = parse_match_teams(lm)
            comp = parse_match_competition(lm)
            minute = parse_match_minute(lm)
            score = parse_match_score(lm)
            status = lm.get("status", "N/A")
            match_msg = f"  [{i}] {home} v {away} ({comp}) - {score} @ {minute}' [{status}]"
            logger.info(match_msg)

