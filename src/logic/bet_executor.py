"""
Bet Executor Module
Main logic for executing lay bets on Over X.5 markets
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from betfair.market_service import MarketService
from betfair.betting_service import BettingService
from betfair.price_ladder import (
    get_increment_for_price, 
    add_ticks_to_price, 
    calculate_ticks_between,
    round_to_valid_price
)
from config.competition_mapper import normalize_text

logger = logging.getLogger("BetfairBot")


# Map target_over value to market type code
TARGET_OVER_TO_MARKET_TYPE = {
    0.5: "OVER_UNDER_05",
    1.5: "OVER_UNDER_15",
    2.5: "OVER_UNDER_25",
    3.5: "OVER_UNDER_35",
    4.5: "OVER_UNDER_45",
}


def find_over_market(market_service: MarketService, event_id: str, 
                    target_over: float) -> Optional[Dict[str, Any]]:
    """
    Find Over X.5 market for an event
    
    Args:
        market_service: MarketService instance
        event_id: Betfair event ID
        target_over: Target Over value (e.g., 2.5)
    
    Returns:
        {
            "marketId": "1.xxxxx",
            "selectionId": 12345,
            "marketName": "Over/Under 2.5 Goals",
            "runnerName": "Over 2.5 Goals"
        } or None if not found
    """
    try:
        # Get market type code for target_over
        market_type_code = TARGET_OVER_TO_MARKET_TYPE.get(target_over)
        if not market_type_code:
            logger.warning(f"No market type code for target_over {target_over}")
            return None
        
        # Get markets for this event
        markets = market_service.list_market_catalogue(
            event_type_ids=[1],  # Football
            competition_ids=[],
            in_play_only=True,
            market_type_codes=[market_type_code],
            max_results=100
        )
        
        # Find market for this specific event
        for market in markets:
            market_event = market.get("event", {})
            if market_event.get("id") == event_id:
                market_name = market.get("marketName", "")
                
                # Check if market name contains Over/Under
                if "over" in market_name.lower() and "under" in market_name.lower():
                    # Find runner "Over X.5"
                    runners = market.get("runners", [])
                    for runner in runners:
                        runner_name = runner.get("runnerName", "")
                        # Check if runner name contains "Over" and the target number
                        if "over" in runner_name.lower():
                            # Extract number from runner name (e.g., "Over 2.5 Goals" -> 2.5)
                            import re
                            numbers = re.findall(r'\d+\.?\d*', runner_name)
                            for num_str in numbers:
                                try:
                                    num = float(num_str)
                                    if abs(num - target_over) < 0.1:  # Allow small difference
                                        return {
                                            "marketId": market.get("marketId"),
                                            "selectionId": runner.get("selectionId"),
                                            "marketName": market_name,
                                            "runnerName": runner_name
                                        }
                                except ValueError:
                                    continue
                    
                    # If exact match not found, try to find any "Over" runner
                    for runner in runners:
                        runner_name = runner.get("runnerName", "")
                        if "over" in runner_name.lower() and str(int(target_over)) in runner_name:
                            return {
                                "marketId": market.get("marketId"),
                                "selectionId": runner.get("selectionId"),
                                "marketName": market_name,
                                "runnerName": runner_name
                            }
        
        logger.debug(f"Over {target_over} market not found for event {event_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error finding over market: {str(e)}")
        return None


def find_under_market(market_service: MarketService, event_id: str, 
                     target_over: float) -> Optional[Dict[str, Any]]:
    """
    Find Under X.5 market for an event (same market as Over X.5, different selection)
    
    Args:
        market_service: MarketService instance
        event_id: Betfair event ID
        target_over: Target Over value (e.g., 2.5) - same market, Under X.5 selection
    
    Returns:
        {
            "marketId": "1.xxxxx",
            "selectionId": 12346,
            "marketName": "Over/Under 2.5 Goals",
            "runnerName": "Under 2.5 Goals"
        } or None if not found
    """
    try:
        # Get market type code for target_over (same as Over X.5)
        market_type_code = TARGET_OVER_TO_MARKET_TYPE.get(target_over)
        if not market_type_code:
            logger.warning(f"No market type code for target_over {target_over}")
            return None
        
        # Get markets for this event
        markets = market_service.list_market_catalogue(
            event_type_ids=[1],  # Football
            competition_ids=[],
            in_play_only=True,
            market_type_codes=[market_type_code],
            max_results=100
        )
        
        # Find market for this specific event
        for market in markets:
            market_event = market.get("event", {})
            if market_event.get("id") == event_id:
                market_name = market.get("marketName", "")
                
                # Check if market name contains Over/Under
                if "over" in market_name.lower() and "under" in market_name.lower():
                    # Find runner "Under X.5"
                    runners = market.get("runners", [])
                    for runner in runners:
                        runner_name = runner.get("runnerName", "")
                        # Check if runner name contains "Under" and the target number
                        if "under" in runner_name.lower():
                            # Extract number from runner name (e.g., "Under 2.5 Goals" -> 2.5)
                            import re
                            numbers = re.findall(r'\d+\.?\d*', runner_name)
                            for num_str in numbers:
                                try:
                                    num = float(num_str)
                                    if abs(num - target_over) < 0.1:  # Allow small difference
                                        return {
                                            "marketId": market.get("marketId"),
                                            "selectionId": runner.get("selectionId"),
                                            "marketName": market_name,
                                            "runnerName": runner_name
                                        }
                                except ValueError:
                                    continue
                    
                    # If exact match not found, try to find any "Under" runner
                    for runner in runners:
                        runner_name = runner.get("runnerName", "")
                        if "under" in runner_name.lower() and str(int(target_over)) in runner_name:
                            return {
                                "marketId": market.get("marketId"),
                                "selectionId": runner.get("selectionId"),
                                "marketName": market_name,
                                "runnerName": runner_name
                            }
        
        logger.debug(f"Under {target_over} market not found for event {event_id}")
        return None
        
    except Exception as e:
        logger.error(f"Error finding under market: {str(e)}")
        return None


def get_market_book_data(market_service: MarketService, market_id: str, 
                        selection_id: int) -> Optional[Dict[str, Any]]:
    """
    Get market book data for a specific selection
    
    Args:
        market_service: MarketService instance
        market_id: Market ID
        selection_id: Selection ID
    
    Returns:
        {
            "bestBackPrice": 2.0,
            "bestLayPrice": 2.1,
            "totalMatched": 10000.0,
            "totalAvailable": 200.0,
            "status": "OPEN"
        } or None if error
    """
    try:
        market_books = market_service.list_market_book(
            market_ids=[market_id],
            price_projection={
                "priceData": ["EX_BEST_OFFERS", "EX_TRADED"]
            }
        )
        
        if not market_books:
            logger.warning(f"No market book data for market {market_id}")
            return None
        
        market_book = market_books[0]
        
        # Check market status
        status = market_book.get("status", "")
        if status != "OPEN":
            logger.warning(f"Market {market_id} is not OPEN (status: {status})")
            return None
        
        # Find runner
        runners = market_book.get("runners", [])
        runner = None
        for r in runners:
            if r.get("selectionId") == selection_id:
                runner = r
                break
        
        if not runner:
            logger.warning(f"Selection {selection_id} not found in market {market_id}")
            return None
        
        # Get prices (focus on LAY side as per requirements)
        ex = runner.get("ex", {})
        available_to_back = ex.get("availableToBack", [])
        available_to_lay = ex.get("availableToLay", [])
        
        best_back_price = None
        best_lay_price = None
        lay_size = 0.0  # Size available at best lay price
        total_lay_size = 0.0  # Total size available on lay side (for book percentage)
        
        if available_to_back:
            best_back_price = available_to_back[0].get("price")
        if available_to_lay:
            best_lay_price = available_to_lay[0].get("price")
            lay_size = available_to_lay[0].get("size", 0.0)
            # Calculate total lay size (sum of all available lay sizes)
            total_lay_size = sum(layer.get("size", 0.0) for layer in available_to_lay)
        
        if best_back_price is None or best_lay_price is None:
            logger.warning(f"No prices available for selection {selection_id}")
            return None
        
        # Get runner-specific matched data (for Under X.5 selection only)
        # Note: Per client requirements, we don't use matched percentage
        # But we need runner data for stability checks
        runner_total_matched = runner.get("totalMatched", 0.0)
        
        return {
            "bestBackPrice": best_back_price,
            "bestLayPrice": best_lay_price,
            "laySize": lay_size,  # Size available at best lay price
            "totalLaySize": total_lay_size,  # Total size on lay side
            "runnerTotalMatched": runner_total_matched,  # Matched for this runner (not used for percentage check)
            "status": status
        }
        
    except Exception as e:
        logger.error(f"Error getting market book data: {str(e)}")
        return None


def check_market_conditions(market_data: Dict[str, Any], 
                           min_odds: float,
                           max_spread_ticks: int,
                           ladder_type: str = "CLASSIC") -> Tuple[bool, str]:
    """
    Check if market conditions are met for bet placement
    
    Requirements (per client - Andrea):
    - Market must be stable (mature market with balanced prices)
    - Odds check must be performed on best back price of Under X.5
    - Odds check: Under X.5 best back > min_odds (only check minimum, no maximum)
    - Lay bet must be placed on Over X.5
    - Spread check: Over X.5 best lay - Over X.5 best back (in same market)
    - Book percentage around 100% on lay side (market is mature/balanced)
    - Spread never exceeds max_spread_ticks
    - NO matched percentage check (client explicitly doesn't want this)
    
    Args:
        market_data: Market book data containing:
            - bestBackPrice: Over X.5 best back (for spread calculation)
            - bestLayPrice: Over X.5 best lay (for spread calculation)
            - underBestBack: Under X.5 best back (for odds check)
            - laySize: Over X.5 lay size
            - totalLaySize: Over X.5 total lay size
        min_odds: Minimum odds threshold (from Excel, per competition + result)
        max_spread_ticks: Maximum allowed spread in ticks
        ladder_type: Price ladder type ("CLASSIC" or "FINEST")
    
    Returns:
        (is_valid, reason)
    """
    # Get Over X.5 prices (for spread calculation)
    over_best_back = market_data.get("bestBackPrice")  # Over X.5 best back
    over_best_lay = market_data.get("bestLayPrice")  # Over X.5 best lay
    lay_size = market_data.get("laySize", 0.0)  # Size at best lay price (Over X.5)
    total_lay_size = market_data.get("totalLaySize", 0.0)  # Total size on lay side (Over X.5)
    
    # Get Under X.5 best back (for odds check)
    under_best_back = market_data.get("underBestBack")
    
    # Check 1: Odds threshold (check best back price of Under X.5 as per client requirement)
    # Per client requirement: At minute 75', Odds only needs to be greater than Min_Odds
    # Correct: Odds_75 > Min_Odds
    # Wrong: Min_Odds < Odds_75 < Quota_Max_Lay_Over (NOT used - no maximum check)
    # Each competition + result has its own Min_Odds from Excel
    if under_best_back is None:
        return False, "Under X.5 best back price not available"
    if under_best_back <= min_odds:
        return False, f"Under X.5 best back price {under_best_back} must be higher than {min_odds}"
    
    # Check 2: Spread ≤ max_spread_ticks (critical requirement)
    # Spread is calculated from Over X.5 best back to Over X.5 best lay (same market)
    if over_best_back is None or over_best_lay is None:
        return False, "Over X.5 prices not available for spread calculation"
    
    spread = over_best_lay - over_best_back
    ticks = calculate_ticks_between(over_best_back, over_best_lay, ladder_type)
    
    if ticks > max_spread_ticks:
        return False, f"Spread {spread} ({ticks} ticks) exceeds maximum {max_spread_ticks} ticks"
    
    # Check 3: Lay side has liquidity (book percentage check)
    # "Book percentage around 100%" means lay side has liquidity available
    # This indicates market is mature with balanced prices on lay side
    # We only check that liquidity exists (no size threshold as per client requirements)
    if total_lay_size <= 0:
        return False, "No liquidity available on lay side"
    
    # Check 4: Best lay price has sufficient size (immediate liquidity at best price)
    if lay_size <= 0:
        return False, "No liquidity available at best lay price"
    
    return True, f"Market stable: spread {ticks} ticks"


def calculate_lay_price(best_lay_price: float, ticks_offset: int = 2,
                       ladder_type: str = "CLASSIC") -> float:
    """
    Calculate lay price by adding ticks to best lay price
    
    Args:
        best_lay_price: Best lay price
        ticks_offset: Number of ticks to add (default: 2)
        ladder_type: Price ladder type ("CLASSIC" or "FINEST")
    
    Returns:
        Lay price
    """
    lay_price = add_ticks_to_price(best_lay_price, ticks_offset, ladder_type)
    return round_to_valid_price(lay_price, ladder_type)


def get_stake_from_excel(competition_name: str, score: str, excel_path: str, 
                        betfair_competition_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get stake percentage and Min_Odds from Excel file based on Competition and Result
    Supports both old format (Competition column) and new format (Competition-Live column)
    
    When Competition-Live matches multiple rows (e.g., "Serie A" for both Italy and Brazil),
    uses Competition-Betfair to disambiguate if provided.
    
    Args:
        competition_name: Competition name from Live Score API (will be matched with Competition-Live or Competition)
        score: Current score at minute 75 (format: "1-1", "0-0", "1-2")
        excel_path: Path to Excel file (Competitions_Results_Odds_Stake.xlsx)
        betfair_competition_name: Optional Betfair competition name (for disambiguation when Competition-Live is ambiguous)
    
    Returns:
        Dictionary with 'stake' and 'min_odds' if found, None if not found
        Format: {"stake": 5.0, "min_odds": 1.5}
    """
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        # Check required columns
        has_competition_live = 'Competition-Live' in df.columns
        has_competition_betfair = 'Competition-Betfair' in df.columns
        has_competition_old = 'Competition' in df.columns
        
        if not has_competition_live and not has_competition_old:
            logger.error(f"Neither 'Competition-Live' nor 'Competition' column found in Excel file. Available: {df.columns.tolist()}")
            return None
        
        if 'Result' not in df.columns or 'Stake' not in df.columns:
            logger.error(f"Required columns 'Result' or 'Stake' not found in Excel file. Available: {df.columns.tolist()}")
            return None
        
        # Check if Min_Odds column exists (optional, will use default if not found)
        has_min_odds = 'Min_Odds' in df.columns or 'Min Odds' in df.columns
        min_odds_column = 'Min_Odds' if 'Min_Odds' in df.columns else ('Min Odds' if 'Min Odds' in df.columns else None)
        
        # Normalize competition name for matching
        # Support format: "ID_Name" (e.g., "4_Serie A") or just "Name" (e.g., "Serie A")
        normalized_competition = normalize_text(competition_name)
        
        # Extract ID and name if format is "ID_Name"
        competition_id = None
        competition_name_only = competition_name
        if "_" in competition_name:
            parts = competition_name.split("_", 1)
            try:
                competition_id = parts[0].strip()
                competition_name_only = parts[1].strip()
            except:
                pass
        
        # Normalize score format (ensure format is "X-Y")
        score_normalized = score.strip().replace(":", "-")
        
        # Find matching row - Priority: Competition-Live, then Competition
        matches = pd.DataFrame()
        
        if has_competition_live:
            # Try matching with Competition-Live column (new format)
            # Support both "ID_Name" format and "Name" format
            def match_competition_live(cell_value):
                if pd.isna(cell_value):
                    return False
                cell_str = str(cell_value).strip()
                
                # Exact match
                if cell_str == competition_name:
                    return True
                
                # Match with normalized text
                if normalize_text(cell_str) == normalized_competition:
                    return True
                
                # If competition_name is "ID_Name" format, also try matching just the name part
                if competition_id and competition_name_only:
                    # Match with "ID_Name" format in Excel
                    if cell_str == f"{competition_id}_{competition_name_only}":
                        return True
                    # Match with just name part
                    if normalize_text(cell_str) == normalize_text(competition_name_only):
                        return True
                
                # If Excel has "ID_Name" format, extract and match name part
                if "_" in cell_str:
                    try:
                        excel_parts = cell_str.split("_", 1)
                        excel_name = excel_parts[1].strip()
                        if normalize_text(excel_name) == normalize_text(competition_name_only):
                            return True
                    except:
                        pass
                
                return False
            
            matches = df[df['Competition-Live'].apply(match_competition_live)]
        
        if matches.empty and has_competition_old:
            # Fallback to Competition column (old format)
            matches = df[
                (df['Competition'].astype(str).str.strip() == competition_name) |
                (df['Competition'].astype(str).str.strip().apply(lambda x: normalize_text(x) == normalized_competition))
            ]
        
        if matches.empty:
            logger.warning(f"No competition match found for: {competition_name} (normalized: {normalized_competition})")
            logger.debug(f"Available competitions in Excel: {df['Competition-Live'].unique().tolist() if has_competition_live else df['Competition'].unique().tolist()}")
            return None
        
        logger.debug(f"Found {len(matches)} competition match(es) for '{competition_name}'. Available Results: {matches['Result'].astype(str).str.strip().unique().tolist()}")
        
        # Filter by score
        score_matches = matches[matches['Result'].astype(str).str.strip() == score_normalized]
        
        if score_matches.empty:
            logger.warning(f"Score {score_normalized} not found in Excel for competition {competition_name}")
            logger.debug(f"Available Results for this competition: {matches['Result'].astype(str).str.strip().unique().tolist()}")
            return None
        
        # If multiple matches and Competition-Betfair is available, use it to disambiguate
        if len(score_matches) > 1 and has_competition_betfair and betfair_competition_name:
            # Support format: "ID_Name" (e.g., "81_Italian Serie A") or just "Name" (e.g., "Italian Serie A")
            betfair_normalized = normalize_text(betfair_competition_name)
            
            # Extract ID and name if format is "ID_Name"
            betfair_competition_id = None
            betfair_competition_name_only = betfair_competition_name
            if "_" in betfair_competition_name:
                parts = betfair_competition_name.split("_", 1)
                try:
                    betfair_competition_id = parts[0].strip()
                    betfair_competition_name_only = parts[1].strip()
                except:
                    pass
            
            def match_competition_betfair(cell_value):
                if pd.isna(cell_value):
                    return False
                cell_str = str(cell_value).strip()
                
                # Exact match
                if cell_str == betfair_competition_name:
                    return True
                
                # Match with normalized text
                if normalize_text(cell_str) == betfair_normalized:
                    return True
                
                # If betfair_competition_name is "ID_Name" format, also try matching just the name part
                if betfair_competition_id and betfair_competition_name_only:
                    # Match with "ID_Name" format in Excel
                    if cell_str == f"{betfair_competition_id}_{betfair_competition_name_only}":
                        return True
                    # Match with just name part
                    if normalize_text(cell_str) == normalize_text(betfair_competition_name_only):
                        return True
                
                # If Excel has "ID_Name" format, extract and match name part
                if "_" in cell_str:
                    try:
                        excel_parts = cell_str.split("_", 1)
                        excel_name = excel_parts[1].strip()
                        if normalize_text(excel_name) == normalize_text(betfair_competition_name_only):
                            return True
                    except:
                        pass
                
                return False
            
            betfair_matches = score_matches[score_matches['Competition-Betfair'].apply(match_competition_betfair)]
            
            if not betfair_matches.empty:
                score_matches = betfair_matches
                logger.debug(f"Disambiguated using Competition-Betfair: '{betfair_competition_name}' -> {len(score_matches)} match(es)")
            else:
                logger.warning(f"Multiple matches found for '{competition_name}' but Competition-Betfair '{betfair_competition_name}' did not match. Using first match.")
        
        # Get stake value and Min_Odds (first match if multiple)
        matched_row = score_matches.iloc[0]
        stake_value = matched_row['Stake']
        
        # Convert to float if needed
        if pd.isna(stake_value):
            logger.warning(f"Stake value is NaN for {competition_name} - {score_normalized}")
            return None
        
        stake_percent = float(stake_value)
        
        # Get Min_Odds from Excel (each competition + result has its own Min_Odds)
        min_odds = None
        if min_odds_column and min_odds_column in matched_row:
            min_odds_value = matched_row[min_odds_column]
            if not pd.isna(min_odds_value):
                try:
                    min_odds = float(min_odds_value)
                except (ValueError, TypeError):
                    logger.warning(f"Min_Odds value is invalid for {competition_name} - {score_normalized}, using default")
        
        # If Min_Odds not found in Excel, use default from config (fallback)
        if min_odds is None:
            # This will be handled by caller, but we log it
            logger.debug(f"Min_Odds not found in Excel for {competition_name} - {score_normalized}, will use default from config")
        
        logger.info(f"Found from Excel: Stake={stake_percent}%, Min_Odds={min_odds if min_odds is not None else 'default'} for {competition_name} - {score_normalized}")
        
        return {
            "stake": stake_percent,
            "min_odds": min_odds  # Can be None if not in Excel
        }
        
    except FileNotFoundError:
        logger.error(f"Excel file not found: {excel_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading stake from Excel: {str(e)}")
        return None


def calculate_stake_and_liability(available_balance: float, stake_percent: float,
                                 lay_price: float) -> Tuple[float, float]:
    """
    Calculate stake and liability for a lay bet from liability percentage
    
    Formula:
    - Liability = Balance × (stake_percent / 100)
    - Stake = Liability / (lay_price - 1)
    
    Args:
        available_balance: Available balance from account
        stake_percent: Liability percentage (from Excel)
        lay_price: Lay price (odds)
    
    Returns:
        (stake, liability)
    """
    # Calculate liability first (this is the target liability amount)
    liability = available_balance * (stake_percent / 100.0)
    
    # Calculate stake from liability
    # For lay bet: liability = stake × (lay_price - 1)
    # Therefore: stake = liability / (lay_price - 1)
    stake = liability / (lay_price - 1.0)
    
    return round(stake, 2), round(liability, 2)


def execute_lay_bet(market_service: MarketService, betting_service: BettingService,
                   event_id: str, event_name: str, target_over: float,
                   bet_config: Dict[str, Any],
                   competition_name: str, current_score: str, excel_path: str) -> Optional[Dict[str, Any]]:
    """
    Execute lay bet on Over X.5 market
    
    Args:
        market_service: MarketService instance
        betting_service: BettingService instance
        event_id: Betfair event ID
        event_name: Event name (for logging)
        target_over: Target Over value (e.g., 2.5)
        bet_config: Bet execution configuration
        competition_name: Competition name (for Excel lookup)
        current_score: Current score at minute 75 (format: "1-1", "0-0")
        excel_path: Path to Excel file (Competitions_Results_Odds_Stake.xlsx)
    
    Returns:
        {
            "success": True,
            "betId": "31242604945",
            "marketId": "1.xxxxx",
            "selectionId": 12345,
            "stake": 50.0,
            "layPrice": 2.04,
            "liability": 52.0
        } or None if failed
    """
    logger.info(f"Executing lay bet for {event_name} (Over {target_over})")
    
    # Phase 1: Find Under X.5 market (for odds check - best back price)
    under_market_info = find_under_market(market_service, event_id, target_over)
    if not under_market_info:
        logger.warning(f"Under {target_over} market not found for {event_name}")
        return {
            "success": False,
            "reason": f"Under {target_over} market not found",
            "skip_reason": "Market unavailable"
        }
    
    under_market_id = under_market_info["marketId"]
    under_selection_id = under_market_info["selectionId"]
    under_market_name = under_market_info["marketName"]
    under_runner_name = under_market_info["runnerName"]
    
    logger.info(f"Found Under market: {under_market_name} (marketId: {under_market_id}, selectionId: {under_selection_id})")
    
    # Phase 2: Get market book data for Under X.5 (to check best back price)
    under_market_data = get_market_book_data(market_service, under_market_id, under_selection_id)
    if not under_market_data:
        logger.warning(f"Could not get market book data for Under {under_market_name}")
        return {
            "success": False,
            "reason": "Could not get market book data for Under X.5",
            "skip_reason": "Market closed or unavailable",
            "bestBackPrice": None,
            "bestLayPrice": None,
            "spread_ticks": None
        }
    
    # Get best back price from Under X.5 (this is what we check)
    under_best_back = under_market_data["bestBackPrice"]
    under_best_lay = under_market_data["bestLayPrice"]
    under_market_status = under_market_data.get("status", "UNKNOWN")
    
    logger.info(f"Under {target_over} prices: Back={under_best_back}, Lay={under_best_lay}")
    
    # Phase 3: Find Over X.5 market (for lay bet placement)
    over_market_info = find_over_market(market_service, event_id, target_over)
    if not over_market_info:
        logger.warning(f"Over {target_over} market not found for {event_name}")
        return {
            "success": False,
            "reason": f"Over {target_over} market not found",
            "skip_reason": "Market unavailable"
        }
    
    over_market_id = over_market_info["marketId"]
    over_selection_id = over_market_info["selectionId"]
    over_market_name = over_market_info["marketName"]
    over_runner_name = over_market_info["runnerName"]
    
    logger.info(f"Found Over market: {over_market_name} (marketId: {over_market_id}, selectionId: {over_selection_id})")
    
    # Phase 4: Get market book data for Over X.5 (for lay bet placement)
    over_market_data = get_market_book_data(market_service, over_market_id, over_selection_id)
    if not over_market_data:
        logger.warning(f"Could not get market book data for Over {over_market_name}")
        return {
            "success": False,
            "reason": "Could not get market book data for Over X.5",
            "skip_reason": "Market closed or unavailable",
            "bestBackPrice": under_best_back,
            "bestLayPrice": None,
            "spread_ticks": None
        }
    
    over_best_back = over_market_data["bestBackPrice"]
    over_best_lay = over_market_data["bestLayPrice"]
    over_lay_size = over_market_data.get("laySize", 0.0)
    over_total_lay_size = over_market_data.get("totalLaySize", 0.0)
    
    logger.info(f"Over {target_over} prices: Back={over_best_back}, Lay={over_best_lay}")
    logger.info(f"Over lay side depth: best price size={over_lay_size}, total size={over_total_lay_size}")
    
    # Phase 5: Get stake and Min_Odds from Excel first (before market conditions check)
    # Per client requirement: Each competition + result has its own Min_Odds
    # Example: Serie A has its own Min_Odds, Premier League has different Min_Odds, etc.
    # Bot reads the correct Min_Odds for each competition from Excel (not using a common set)
    excel_data = get_stake_from_excel(competition_name, current_score, excel_path)
    
    if excel_data is None:
        # Score not found in Excel → discard match (no bet placed)
        logger.warning(f"Score {current_score} not found in Excel for {competition_name}. Discarding match.")
        return {
            "success": False,
            "reason": f"Score {current_score} not found in Excel for {competition_name}",
            "skip_reason": "Score not in Excel targets",
            "bestBackPrice": under_best_back,  # Under X.5 best back
            "bestLayPrice": over_best_lay,  # Over X.5 best lay
            "spread_ticks": spread_ticks,
            "competition": competition_name,
            "score": current_score
        }
    
    stake_percent = excel_data.get("stake")
    min_odds_from_excel = excel_data.get("min_odds")
    
    # Use Min_Odds from Excel if available, otherwise fallback to config default
    # Each competition + result has its own Min_Odds (e.g., Serie A has different Min_Odds than Premier League)
    if min_odds_from_excel is not None:
        min_odds = min_odds_from_excel
        logger.info(f"Using Min_Odds from Excel: {min_odds} for {competition_name} - {current_score} (competition-specific odds)")
    else:
        # Fallback to config default if not in Excel
        min_odds = bet_config.get("min_odds", 1.5)
        logger.info(f"Min_Odds not in Excel, using default from config: {min_odds}")
    
    max_spread_ticks = bet_config.get("max_spread_ticks", 4)
    ladder_type = bet_config.get("price_ladder_type", "CLASSIC")
    
    # Phase 6: Check market conditions
    # Per client requirement:
    # - Odds check: Under X.5 best back price > min_odds (from Excel, per competition + result)
    #   * At minute 75', Odds only needs to be greater than Min_Odds (no maximum check)
    #   * Correct: Odds_75 > Min_Odds
    #   * Wrong: Min_Odds < Odds_75 < Quota_Max_Lay_Over (NOT used)
    # - Spread check: Over X.5 best lay - Over X.5 best back (in same market)
    check_market_data = {
        "bestBackPrice": over_best_back,  # Over X.5 best back (for spread calculation)
        "bestLayPrice": over_best_lay,  # Over X.5 best lay (for spread calculation)
        "laySize": over_lay_size,  # Use Over X.5 lay size
        "totalLaySize": over_total_lay_size,  # Use Over X.5 total lay size
        "underBestBack": under_best_back  # Under X.5 best back (for odds check)
    }
    
    is_valid, reason = check_market_conditions(
        check_market_data, min_odds, max_spread_ticks, ladder_type
    )
    
    # Calculate spread in ticks for skipped matches (Over X.5 best lay - Over X.5 best back)
    spread_ticks = calculate_ticks_between(over_best_back, over_best_lay, ladder_type) if over_best_back and over_best_lay else None
    
    if not is_valid:
        logger.warning(f"Market conditions not met: {reason}")
        return {
            "success": False,
            "reason": reason,
            "skip_reason": "Market conditions not met",
            "bestBackPrice": under_best_back,  # Under X.5 best back
            "bestLayPrice": over_best_lay,  # Over X.5 best lay
            "spread_ticks": spread_ticks,
            "marketStatus": under_market_status
        }
    
    logger.info(f"Market conditions OK: {reason} (checked Under {target_over} best back: {under_best_back} > {min_odds})")
    
    # Phase 7: Calculate lay price for Over X.5 (+2 ticks from Over X.5 best lay price)
    ticks_offset = bet_config.get("ticks_offset", 2)
    lay_price = calculate_lay_price(over_best_lay, ticks_offset, ladder_type)
    
    logger.info(f"Calculated lay price for Over {target_over}: {lay_price} (bestLay {over_best_lay} + {ticks_offset} ticks)")
    
    # Phase 8: Calculate stake/liability (stake_percent already retrieved from Excel in Phase 5)
    
    # Step 5.2: Get account funds
    account_funds = market_service.get_account_funds()
    if not account_funds:
        logger.warning("Could not retrieve account funds")
        return {
            "success": False,
            "reason": "Could not retrieve account funds",
            "skip_reason": "Account funds unavailable",
            "bestBackPrice": under_best_back,  # Under X.5 best back
            "bestLayPrice": over_best_lay,  # Over X.5 best lay
            "spread_ticks": spread_ticks
        }
    
    available_balance = account_funds.get("availableToBetBalance", 0.0)
    if available_balance <= 0:
        logger.warning(f"Insufficient balance: {available_balance}")
        return {
            "success": False,
            "reason": f"Insufficient balance: {available_balance}",
            "skip_reason": "Insufficient balance",
            "bestBackPrice": under_best_back,  # Under X.5 best back
            "bestLayPrice": over_best_lay,  # Over X.5 best lay
            "spread_ticks": spread_ticks
        }
    
    # Step 5.3: Calculate stake and liability from Excel stake percentage
    stake, liability = calculate_stake_and_liability(
        available_balance, stake_percent, lay_price
    )
    
    logger.info(f"Stake calculation from Excel: Competition={competition_name}, Score={current_score}, Stake%={stake_percent}%, Balance={available_balance}, Stake={stake}, Liability={liability}")
    
    # Check if we have enough funds
    if liability > available_balance:
        logger.warning(f"Insufficient funds: need {liability}, have {available_balance}")
        return {
            "success": False,
            "reason": f"Insufficient funds: need {liability}, have {available_balance}",
            "skip_reason": "Insufficient funds for liability",
            "bestBackPrice": under_best_back,  # Under X.5 best back
            "bestLayPrice": over_best_lay,  # Over X.5 best lay
            "spread_ticks": spread_ticks,
            "calculatedLayPrice": lay_price,
            "calculatedLiability": liability
        }
    
    # Phase 8: Place lay bet on Over X.5
    persistence_type = bet_config.get("persistence_type", "LAPSE")
    
    logger.info(f"Placing lay bet on Over {target_over}: Price={lay_price}, Size={stake}, Liability={liability}")
    
    bet_result = betting_service.place_lay_bet(
        market_id=over_market_id,  # Use Over X.5 market ID
        selection_id=over_selection_id,  # Use Over X.5 selection ID
        price=lay_price,
        size=stake,
        persistence_type=persistence_type
    )
    
    if not bet_result:
        logger.error("Failed to place bet")
        return {
            "success": False,
            "reason": "Failed to place bet (API error)",
            "skip_reason": "Bet placement failed",
            "bestBackPrice": under_best_back,  # Under X.5 best back
            "bestLayPrice": over_best_lay,  # Over X.5 best lay
            "spread_ticks": spread_ticks,
            "calculatedLayPrice": lay_price,
            "calculatedStake": stake,
            "calculatedLiability": liability
        }
    
    # Phase 9: Return result
    logger.info(f"Bet placed successfully: BetId={bet_result.get('betId')}")
    
    return {
        "success": True,
        "betId": bet_result.get("betId"),
        "marketId": over_market_id,  # Over X.5 market ID
        "selectionId": over_selection_id,  # Over X.5 selection ID
        "marketName": over_market_name,  # Over X.5 market name
        "runnerName": over_runner_name,  # Over X.5 runner name
        "stake": stake,
        "layPrice": lay_price,
        "liability": liability,
        "bestBackPrice": under_best_back,  # Under X.5 best back (used for odds check)
        "bestLayPrice": over_best_lay,  # Over X.5 best lay (used for bet placement)
        "spread_ticks": spread_ticks,
        "orderStatus": bet_result.get("orderStatus"),
        "sizeMatched": bet_result.get("sizeMatched", 0.0),
        "averagePriceMatched": bet_result.get("averagePriceMatched", 0.0),
        "placedDate": bet_result.get("placedDate")
    }

