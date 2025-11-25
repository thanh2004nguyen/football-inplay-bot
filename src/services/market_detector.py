"""
Market Detector Service
Handles Betfair market detection and filtering
"""
import logging
from typing import Dict, Any, List, Set, Optional
from services.betfair import get_live_markets_from_stream_api

logger = logging.getLogger("BetfairBot")


class MarketDetector:
    """Service for detecting and filtering Betfair markets"""
    
    def __init__(self, market_service, betfair_config: Dict[str, Any], competition_ids: Set[int]):
        """
        Initialize Market Detector
        
        Args:
            market_service: MarketService instance
            betfair_config: Betfair configuration
            competition_ids: Set of competition IDs from Excel
        """
        self.market_service = market_service
        self.betfair_config = betfair_config
        self.competition_ids = competition_ids
        self.cached_markets: List[Dict[str, Any]] = []
        self.market_type_codes = ["OVER_UNDER_05", "OVER_UNDER_15", "OVER_UNDER_25", 
                                   "OVER_UNDER_35", "OVER_UNDER_45"]
    
    def detect_markets(self) -> Dict[str, Dict[str, Any]]:
        """
        Detect and filter Betfair markets
        
        Returns:
            Dictionary of unique events: {event_id: {event, competition, markets}}
        """
        # Get live markets from Stream API
        markets = get_live_markets_from_stream_api(
            app_key=self.betfair_config["app_key"],
            session_token=self.market_service.session_token,
            api_endpoint=self.market_service.api_endpoint,
            market_type_codes=self.market_type_codes,
            collect_duration=5.0  # Collect messages for 5 seconds
        )
        
        # Cache markets if we got valid data, otherwise use cached data
        if markets and len(markets) > 0:
            self.cached_markets = markets
        elif not markets or len(markets) == 0:
            # Use cached data if available
            if self.cached_markets:
                logger.debug(f"Stream API returned 0 markets, using cached {len(self.cached_markets)} markets from previous iteration")
                markets = self.cached_markets
        
        # Filter by competition_ids from Excel
        unique_events: Dict[str, Dict[str, Any]] = {}
        if markets:
            logger.debug(f"Betfair Stream API returned {len(markets)} markets before Excel filtering")
            for market in markets:
                event = market.get("event", {})
                event_id = event.get("id", "")
                competition = market.get("competition", {})
                competition_id = competition.get("id")
                competition_name = competition.get("name", "N/A")
                event_name = event.get("name", "N/A")
                
                # Filter by competition_ids from Excel
                if self.competition_ids:
                    if not competition_id:
                        # Market has no competition_id - skip it
                        continue
                    
                    # Convert competition_id to int for comparison
                    try:
                        comp_id_int = int(competition_id)
                    except (ValueError, TypeError):
                        continue
                    
                    # Convert competition_ids to ints for comparison
                    competition_ids_int = set()
                    for cid in self.competition_ids:
                        try:
                            if isinstance(cid, int):
                                competition_ids_int.add(cid)
                            elif isinstance(cid, str):
                                cid_clean = str(cid).strip()
                                if cid_clean:
                                    competition_ids_int.add(int(cid_clean))
                            else:
                                competition_ids_int.add(int(cid))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"⚠️ Failed to convert competition_id '{cid}' (type: {type(cid)}) to int: {e}")
                            continue
                    
                    # Check if competition_id is in Excel competitions list
                    if comp_id_int not in competition_ids_int:
                        # Log first few mismatches for debugging
                        if len(competition_ids_int) <= 20:
                            logger.debug(f"❌ Competition ID {comp_id_int} NOT in Excel filter {sorted(competition_ids_int)} - skipping market '{event_name}'")
                        continue  # Skip this market - not in Excel competitions
                    else:
                        logger.debug(f"✅ Competition ID {comp_id_int} MATCHED in Excel filter for '{event_name}'")
                
                if event_id and event_id not in unique_events:
                    # Ensure competition has ID before storing
                    comp_id = competition_id
                    
                    # Make sure competition object has the ID field
                    if competition and isinstance(competition, dict):
                        # Ensure competition dict has "id" field
                        if "id" not in competition or competition.get("id") != competition_id:
                            # Create a new competition dict with ID
                            competition = {
                                "id": competition_id,
                                "name": competition.get("name", competition_name)
                            }
                    elif not competition:
                        # Create competition object if it doesn't exist
                        competition = {
                            "id": competition_id,
                            "name": competition_name
                        }
                    
                    # Make a copy of competition to avoid reference issues
                    competition_copy = competition.copy() if isinstance(competition, dict) else competition
                    unique_events[event_id] = {
                        "event": event,
                        "competition": competition_copy,
                        "markets": []
                    }
                    # Debug: log competition ID when storing
                    logger.debug(f"✅ Stored event {event_id} ({event_name}) with competition ID: {comp_id}, name: {competition.get('name') if isinstance(competition, dict) else competition_name}")
                if event_id:
                    unique_events[event_id]["markets"].append(market)
        
        return unique_events
    
    def log_markets(self, unique_events: Dict[str, Dict[str, Any]]):
        """
        Log detected markets
        
        Args:
            unique_events: Dictionary of unique events
        """
        # Log Betfair events clearly - show ALL matches EVERY iteration
        # Always log, even if 0 matches
        betfair_msg = f"Betfair: {len(unique_events)} available matches after comparing with Excel."
        logger.info(betfair_msg)
        
        # Show ALL events (not just first 5) - log every iteration
        if unique_events:
            event_list = list(unique_events.values())
            for i, event_data in enumerate(event_list, 1):
                event = event_data["event"]
                event_name = event.get("name", "N/A")
                competition_obj = event_data.get("competition", {})
                competition_id = competition_obj.get("id", "") if isinstance(competition_obj, dict) else ""
                competition_name = competition_obj.get("name", "N/A") if isinstance(competition_obj, dict) else "N/A"
                market_count = len(event_data["markets"])
                
                # Format: ID_Name (same format as Live API)
                if competition_id:
                    competition_display = f"{competition_id}_{competition_name}"
                else:
                    competition_display = competition_name
                
                event_msg = f"  [{i}] {event_name} ({competition_display}) - {market_count} market(s)"
                logger.info(event_msg)

