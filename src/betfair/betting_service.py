"""
Betting Service Module
Handles placing bets on Betfair Exchange
"""
import requests
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("BetfairBot")


class BettingService:
    """Handles bet placement on Betfair Exchange"""
    
    def __init__(self, app_key: str, session_token: str, api_endpoint: str):
        """
        Initialize betting service
        
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
        logger.debug("Session token updated in betting service")
    
    def place_orders(self, market_id: str, instructions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Place orders on Betfair Exchange
        
        Args:
            market_id: Market ID to place bet on
            instructions: List of instruction dictionaries
        
        Returns:
            Response dictionary with betId and status, or None if error
        """
        try:
            url = f"{self.api_endpoint}/placeOrders/"
            
            payload = {
                "marketId": market_id,
                "instructions": instructions
            }
            
            logger.debug(f"Placing orders on market {market_id}: {len(instructions)} instruction(s)")
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # Check for errors in response
            if isinstance(result, dict) and "error" in result:
                error_code = result.get("error", {}).get("code", "UNKNOWN")
                error_message = result.get("error", {}).get("message", "Unknown error")
                logger.error(f"Betfair API error: {error_code} - {error_message}")
                return None
            
            logger.info(f"Orders placed successfully on market {market_id}")
            return result
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed - session token may have expired")
                raise
            else:
                error_text = e.response.text[:200] if e.response.text else "No error details"
                logger.error(f"HTTP error placing orders: {e.response.status_code} - {error_text}")
                return None
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            logger.error(f"Network error placing orders: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error placing orders: {str(e)}")
            return None
    
    def place_lay_bet(self, market_id: str, selection_id: int, 
                     price: float, size: float, 
                     persistence_type: str = "LAPSE",
                     handicap: float = 0.0) -> Optional[Dict[str, Any]]:
        """
        Place a lay bet on a selection
        
        Args:
            market_id: Market ID
            selection_id: Selection ID to lay
            price: Lay price (odds)
            size: Stake size
            persistence_type: "LAPSE" or "PERSIST"
            handicap: Handicap value (default: 0.0)
        
        Returns:
            Response dictionary with betId and status, or None if error
        """
        instruction = {
            "selectionId": selection_id,
            "handicap": handicap,
            "side": "LAY",
            "orderType": "LIMIT",
            "limitOrder": {
                "size": size,
                "price": price,
                "persistenceType": persistence_type
            }
        }
        
        result = self.place_orders(market_id, [instruction])
        
        if result and "instructionReports" in result:
            report = result["instructionReports"][0] if result["instructionReports"] else None
            if report:
                status = report.get("status", "UNKNOWN")
                bet_id = report.get("betId")
                
                if status == "SUCCESS":
                    logger.info(f"Lay bet placed successfully: BetId={bet_id}, Price={price}, Size={size}")
                    return {
                        "betId": bet_id,
                        "status": status,
                        "orderStatus": report.get("orderStatus"),
                        "sizeMatched": report.get("sizeMatched", 0.0),
                        "averagePriceMatched": report.get("averagePriceMatched", 0.0),
                        "placedDate": report.get("placedDate")
                    }
                else:
                    error_code = report.get("errorCode")
                    error_message = report.get("instruction", {}).get("limitOrder", {}).get("size", "Unknown")
                    logger.error(f"Bet placement failed: {status}, ErrorCode={error_code}")
                    return None
        
        return None

