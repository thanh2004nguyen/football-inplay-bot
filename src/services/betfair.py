"""
Betfair Services Module
Consolidated Betfair services: Market Service, Betting Service, Stream API, Price Ladder, Market Filter
"""
import requests
import socket
import ssl
import json
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("BetfairBot")

# ============================================================================
# PRICE LADDER FUNCTIONS
# ============================================================================

# CLASSIC Price Ladder increments (from Betfair API documentation)
CLASSIC_LADDER = [
    (1.01, 2.0, 0.01),      # 1.01 → 2: increment 0.01
    (2.0, 3.0, 0.02),      # 2 → 3: increment 0.02
    (3.0, 4.0, 0.05),      # 3 → 4: increment 0.05
    (4.0, 6.0, 0.1),       # 4 → 6: increment 0.1
    (6.0, 10.0, 0.2),      # 6 → 10: increment 0.2
    (10.0, 20.0, 0.5),     # 10 → 20: increment 0.5
    (20.0, 30.0, 1.0),     # 20 → 30: increment 1.0
    (30.0, 50.0, 2.0),     # 30 → 50: increment 2.0
    (50.0, 100.0, 5.0),    # 50 → 100: increment 5.0
    (100.0, 1000.0, 10.0), # 100 → 1000: increment 10.0
]

# FINEST Price Ladder: always 0.01 increment
FINEST_INCREMENT = 0.01


def get_increment_for_price(price: float, ladder_type: str = "CLASSIC") -> float:
    """Get the price increment for a given price based on ladder type"""
    if ladder_type == "FINEST":
        return FINEST_INCREMENT
    
    for min_price, max_price, increment in CLASSIC_LADDER:
        if min_price <= price < max_price:
            return increment
    
    if price >= 1000.0:
        return CLASSIC_LADDER[-1][2]
    if price < 1.01:
        return CLASSIC_LADDER[0][2]
    
    logger.warning(f"Could not determine increment for price {price}, using 0.01")
    return 0.01


def add_ticks_to_price(price: float, ticks: int, ladder_type: str = "CLASSIC") -> float:
    """Add ticks to a price"""
    increment = get_increment_for_price(price, ladder_type)
    new_price = price + (ticks * increment)
    
    if increment >= 1.0:
        new_price = round(new_price, 0)
    elif increment >= 0.1:
        new_price = round(new_price, 1)
    elif increment >= 0.01:
        new_price = round(new_price, 2)
    else:
        new_price = round(new_price, 3)
    
    return new_price


def calculate_ticks_between(price1: float, price2: float, ladder_type: str = "CLASSIC") -> int:
    """Calculate the number of ticks between two prices"""
    if price1 >= price2:
        return 0
    
    if ladder_type == "FINEST":
        return int((price2 - price1) / FINEST_INCREMENT)
    
    current_price = price1
    total_ticks = 0
    
    while current_price < price2:
        increment = get_increment_for_price(current_price, ladder_type)
        next_boundary = None
        
        for min_price, max_price, _ in CLASSIC_LADDER:
            if min_price <= current_price < max_price:
                next_boundary = max_price
                break
        
        if next_boundary is None or next_boundary > price2:
            remaining = price2 - current_price
            ticks_in_range = int(remaining / increment)
            total_ticks += ticks_in_range
            break
        else:
            distance_to_boundary = next_boundary - current_price
            ticks_to_boundary = int(distance_to_boundary / increment)
            total_ticks += ticks_to_boundary
            current_price = next_boundary
    
    return total_ticks


def is_valid_price(price: float, ladder_type: str = "CLASSIC") -> bool:
    """Check if a price is valid according to the price ladder"""
    if price < 1.01:
        return False
    
    if ladder_type == "FINEST":
        return abs(price - round(price, 2)) < 0.001
    
    for min_price, max_price, increment in CLASSIC_LADDER:
        if min_price <= price < max_price:
            diff = price - min_price
            if abs(diff % increment) < 0.001 or abs(diff % increment - increment) < 0.001:
                return True
    
    if price >= 1000.0:
        increment = CLASSIC_LADDER[-1][2]
        base = 1000.0
        diff = price - base
        return abs(diff % increment) < 0.001 or abs(diff % increment - increment) < 0.001
    
    return False


def round_to_valid_price(price: float, ladder_type: str = "CLASSIC") -> float:
    """Round a price to the nearest valid price according to the ladder"""
    if price < 1.01:
        return 1.01
    
    increment = get_increment_for_price(price, ladder_type)
    
    if ladder_type == "FINEST":
        return round(price, 2)
    
    for min_price, max_price, inc in CLASSIC_LADDER:
        if min_price <= price < max_price:
            diff = price - min_price
            ticks = round(diff / inc)
            return min_price + (ticks * inc)
    
    if price >= 1000.0:
        increment = CLASSIC_LADDER[-1][2]
        base = 1000.0
        diff = price - base
        ticks = round(diff / increment)
        return base + (ticks * increment)
    
    return round(price, 2)


# ============================================================================
# MARKET FILTER FUNCTIONS
# ============================================================================

ALLOWED_MARKET_TYPES = [
    "OVER_UNDER_25", "OVER_UNDER_15", "OVER_UNDER_35", "OVER_UNDER_05", "OVER_UNDER_45",
    "MATCH_ODDS", "BOTH_TEAMS_TO_SCORE", "CORRECT_SCORE", "FIRST_GOAL_SCORER", "NEXT_GOAL",
    "HALF_TIME_SCORE", "HALF_TIME_FULL_TIME", "DRAW_NO_BET", "DOUBLE_CHANCE",
    "ASIAN_HANDICAP", "EUROPEAN_HANDICAP", "TOTAL_GOALS", "WIN_DRAW_WIN",
    "TO_SCORE", "TO_SCORE_2_OR_MORE", "TO_SCORE_A_HATTRICK", "ANYTIME_GOALSCORER",
    "FIRST_GOALSCORER", "LAST_GOALSCORER", "MATCH_BETTING", "MATCH_RESULT",
    "TO_WIN_MATCH", "TO_WIN_TO_NIL", "TO_WIN_EITHER_HALF", "TO_WIN_BOTH_HALVES",
    "CLEAN_SHEET", "TEAM_TOTAL_GOALS", "EXACT_GOALS", "ODD_OR_EVEN",
    "GOAL_BOTH_HALVES", "MOST_GOALS", "TO_QUALIFY", "TO_LIFT_TROPHY",
]

EXCLUDED_MARKET_TYPES = [
    "OUTRIGHT", "TOP_GOALSCORER", "RELEGATION", "PROMOTION", "CHAMPION",
    "WINNER", "SEASON_WINNER", "LEAGUE_WINNER", "TITLE_WINNER",
]

EXCLUDED_KEYWORDS = [
    "winner", "champion", "outright", "season", "league winner", "top scorer",
    "relegation", "promotion", "championship", "title", "season winner",
    "golden boot", "player of the season", "manager of the season",
    "young player", "most assists", "most goals", "clean sheets",
    "goalkeeper", "defender", "midfielder", "forward", "team of the season",
]


def is_match_specific_market(market: Dict[str, Any]) -> bool:
    """Check if market is match-specific (not season-long)"""
    market_name = market.get("marketName", "").lower()
    market_type = market.get("marketType", "").upper()
    
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in market_name:
            logger.debug(f"Excluded market (keyword '{keyword}'): {market.get('marketName', 'N/A')}")
            return False
    
    if market_type in EXCLUDED_MARKET_TYPES:
        logger.debug(f"Excluded market (type '{market_type}'): {market.get('marketName', 'N/A')}")
        return False
    
    if market_type in ALLOWED_MARKET_TYPES:
        return True
    
    match_indicators = [
        "over", "under", "match odds", "both teams", "correct score", "first goal", "next goal",
        "half time", "full time", "draw", "handicap", "total goals", "to score",
        "clean sheet", "win to nil", "exact goals", "odd or even", "both halves", "to qualify"
    ]
    
    for indicator in match_indicators:
        if indicator in market_name:
            return True
    
    logger.debug(f"Uncertain market type, excluding (safer): {market.get('marketName', 'N/A')} (type: {market_type})")
    return False


def filter_match_specific_markets(markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter markets to only keep match-specific markets"""
    if not markets:
        return []
    
    filtered = []
    excluded_count = 0
    excluded_markets = []
    
    for market in markets:
        if is_match_specific_market(market):
            filtered.append(market)
        else:
            excluded_count += 1
            excluded_markets.append(market.get("marketName", "N/A"))
    
    if excluded_count > 0:
        logger.debug(f"Filtered out {excluded_count} season-related market(s), kept {len(filtered)} match-specific market(s)")
        if excluded_markets:
            logger.debug(f"Excluded markets (sample): {', '.join(excluded_markets[:5])}{'...' if len(excluded_markets) > 5 else ''}")
    
    return filtered


# ============================================================================
# HELPER FUNCTIONS FOR DATA WEIGHT CALCULATION
# ============================================================================

def calculate_market_projection_weight(market_projection: List[str]) -> int:
    """Calculate weight for listMarketCatalogue based on MarketProjection"""
    weight = 0
    for projection in market_projection:
        if projection == "MARKET_DESCRIPTION":
            weight += 1
        elif projection == "RUNNER_METADATA":
            weight += 1
    return weight


def calculate_price_projection_weight(price_projection: Dict[str, Any]) -> int:
    """Calculate weight for listMarketBook based on PriceProjection"""
    if not price_projection or "priceData" not in price_projection:
        return 2
    
    price_data = price_projection.get("priceData", [])
    
    has_ex_best_offers = "EX_BEST_OFFERS" in price_data
    has_ex_traded = "EX_TRADED" in price_data
    has_ex_all_offers = "EX_ALL_OFFERS" in price_data
    
    if has_ex_all_offers and has_ex_traded:
        return 32
    elif has_ex_best_offers and has_ex_traded:
        return 20
    
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
    
    return weight if weight > 0 else 2


# ============================================================================
# STREAM API FUNCTION
# ============================================================================

def get_live_markets_from_stream_api(app_key: str, session_token: str, api_endpoint: str, 
                                     market_type_codes: List[str] = None,
                                     collect_duration: float = 5.0) -> List[Dict[str, Any]]:
    """
    Get live markets from Betfair Stream API (same as test_betfair_stream_realtime.py).
    Only returns markets that are actually OPEN and inPlay (verified by Stream API).
    """
    if not market_type_codes:
        market_type_codes = ["OVER_UNDER_05", "OVER_UNDER_15", "OVER_UNDER_25", "OVER_UNDER_35", "OVER_UNDER_45"]
    
    # Step 1: Get market IDs from REST API
    url = f"{api_endpoint}/listMarketCatalogue/"
    headers = {
        "X-Application": app_key,
        "X-Authentication": session_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "filter": {
            "eventTypeIds": [1],  # Football
            "marketTypeCodes": market_type_codes,
            "inPlay": True
        },
        "maxResults": 200,
        "marketProjection": ["MARKET_DESCRIPTION", "COMPETITION", "EVENT"]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.warning(f"Failed to get markets from REST API: {response.status_code}")
            return []
        
        markets = response.json()
        if not isinstance(markets, list):
            return []
        
        market_ids = [str(m.get("marketId")) for m in markets if m.get("marketId")]
        if not market_ids:
            return []
        
        market_data_map = {}
        for m in markets:
            market_id = m.get("marketId")
            if market_id:
                market_data_map[str(market_id)] = m
        
        logger.debug(f"Got {len(market_ids)} market IDs from REST API, connecting to Stream API...")
        
    except Exception as e:
        logger.warning(f"Error getting markets from REST API: {str(e)}")
        return []
    
    # Step 2: Connect to Stream API and subscribe
    sock = None
    ssl_sock = None
    live_markets = {}
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect(("stream-api.betfair.com", 443))
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        ssl_sock = context.wrap_socket(sock, server_hostname="stream-api.betfair.com")
        
        # Authenticate
        auth_msg = {
            "op": "authentication",
            "appKey": app_key,
            "session": session_token
        }
        payload_auth = json.dumps(auth_msg) + "\r\n"
        ssl_sock.send(payload_auth.encode('utf-8'))
        
        # Receive auth response
        ssl_sock.settimeout(10)
        message_buffer = b""
        auth_success = False
        
        for _ in range(3):
            try:
                data = ssl_sock.recv(4096)
                if not data:
                    break
                message_buffer += data
                
                while b"\r\n" in message_buffer:
                    parts = message_buffer.split(b"\r\n", 1)
                    complete_message = parts[0].decode('utf-8', errors='ignore')
                    message_buffer = parts[1] if len(parts) > 1 else b""
                    
                    if complete_message.strip():
                        try:
                            msg = json.loads(complete_message.strip())
                            op = msg.get("op")
                            
                            if op == "connection":
                                logger.debug("Received connection message from Stream API")
                                continue
                            elif op == "status":
                                status_code = msg.get("statusCode")
                                if status_code == "SUCCESS":
                                    auth_success = True
                                    logger.debug("Stream API authentication successful")
                                    break
                                else:
                                    error_msg = msg.get("error", "Unknown error")
                                    logger.warning(f"Stream API authentication failed: {status_code} - {error_msg}")
                                    return []
                        except json.JSONDecodeError:
                            continue
                
                if auth_success:
                    break
            except socket.timeout:
                if message_buffer:
                    try:
                        msg = json.loads(message_buffer.decode('utf-8', errors='ignore').strip())
                        if msg.get("op") == "status" and msg.get("statusCode") == "SUCCESS":
                            auth_success = True
                            break
                    except:
                        pass
                break
        
        if not auth_success:
            logger.warning("Stream API authentication: No SUCCESS status received")
            return []
        
        # Subscribe to markets (max 200 per subscription)
        if len(market_ids) > 200:
            market_ids = market_ids[:200]
        
        sub_msg = {
            "op": "marketSubscription",
            "id": 1,
            "marketFilter": {
                "marketIds": market_ids
            },
            "marketDataFilter": {
                "fields": ["EX_MARKET_DEF", "EX_ALL_OFFERS"]
            },
            "heartbeatMs": 5000,
            "conflateMs": 0
        }
        payload_sub = json.dumps(sub_msg) + "\r\n"
        ssl_sock.send(payload_sub.encode('utf-8'))
        
        logger.debug(f"Subscribed to {len(market_ids)} markets, collecting messages for {collect_duration}s...")
        
        # Step 3: Collect messages
        message_buffer = b""
        start_time = time.time()
        
        while time.time() - start_time < collect_duration:
            try:
                ssl_sock.settimeout(1.0)
                data = ssl_sock.recv(4096)
                if not data:
                    break
                
                message_buffer += data
                
                while b"\r\n" in message_buffer:
                    parts = message_buffer.split(b"\r\n", 1)
                    complete_message = parts[0].decode('utf-8', errors='ignore')
                    message_buffer = parts[1] if len(parts) > 1 else b""
                    
                    if complete_message.strip():
                        try:
                            msg = json.loads(complete_message.strip())
                            op = msg.get("op")
                            
                            if op == "mcm":  # MarketChangeMessage
                                mc = msg.get("mc") or []
                                for market in mc:
                                    mid = market.get("id")
                                    md = market.get("marketDefinition") or {}
                                    inplay = md.get("inPlay", False)
                                    status = md.get("status")
                                    
                                    if inplay and status and status.upper() == "OPEN":
                                        if mid and mid in market_data_map:
                                            live_markets[mid] = market_data_map[mid]
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.debug(f"Error processing Stream API message: {str(e)}")
                            continue
            except socket.timeout:
                continue
            except Exception as e:
                logger.debug(f"Error receiving from Stream API: {str(e)}")
                break
        
        logger.debug(f"Collected {len(live_markets)} live markets from Stream API")
        
    except Exception as e:
        logger.warning(f"Error connecting to Stream API: {str(e)}")
    finally:
        if ssl_sock:
            try:
                ssl_sock.close()
            except:
                pass
        if sock:
            try:
                sock.close()
            except:
                pass
    
    return list(live_markets.values())


# ============================================================================
# MARKET SERVICE CLASS
# ============================================================================

class MarketService:
    """Handles Betfair market data retrieval"""
    
    def __init__(self, app_key: str, session_token: str, api_endpoint: str, 
                 max_data_weight_points: int = 190):
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
        """List all available event types (sports)"""
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
        """List competitions for given event types"""
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
            
            return competitions
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error listing competitions: {str(e)}")
            return []
    
    def list_market_catalogue(self, event_type_ids: List[int], 
                             competition_ids: List[int] = None,
                             in_play_only: bool = True,
                             market_type_codes: List[str] = None,
                             max_results: int = 1000) -> List[Dict[str, Any]]:
        """List market catalogue with filters"""
        try:
            url = f"{self.api_endpoint}/listMarketCatalogue/"
            
            base_filter = {
                "eventTypeIds": event_type_ids,
            }
            
            if in_play_only:
                base_filter["inPlay"] = True
            
            if market_type_codes:
                base_filter["marketTypeCodes"] = market_type_codes
            
            market_projection = [
                "MARKET_DESCRIPTION",
                "COMPETITION",
                "EVENT"
            ]
            
            projection_weight = calculate_market_projection_weight(market_projection)
            max_markets_by_weight = self.max_data_weight_points // projection_weight if projection_weight > 0 else 100
            max_results_per_request = min(200, max_markets_by_weight)
            
            total_weight = projection_weight * max_results_per_request
            if total_weight > self.max_data_weight_points:
                max_results_per_request = self.max_data_weight_points // projection_weight
                logger.warning(f"Adjusted max_results_per_request to {max_results_per_request} to stay within data weight limit")
            
            all_markets = []
            
            if competition_ids and len(competition_ids) > 0:
                competition_batch_size = 10
                remaining_competitions = competition_ids.copy()
                
                while remaining_competitions:
                    batch_competition_ids = remaining_competitions[:competition_batch_size]
                    remaining_competitions = remaining_competitions[competition_batch_size:]
                    
                    filter_dict = base_filter.copy()
                    filter_dict["competitionIds"] = batch_competition_ids
                    
                    payload = {
                        "filter": filter_dict,
                        "maxResults": max_results_per_request,
                        "marketProjection": market_projection
                    }
                    
                    response = requests.post(url, json=payload, headers=self.headers, timeout=30)
                    response.raise_for_status()
                    
                    result = response.json()
                    batch_markets = result if isinstance(result, list) else []
                    all_markets.extend(batch_markets)
                    
                    if len(batch_markets) >= max_results_per_request:
                        for comp_id in batch_competition_ids:
                            filter_dict_individual = base_filter.copy()
                            filter_dict_individual["competitionIds"] = [comp_id]
                            
                            payload_individual = {
                                "filter": filter_dict_individual,
                                "maxResults": max_results_per_request,
                                "marketProjection": market_projection
                            }
                            
                            try:
                                response_individual = requests.post(url, json=payload_individual, headers=self.headers, timeout=30)
                                response_individual.raise_for_status()
                                
                                result_individual = response_individual.json()
                                individual_markets = result_individual if isinstance(result_individual, list) else []
                                all_markets.extend(individual_markets)
                            except Exception:
                                continue
            
            else:
                filter_dict = base_filter.copy()
                
                payload = {
                    "filter": filter_dict,
                    "maxResults": max_results_per_request,
                    "marketProjection": market_projection
                }
                
                response = requests.post(url, json=payload, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                markets = result if isinstance(result, list) else []
                all_markets.extend(markets)
            
            seen_market_ids = set()
            unique_markets = []
            for market in all_markets:
                market_id = market.get("marketId")
                if market_id and market_id not in seen_market_ids:
                    seen_market_ids.add(market_id)
                    unique_markets.append(market)
            
            logger.debug(f"Retrieved {len(unique_markets)} unique markets from catalogue "
                        f"(from {len(all_markets)} total, {len(all_markets) - len(unique_markets)} duplicates removed)")
            
            return unique_markets
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed - session token may have expired")
                raise
            else:
                logger.error(f"HTTP error listing market catalogue: {e.response.status_code} - {e.response.text}")
                raise
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            logger.debug(f"Network error in list_market_catalogue: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing market catalogue: {str(e)}")
            return []
    
    def list_market_book(self, market_ids: List[str], 
                        price_projection: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get detailed market book data including prices"""
        try:
            url = f"{self.api_endpoint}/listMarketBook/"
            
            if price_projection is None:
                price_projection = {
                    "priceData": ["EX_BEST_OFFERS", "SP_AVAILABLE", "SP_TRADED"]
                }
            
            projection_weight = calculate_price_projection_weight(price_projection)
            max_markets_per_request = self.max_data_weight_points // projection_weight if projection_weight > 0 else 1
            
            all_market_books = []
            for i in range(0, len(market_ids), max_markets_per_request):
                batch_market_ids = market_ids[i:i + max_markets_per_request]
                
                total_weight = projection_weight * len(batch_market_ids)
                if total_weight > self.max_data_weight_points:
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
        """Get account balance and funds information"""
        try:
            account_endpoint = getattr(self, 'account_endpoint', "https://api.betfair.com/exchange/account/rest/v1.0")
            url = f"{account_endpoint}/getAccountFunds/"
            
            account_headers = {
                'X-Application': self.app_key,
                'X-Authentication': self.session_token,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json={}, headers=account_headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Could not retrieve account funds: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.warning(f"Error getting account funds: {str(e)}")
            return None


# ============================================================================
# BETTING SERVICE CLASS
# ============================================================================

class BettingService:
    """Handles bet placement on Betfair Exchange"""
    
    def __init__(self, app_key: str, session_token: str, api_endpoint: str):
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
        """Place orders on Betfair Exchange"""
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
        """Place a lay bet on a selection"""
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

