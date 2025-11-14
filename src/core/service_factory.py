"""
Service Factory Module
Creates real or mock services based on test mode configuration
"""
import logging
from typing import Optional

logger = logging.getLogger("BetfairBot")


class ServiceFactory:
    """Factory to create services (real or mock) based on test mode"""
    
    def __init__(self, config: dict):
        """
        Initialize service factory
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.test_mode_config = config.get("test_mode", {})
        self.is_test_mode = self.test_mode_config.get("enabled", False)
        
        if self.is_test_mode:
            logger.info("=" * 60)
            logger.info("TEST MODE ENABLED - Using mock services")
            logger.info("=" * 60)
            print("=" * 60)
            print("⚠️  TEST MODE ENABLED")
            print("   Bot will NOT place real bets")
            print("   All API calls will be simulated")
            print("=" * 60)
    
    def create_betting_service(self, app_key: str, session_token: str, 
                              api_endpoint: str):
        """
        Create betting service (real or mock)
        
        Args:
            app_key: Betfair app key
            session_token: Session token
            api_endpoint: API endpoint
        
        Returns:
            BettingService or MockBettingService
        """
        if self.is_test_mode:
            from betfair.mock_betting_service import MockBettingService
            mock_bet_id_prefix = self.test_mode_config.get("mock_bet_id_prefix", "TEST_")
            simulate_matched = self.test_mode_config.get("simulate_bet_matched", False)
            return MockBettingService(
                mock_bet_id_prefix=mock_bet_id_prefix,
                simulate_matched=simulate_matched
            )
        else:
            from betfair.betting_service import BettingService
            return BettingService(app_key, session_token, api_endpoint)
    
    def create_market_service(self, app_key: str, session_token: str,
                             api_endpoint: str, account_endpoint: str):
        """
        Create market service (real or mock)
        
        Args:
            app_key: Betfair app key
            session_token: Session token
            api_endpoint: API endpoint
            account_endpoint: Account API endpoint (not used by MarketService, but kept for consistency)
        
        Returns:
            MarketService or MockMarketService
        """
        if self.is_test_mode:
            from betfair.mock_market_service import MockMarketService
            return MockMarketService(self.test_mode_config)
        else:
            from betfair.market_service import MarketService
            # MarketService doesn't need account_endpoint in constructor, but we store it for get_account_funds
            market_service = MarketService(app_key, session_token, api_endpoint)
            # Store account_endpoint for get_account_funds method
            market_service.account_endpoint = account_endpoint
            return market_service
    
    def create_live_score_client(self, api_key: str, api_secret: str,
                                 base_url: str, rate_limit_per_day: int):
        """
        Create Live Score client (real or mock)
        
        Args:
            api_key: Live Score API key
            api_secret: Live Score API secret
            base_url: Base URL
            rate_limit_per_day: Rate limit per day
        
        Returns:
            LiveScoreClient or MockLiveScoreClient
        """
        if self.is_test_mode:
            from football_api.mock_live_score_client import MockLiveScoreClient
            return MockLiveScoreClient(self.test_mode_config)
        else:
            from football_api.live_score_client import LiveScoreClient
            return LiveScoreClient(api_key, api_secret, base_url, rate_limit_per_day)

