"""
Market Filter Module
Filters markets to only include match-specific markets, excluding season-long markets
"""
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger("BetfairBot")


# Market types that are allowed (match-specific)
ALLOWED_MARKET_TYPES = [
    "OVER_UNDER_25",      # Over/Under 2.5
    "OVER_UNDER_15",      # Over/Under 1.5
    "OVER_UNDER_35",      # Over/Under 3.5
    "OVER_UNDER_05",      # Over/Under 0.5
    "OVER_UNDER_45",      # Over/Under 4.5
    "MATCH_ODDS",         # Match Odds
    "BOTH_TEAMS_TO_SCORE", # Both Teams to Score
    "CORRECT_SCORE",      # Correct Score
    "FIRST_GOAL_SCORER",  # First Goal Scorer
    "NEXT_GOAL",          # Next Goal
    "HALF_TIME_SCORE",    # Half Time Score
    "HALF_TIME_FULL_TIME", # Half Time / Full Time
    "DRAW_NO_BET",        # Draw No Bet
    "DOUBLE_CHANCE",      # Double Chance
    "ASIAN_HANDICAP",     # Asian Handicap
    "EUROPEAN_HANDICAP",  # European Handicap
    "TOTAL_GOALS",        # Total Goals
    "WIN_DRAW_WIN",       # Win Draw Win
    "TO_SCORE",           # To Score
    "TO_SCORE_2_OR_MORE", # To Score 2 or More
    "TO_SCORE_A_HATTRICK", # To Score a Hat-trick
    "ANYTIME_GOALSCORER", # Anytime Goalscorer
    "FIRST_GOALSCORER",   # First Goalscorer
    "LAST_GOALSCORER",    # Last Goalscorer
    "MATCH_BETTING",      # Match Betting
    "MATCH_RESULT",       # Match Result
    "TO_WIN_MATCH",       # To Win Match
    "TO_WIN_TO_NIL",      # To Win to Nil
    "TO_WIN_EITHER_HALF", # To Win Either Half
    "TO_WIN_BOTH_HALVES", # To Win Both Halves
    "CLEAN_SHEET",        # Clean Sheet
    "TEAM_TOTAL_GOALS",   # Team Total Goals
    "EXACT_GOALS",        # Exact Goals
    "ODD_OR_EVEN",        # Odd or Even
    "GOAL_BOTH_HALVES",   # Goal in Both Halves
    "MOST_GOALS",         # Most Goals
    "TO_QUALIFY",         # To Qualify (match-specific, not season)
    "TO_LIFT_TROPHY",     # To Lift Trophy (match-specific, e.g., cup final)
]

# Market types that are excluded (season-long or outright)
EXCLUDED_MARKET_TYPES = [
    "OUTRIGHT",           # Outright Winner
    "TOP_GOALSCORER",     # Top Goalscorer (season-long)
    "RELEGATION",         # Relegation
    "PROMOTION",          # Promotion
    "CHAMPION",           # Champion
    "WINNER",             # Winner (outright)
    "SEASON_WINNER",      # Season Winner
    "LEAGUE_WINNER",      # League Winner
    "TITLE_WINNER",       # Title Winner
]

# Keywords in market name that indicate season-long markets
EXCLUDED_KEYWORDS = [
    "winner",
    "champion",
    "outright",
    "season",
    "league winner",
    "top scorer",
    "relegation",
    "promotion",
    "championship",
    "title",
    "season winner",
    "golden boot",
    "player of the season",
    "manager of the season",
    "young player",
    "most assists",
    "most goals",
    "clean sheets",
    "goalkeeper",
    "defender",
    "midfielder",
    "forward",
    "team of the season",
]


def is_match_specific_market(market: Dict[str, Any]) -> bool:
    """
    Check if market is match-specific (not season-long)
    
    Args:
        market: Market dictionary from Betfair API
    
    Returns:
        True if market is match-specific, False if season-related
    """
    market_name = market.get("marketName", "").lower()
    market_type = market.get("marketType", "").upper()
    
    # Check excluded keywords in market name
    for keyword in EXCLUDED_KEYWORDS:
        if keyword in market_name:
            logger.debug(f"Excluded market (keyword '{keyword}'): {market.get('marketName', 'N/A')}")
            return False
    
    # Check excluded market types
    if market_type in EXCLUDED_MARKET_TYPES:
        logger.debug(f"Excluded market (type '{market_type}'): {market.get('marketName', 'N/A')}")
        return False
    
    # Check if market type is in allowed list
    if market_type in ALLOWED_MARKET_TYPES:
        return True
    
    # Check if market name contains match-specific indicators
    match_indicators = [
        "over", "under", "match odds", "both teams", 
        "correct score", "first goal", "next goal",
        "half time", "full time", "draw",
        "handicap", "total goals", "to score",
        "clean sheet", "win to nil", "exact goals",
        "odd or even", "both halves", "to qualify"
    ]
    
    for indicator in match_indicators:
        if indicator in market_name:
            return True
    
    # Default: exclude if unsure (safer approach)
    # Log at debug level to avoid spam
    logger.debug(f"Uncertain market type, excluding (safer): {market.get('marketName', 'N/A')} (type: {market_type})")
    return False


def filter_match_specific_markets(markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter markets to only keep match-specific markets
    
    Args:
        markets: List of market dictionaries from Betfair API
    
    Returns:
        Filtered list of match-specific markets
    """
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
            market_name = market.get("marketName", "N/A")
            excluded_markets.append(market_name)
    
    if excluded_count > 0:
        logger.debug(f"Filtered out {excluded_count} season-related market(s), kept {len(filtered)} match-specific market(s)")
        # Log first few excluded markets at debug level
        if excluded_markets:
            logger.debug(f"Excluded markets (sample): {', '.join(excluded_markets[:5])}{'...' if len(excluded_markets) > 5 else ''}")
    
    return filtered

