"""
Mock Betting Service for Test Mode
Simulates bet placement without making real API calls
"""
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class MockBettingService:
    """Mock betting service that simulates bet placement for test mode"""
    
    def __init__(self, mock_bet_id_prefix: str = "TEST_", simulate_matched: bool = False):
        """
        Initialize mock betting service
        
        Args:
            mock_bet_id_prefix: Prefix for mock bet IDs (e.g., "TEST_")
            simulate_matched: If True, simulate bet matched immediately (sizeMatched > 0)
        """
        self.mock_bet_id_prefix = mock_bet_id_prefix
        self.bet_counter = 0
        self.simulate_matched = simulate_matched
        logger.info(f"MockBettingService initialized (TEST MODE, simulate_matched={simulate_matched})")
    
    def update_session_token(self, new_token: str):
        """Update session token (no-op for mock service)"""
        logger.debug("Mock service: Session token update (no-op)")
    
    def place_orders(self, market_id: str, instructions: list) -> Optional[Dict[str, Any]]:
        """
        Simulate placing orders (test mode)
        
        Args:
            market_id: Market ID
            instructions: List of instruction dictionaries
        
        Returns:
            Mock response dictionary
        """
        self.bet_counter += 1
        mock_bet_id = f"{self.mock_bet_id_prefix}{int(time.time() * 1000)}_{self.bet_counter}"
        
        logger.info(f"[TEST MODE] Simulating bet placement: MarketId={market_id}, Instructions={len(instructions)}")
        
        # Simulate API delay
        time.sleep(0.1)
        
        # Return mock response
        return {
            "instructionReports": [
                {
                    "status": "SUCCESS",
                    "betId": mock_bet_id,
                    "orderStatus": "EXECUTABLE",
                    "sizeMatched": 0.0,
                    "averagePriceMatched": 0.0,
                    "placedDate": datetime.now().isoformat()
                }
            ]
        }
    
    def place_lay_bet(self, market_id: str, selection_id: int, 
                     price: float, size: float, 
                     persistence_type: str = "LAPSE",
                     handicap: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Simulate placing a lay bet (test mode)
        
        Args:
            market_id: Market ID
            selection_id: Selection ID to lay
            price: Lay price (odds)
            size: Stake size
            persistence_type: "LAPSE" or "PERSIST"
            handicap: Handicap value (default: 0.0)
        
        Returns:
            Mock response dictionary with betId and status
        """
        self.bet_counter += 1
        mock_bet_id = f"{self.mock_bet_id_prefix}{int(time.time() * 1000)}_{self.bet_counter}"
        
        logger.info(f"[TEST MODE] Simulating lay bet placement:")
        logger.info(f"  MarketId: {market_id}")
        logger.info(f"  SelectionId: {selection_id}")
        logger.info(f"  Price: {price}")
        logger.info(f"  Size: {size}")
        logger.info(f"  PersistenceType: {persistence_type}")
        logger.info(f"  Mock BetId: {mock_bet_id}")
        
        # Simulate API delay
        time.sleep(0.1)
        
        # Return mock response
        # If simulate_matched is True, simulate bet matched immediately
        size_matched = 0.0
        average_price_matched = 0.0
        if self.simulate_matched:
            size_matched = size  # Fully matched
            average_price_matched = price  # Matched at lay price
            logger.info(f"[TEST MODE] Simulating bet matched immediately: SizeMatched={size_matched}")
        
        return {
            "betId": mock_bet_id,
            "status": "SUCCESS",
            "orderStatus": "EXECUTABLE",
            "sizeMatched": size_matched,
            "averagePriceMatched": average_price_matched,
            "placedDate": datetime.now().isoformat()
        }

