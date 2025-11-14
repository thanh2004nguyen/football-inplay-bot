"""
Mock Market Service for Test Mode
Simulates market data retrieval without making real API calls
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("BetfairBot")


class MockMarketService:
    """Mock market service that simulates market data retrieval for test mode"""
    
    def __init__(self, test_mode_config: dict):
        """
        Initialize mock market service
        
        Args:
            test_mode_config: Test mode configuration dictionary
        """
        self.test_mode_config = test_mode_config
        self.mock_data = test_mode_config.get("mock_data", {})
        logger.info("MockMarketService initialized (TEST MODE)")
    
    def update_session_token(self, new_token: str):
        """Update session token (no-op for mock service)"""
        logger.debug("Mock service: Session token update (no-op)")
    
    def list_market_catalogue(self, event_type_ids: List[int], 
                             competition_ids: List[int] = None,
                             in_play_only: bool = True,
                             market_type_codes: List[str] = None,
                             max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        Simulate listing market catalogue (test mode)
        
        Returns mock markets based on test_mode_config or default mock data
        """
        logger.info(f"[TEST MODE] Simulating list_market_catalogue")
        
        # Check if custom mock markets are provided
        mock_markets = self.mock_data.get("markets", [])
        if mock_markets:
            logger.info(f"[TEST MODE] Using {len(mock_markets)} custom mock markets")
            return mock_markets
        
        # Return default empty list (no markets found scenario)
        # In test mode, you can inject markets via config if needed
        logger.info("[TEST MODE] No custom mock markets, returning empty list")
        return []
    
    def list_market_book(self, market_ids: List[str], 
                        price_projection: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Simulate getting market book data (test mode)
        
        Returns mock market book data based on test_mode_config or default mock data
        """
        logger.info(f"[TEST MODE] Simulating list_market_book for {len(market_ids)} market(s)")
        
        # Check if custom mock market books are provided
        mock_market_books = self.mock_data.get("market_books", {})
        
        market_books = []
        for market_id in market_ids:
            if market_id in mock_market_books:
                market_books.append(mock_market_books[market_id])
            else:
                # Return default mock market book
                market_books.append({
                    "marketId": market_id,
                    "status": "OPEN",
                    "runners": [
                        {
                            "selectionId": 12345,
                            "ex": {
                                "availableToBack": [{"price": 2.1, "size": 100.0}],
                                "availableToLay": [{"price": 2.2, "size": 100.0}]
                            },
                            "totalMatched": 10000.0
                        }
                    ]
                })
        
        logger.info(f"[TEST MODE] Returning {len(market_books)} mock market book(s)")
        return market_books
    
    def list_competitions(self, event_type_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Simulate listing competitions (test mode)
        
        Returns mock competitions based on test_mode_config or default mock data
        """
        logger.info(f"[TEST MODE] Simulating list_competitions for event types {event_type_ids}")
        
        # Check if custom mock competitions are provided
        mock_competitions = self.mock_data.get("competitions", [])
        if mock_competitions:
            logger.info(f"[TEST MODE] Using {len(mock_competitions)} custom mock competitions")
            return mock_competitions
        
        # Return default mock competitions based on markets in mock_data
        # Extract unique competitions from markets
        markets = self.mock_data.get("markets", [])
        competitions = []
        seen_competition_ids = set()
        
        for market in markets:
            comp = market.get("competition", {})
            if comp and isinstance(comp, dict):
                comp_id = comp.get("id")
                if comp_id and comp_id not in seen_competition_ids:
                    competitions.append({
                        "id": comp_id,
                        "name": comp.get("name", f"Competition {comp_id}")
                    })
                    seen_competition_ids.add(comp_id)
        
        if competitions:
            logger.info(f"[TEST MODE] Extracted {len(competitions)} competitions from mock markets")
            return competitions
        
        # Return default empty list (no competitions found scenario)
        logger.info("[TEST MODE] No custom mock competitions, returning empty list")
        return []
    
    def get_account_funds(self) -> Optional[Dict[str, Any]]:
        """
        Simulate getting account funds (test mode)
        
        Returns mock account funds based on test_mode_config or default
        """
        logger.info("[TEST MODE] Simulating get_account_funds")
        
        # Check if custom balance is provided
        mock_balance = self.mock_data.get("account_balance", 1000.0)
        
        return {
            "availableToBetBalance": mock_balance,
            "totalBalance": mock_balance,
            "exposure": 0.0,
            "retainedCommission": 0.0
        }

