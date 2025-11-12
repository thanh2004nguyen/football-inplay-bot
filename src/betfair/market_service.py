"""
Betfair Market Service Module
Retrieves and filters live football markets from Betfair Italy Exchange
"""
import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("BetfairBot")


class MarketService:
    """Handles Betfair market data retrieval"""
    
    def __init__(self, app_key: str, session_token: str, api_endpoint: str):
        """
        Initialize market service
        
        Args:
            app_key: Betfair Application Key
            session_token: Current session token
            api_endpoint: Betfair API endpoint base URL
        """
        self.app_key = app_key
        self.session_token = session_token
        self.api_endpoint = api_endpoint.rstrip('/')
        self.headers = {
            'X-Application': app_key,
            'X-Authentication': session_token,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    
    def update_session_token(self, new_token: str):
        """Update session token after re-authentication"""
        self.session_token = new_token
        self.headers['X-Authentication'] = new_token
        logger.debug("Session token updated in market service")
    
    def list_event_types(self) -> List[Dict[str, Any]]:
        """
        List all available event types (sports)
        
        Returns:
            List of event type dictionaries
        """
        try:
            url = f"{self.api_endpoint}/listEventTypes/"
            payload = {"filter": {}}
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            event_types = result if isinstance(result, list) else []
            
            logger.info(f"Retrieved {len(event_types)} event types")
            return event_types
            
        except Exception as e:
            logger.error(f"Error listing event types: {str(e)}")
            return []
    
    def list_competitions(self, event_type_ids: List[int]) -> List[Dict[str, Any]]:
        """
        List competitions for given event types
        
        Args:
            event_type_ids: List of event type IDs (e.g., [1] for Soccer)
        
        Returns:
            List of competition dictionaries
        """
        try:
            url = f"{self.api_endpoint}/listCompetitions/"
            payload = {
                "filter": {
                    "eventTypeIds": event_type_ids
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            competitions = result if isinstance(result, list) else []
            
            logger.info(f"Retrieved {len(competitions)} competitions for event types {event_type_ids}")
            return competitions
            
        except Exception as e:
            logger.error(f"Error listing competitions: {str(e)}")
            return []
    
    def list_market_catalogue(self, event_type_ids: List[int], 
                             competition_ids: List[int] = None,
                             in_play_only: bool = True,
                             market_type_codes: List[str] = None,
                             max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        List market catalogue with filters
        
        Args:
            event_type_ids: List of event type IDs (e.g., [1] for Soccer)
            competition_ids: Optional list of competition IDs to filter
            in_play_only: Only return in-play markets
            market_type_codes: Optional list of market type codes (e.g., ["MATCH_ODDS"])
            max_results: Maximum number of results to return
        
        Returns:
            List of market catalogue dictionaries
        """
        try:
            url = f"{self.api_endpoint}/listMarketCatalogue/"
            
            # Build filter
            filter_dict = {
                "eventTypeIds": event_type_ids,
                "inPlay": in_play_only
            }
            
            if competition_ids:
                filter_dict["competitionIds"] = competition_ids
            
            if market_type_codes:
                filter_dict["marketTypeCodes"] = market_type_codes
            
            # Reduce maxResults to avoid TOO_MUCH_DATA error
            # When filtering by competitions, still limit results
            if competition_ids:
                max_results = min(max_results, 50)  # Limit to 50 when filtering by competitions
            else:
                max_results = min(max_results, 100)  # Limit to 100 when getting all competitions
            
            # Reduce marketProjection to minimize data size
            # Only request essential fields to avoid TOO_MUCH_DATA
            payload = {
                "filter": filter_dict,
                "maxResults": max_results,
                "marketProjection": [
                    "COMPETITION",
                    "EVENT",
                    "MARKET_DESCRIPTION"
                ]
            }
            
            logger.debug(f"Requesting market catalogue with filter: {filter_dict}")
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            markets = result if isinstance(result, list) else []
            
            logger.debug(f"Retrieved {len(markets)} markets from catalogue")
            return markets
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed - session token may have expired")
                # Raise authentication errors so main.py can handle re-login
                raise
            else:
                logger.error(f"HTTP error listing market catalogue: {e.response.status_code} - {e.response.text}")
                # Raise HTTP errors so main.py can handle retry
                raise
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            # Re-raise network errors so main.py can handle retry/reconnect
            logger.debug(f"Network error in list_market_catalogue: {str(e)}")
            raise
        except Exception as e:
            # Only catch unexpected errors, log and return empty list
            logger.error(f"Unexpected error listing market catalogue: {str(e)}")
            return []
    
    def list_market_book(self, market_ids: List[str], 
                        price_projection: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get detailed market book data including prices
        
        Args:
            market_ids: List of market IDs
            price_projection: Optional price projection settings
        
        Returns:
            List of market book dictionaries
        """
        try:
            url = f"{self.api_endpoint}/listMarketBook/"
            
            payload = {
                "marketIds": market_ids,
                "priceProjection": price_projection or {
                    "priceData": ["EX_BEST_OFFERS", "SP_AVAILABLE", "SP_TRADED"]
                }
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            market_books = result if isinstance(result, list) else []
            
            logger.debug(f"Retrieved market book for {len(market_books)} markets")
            return market_books
            
        except Exception as e:
            logger.error(f"Error listing market book: {str(e)}")
            return []
    
    def get_account_funds(self) -> Optional[Dict[str, Any]]:
        """
        Get account balance and funds information
        
        Returns:
            Account funds dictionary or None if error
        """
        try:
            # Use account endpoint directly
            account_endpoint = "https://api.betfair.com/exchange/account/rest/v1.0"
            url = f"{account_endpoint}/getAccountFunds/"
            
            # Account API needs both headers for Italian Exchange
            account_headers = {
                'X-Application': self.app_key,
                'X-Authentication': self.session_token,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json={}, headers=account_headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info("Account funds retrieved successfully")
            return result
            
        except requests.exceptions.HTTPError as e:
            # Account funds is non-critical, just log warning
            logger.warning(f"Could not retrieve account funds: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.warning(f"Error getting account funds: {str(e)}")
            return None

