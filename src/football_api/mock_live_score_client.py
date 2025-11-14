"""
Mock Live Score Client for Test Mode
Simulates Live Score API calls without making real API requests
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("BetfairBot")


class MockLiveScoreClient:
    """Mock Live Score client that simulates API calls for test mode"""
    
    def __init__(self, test_mode_config: dict):
        """
        Initialize mock Live Score client
        
        Args:
            test_mode_config: Test mode configuration dictionary
        """
        self.test_mode_config = test_mode_config
        self.mock_data = test_mode_config.get("mock_data", {})
        logger.info("MockLiveScoreClient initialized (TEST MODE)")
    
    def get_live_matches(self) -> List[Dict[str, Any]]:
        """
        Simulate getting live matches (test mode)
        
        Returns mock live matches based on test_mode_config or default mock data
        """
        logger.info("[TEST MODE] Simulating get_live_matches")
        
        # Check if custom mock matches are provided
        mock_matches = self.mock_data.get("live_matches", [])
        if mock_matches:
            logger.info(f"[TEST MODE] Using {len(mock_matches)} custom mock live matches")
            return mock_matches
        
        # Return default empty list (no live matches scenario)
        # In test mode, you can inject matches via config if needed
        logger.info("[TEST MODE] No custom mock matches, returning empty list")
        return []
    
    def get_match_details(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Simulate getting match details (test mode)
        
        Returns mock match details based on test_mode_config or default mock data
        """
        logger.info(f"[TEST MODE] Simulating get_match_details for match {match_id}")
        
        # Check if custom match details are provided
        mock_match_details = self.mock_data.get("match_details", {})
        if match_id in mock_match_details:
            logger.info(f"[TEST MODE] Using custom mock details for match {match_id}")
            return mock_match_details[match_id]
        
        # Return default mock match details (matching Live Score API format)
        default_details = {
            "id": match_id,
            "home": {"name": "Team A"},
            "away": {"name": "Team B"},
            "scores": {"score": "1 - 1"},
            "time": "65",
            "status": "1",
            "events": [
                {
                    "id": "1",
                    "type": "goal",
                    "minute": 65,
                    "home_score": "1",
                    "away_score": "1",
                    "cancelled": False
                }
            ]
        }
        
        logger.info(f"[TEST MODE] Returning default mock details for match {match_id}")
        return default_details

