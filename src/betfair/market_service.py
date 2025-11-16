"""
Betfair Market Service Module
Retrieves and filters live football markets from Betfair Italy Exchange
"""
import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("BetfairBot")


def calculate_market_projection_weight(market_projection: List[str]) -> int:
    """
    Calculate weight for listMarketCatalogue based on MarketProjection
    
    According to Betfair docs:
    - MARKET_DESCRIPTION: 1
    - RUNNER_METADATA: 1
    - COMPETITION, EVENT, EVENT_TYPE, MARKET_START_TIME: 0
    
    Args:
        market_projection: List of projection strings
        
    Returns:
        Total weight
    """
    weight = 0
    for projection in market_projection:
        if projection == "MARKET_DESCRIPTION":
            weight += 1
        elif projection == "RUNNER_METADATA":
            weight += 1
        # COMPETITION, EVENT, EVENT_TYPE, MARKET_START_TIME have weight 0
    return weight


def calculate_price_projection_weight(price_projection: Dict[str, Any]) -> int:
    """
    Calculate weight for listMarketBook based on PriceProjection
    
    According to Betfair docs:
    - Null (no projection): 2
    - SP_AVAILABLE: 3
    - SP_TRADED: 7
    - EX_BEST_OFFERS: 5
    - EX_ALL_OFFERS: 17
    - EX_TRADED: 17
    - EX_BEST_OFFERS + EX_TRADED: 20 (combined, not sum)
    - EX_ALL_OFFERS + EX_TRADED: 32 (combined, not sum)
    
    Args:
        price_projection: Price projection dict with "priceData" key
        
    Returns:
        Total weight
    """
    if not price_projection or "priceData" not in price_projection:
        return 2  # Null projection
    
    price_data = price_projection.get("priceData", [])
    
    # Check for special combinations first
    has_ex_best_offers = "EX_BEST_OFFERS" in price_data
    has_ex_traded = "EX_TRADED" in price_data
    has_ex_all_offers = "EX_ALL_OFFERS" in price_data
    
    if has_ex_all_offers and has_ex_traded:
        return 32  # EX_ALL_OFFERS + EX_TRADED = 32
    elif has_ex_best_offers and has_ex_traded:
        return 20  # EX_BEST_OFFERS + EX_TRADED = 20
    
    # Calculate individual weights
    weight = 0
    for data_type in price_data:
        if data_type == "SP_AVAILABLE":
            weight += 3
        elif data_type == "SP_TRADED":
            weight += 7
        elif data_type == "EX_BEST_OFFERS":
            weight += 5
        elif data_type == "EX_ALL_OFFERS":
            weight += 17
        elif data_type == "EX_TRADED":
            weight += 17
    
    return weight if weight > 0 else 2  # Default to 2 if empty


class MarketService:
    """Handles Betfair market data retrieval"""
    
    def __init__(self, app_key: str, session_token: str, api_endpoint: str, 
                 max_data_weight_points: int = 190):
        """
        Initialize market service
        
        Args:
            app_key: Betfair Application Key
            session_token: Current session token
            api_endpoint: Betfair API endpoint base URL
            max_data_weight_points: Maximum data weight points per request (default 190, Betfair limit is 200)
        """
        self.app_key = app_key
        self.session_token = session_token
        self.api_endpoint = api_endpoint.rstrip('/')
        self.max_data_weight_points = max_data_weight_points
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
            
        except KeyboardInterrupt:
            # Re-raise KeyboardInterrupt to allow graceful shutdown
            raise
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
            
            # Reduce marketProjection to minimize data size
            # Only request essential fields to avoid TOO_MUCH_DATA
            market_projection = [
                "COMPETITION",
                "EVENT",
                "MARKET_DESCRIPTION"
            ]
            
            # Calculate weight and adjust max_results to stay within limit
            projection_weight = calculate_market_projection_weight(market_projection)
            max_markets_by_weight = self.max_data_weight_points // projection_weight if projection_weight > 0 else 100
            
            # Reduce maxResults to avoid TOO_MUCH_DATA error
            # When filtering by competitions, still limit results
            if competition_ids:
                max_results = min(max_results, 50, max_markets_by_weight)
            else:
                max_results = min(max_results, 100, max_markets_by_weight)
            
            # Final validation: ensure we don't exceed weight limit
            total_weight = projection_weight * max_results
            if total_weight > self.max_data_weight_points:
                max_results = self.max_data_weight_points // projection_weight
                logger.warning(f"Adjusted max_results to {max_results} to stay within data weight limit "
                             f"({projection_weight} weight × {max_results} markets = {total_weight} points)")
            
            payload = {
                "filter": filter_dict,
                "maxResults": max_results,
                "marketProjection": market_projection
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
        
        Automatically splits requests if data weight would exceed limit.
        
        Args:
            market_ids: List of market IDs
            price_projection: Optional price projection settings
        
        Returns:
            List of market book dictionaries
        """
        try:
            url = f"{self.api_endpoint}/listMarketBook/"
            
            # Use default projection if not provided
            if price_projection is None:
                price_projection = {
                    "priceData": ["EX_BEST_OFFERS", "SP_AVAILABLE", "SP_TRADED"]
                }
            
            # Calculate weight for this price projection
            projection_weight = calculate_price_projection_weight(price_projection)
            
            # Calculate max markets per request
            max_markets_per_request = self.max_data_weight_points // projection_weight if projection_weight > 0 else 1
            
            # If we exceed limit, split into multiple requests
            all_market_books = []
            for i in range(0, len(market_ids), max_markets_per_request):
                batch_market_ids = market_ids[i:i + max_markets_per_request]
                
                # Final validation
                total_weight = projection_weight * len(batch_market_ids)
                if total_weight > self.max_data_weight_points:
                    # Further reduce batch size if needed
                    max_batch_size = self.max_data_weight_points // projection_weight
                    batch_market_ids = batch_market_ids[:max_batch_size]
                    logger.warning(f"Reduced batch size to {len(batch_market_ids)} markets to stay within "
                                 f"data weight limit ({projection_weight} weight × {len(batch_market_ids)} = "
                                 f"{projection_weight * len(batch_market_ids)} points)")
                
                payload = {
                    "marketIds": batch_market_ids,
                    "priceProjection": price_projection
                }
                
                response = requests.post(url, json=payload, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                batch_market_books = result if isinstance(result, list) else []
                all_market_books.extend(batch_market_books)
                
                if len(market_ids) > max_markets_per_request:
                    logger.debug(f"Split request: {len(batch_market_ids)}/{len(market_ids)} markets "
                               f"(weight: {projection_weight} × {len(batch_market_ids)} = "
                               f"{projection_weight * len(batch_market_ids)} points)")
            
            logger.debug(f"Retrieved market book for {len(all_market_books)} markets")
            return all_market_books
            
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
            # Use account endpoint (from constructor or default)
            account_endpoint = getattr(self, 'account_endpoint', "https://api.betfair.com/exchange/account/rest/v1.0")
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

