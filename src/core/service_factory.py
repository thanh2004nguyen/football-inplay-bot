"""
Service Factory Module
Creates services for the bot
"""
import logging
from typing import Optional

logger = logging.getLogger("BetfairBot")


class ServiceFactory:
    """Factory to create services"""
    
    def __init__(self, config: dict):
        """
        Initialize service factory
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
    
    def create_betting_service(self, app_key: str, session_token: str, 
                              api_endpoint: str):
        """
        Create betting service
        
        Args:
            app_key: Betfair app key
            session_token: Session token
            api_endpoint: API endpoint
        
        Returns:
            BettingService
        """
        from services.betfair import BettingService
        return BettingService(app_key, session_token, api_endpoint)
    
    def create_market_service(self, app_key: str, session_token: str,
                             api_endpoint: str, account_endpoint: str):
        """
        Create market service
        
        Args:
            app_key: Betfair app key
            session_token: Session token
            api_endpoint: API endpoint
            account_endpoint: Account API endpoint (not used by MarketService, but kept for consistency)
        
        Returns:
            MarketService
        """
        from services.betfair import MarketService
        # MarketService doesn't need account_endpoint in constructor, but we store it for get_account_funds
        market_service = MarketService(app_key, session_token, api_endpoint)
        # Store account_endpoint for get_account_funds method
        market_service.account_endpoint = account_endpoint
        return market_service
    
    def create_live_score_client(self, api_key: str, api_secret: str,
                                 base_url: str, rate_limit_per_day: int):
        """
        Create Live Score client
        
        Args:
            api_key: Live Score API key
            api_secret: Live Score API secret
            base_url: Base URL
            rate_limit_per_day: Rate limit per day
        
        Returns:
            LiveScoreClient
        """
        from services.live import LiveScoreClient
        return LiveScoreClient(api_key, api_secret, base_url, rate_limit_per_day)

