"""
Match Matcher Module
Matches Betfair events with Live Score API matches
"""
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("BetfairBot")

# League name normalization mapping (similar to compare_competitions.py)
LEAGUE_NORMALIZATION = {
    "serie a": "serie a",
    "serie b": "serie b",
    "premier league": "premier league",
    "championship": "championship",
    "league one": "league 1",
    "league two": "league 2",
    "ligue 2": "ligue 2",
    "national": "national",
    "bundesliga 1": "bundesliga",
    "bundesliga": "bundesliga",
    "3rd liga": "3. liga",
    "3. liga": "3. liga",
    "eredivisie": "eredivisie",
    "ekstraklasa": "ekstraklasa",
    "segunda liga": "segunda liga",
    "liga 1": "liga i",
    "liga i": "liga i",
    "liga 2": "liga ii",
    "liga ii": "liga ii",
    "prva liga": "prva liga",
    "prvaliga": "prva liga",
    "2. snl": "2nd snl",
    "2nd snl": "2nd snl",
    "2. liga": "2nd liga",
    "2nd liga": "2nd liga",
    "super league": "super league",
    "superliga": "superliga",
    "allsvenskan": "allsvenskan",
    "challenge league": "challenge league",
    "1. lig": "1st lig",
    "1st lig": "1st lig",
    "mls": "major league soccer",
    "major league soccer": "major league soccer",
    "vtora liga": "vtora liga",
    "division 1": "division 1",
    "division 2": "division 2",
    "primera division": "primera division",
    "segunda division": "segunda division",
    "chinese league": "chinese super league",
    "chinese super league": "chinese super league",
    "j. league 2": "j. league 2",
    "eliteserien": "eliteserien",
    "regionalliga": "regionalliga",
    "championnat national": "championnat national",
}

# Manual competition name mappings (for ambiguous cases)
COMPETITION_MANUAL_MAPPING = {
    # Format: (betfair_name_normalized, api_name_normalized)
    # These will be matched exactly
    ("romania liga 1", "liga i"),
    ("romania liga 2", "liga ii"),
    ("spain primera division", "primera division"),
    ("argentina primera division", "primera division"),
    ("italy serie b", "serie b"),
    ("brazil brasilero serie b", "serie b"),
    ("china chinese league", "super league"),
    ("england championship", "championship"),
    ("scotland championship", "championship"),
    ("england league one", "league 1"),
    ("england league two", "league 2"),
}


class MatchMatcher:
    """Matches Betfair events with Live Score API matches"""
    
    def __init__(self):
        """Initialize match matcher with empty cache"""
        self.match_cache: Dict[str, str] = {}  # Betfair Event ID -> Live API Match ID
        # Logging moved to main.py setup checklist
    
    def normalize_team_name(self, team_name: str) -> str:
        """
        Normalize team name for matching
        
        Args:
            team_name: Team name to normalize
        
        Returns:
            Normalized team name
        """
        if not team_name:
            return ""
        
        # Convert to lowercase
        normalized = team_name.lower()
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'\b(fc|cf|ac|sc|united|city|town|rovers|athletic|sporting)\b', '', normalized)
        
        # Remove special characters
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def calculate_team_similarity(self, team1: str, team2: str) -> float:
        """
        Calculate similarity between two team names
        
        Args:
            team1: First team name
            team2: Second team name
        
        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not team1 or not team2:
            return 0.0
        
        norm1 = self.normalize_team_name(team1)
        norm2 = self.normalize_team_name(team2)
        
        # Exact match
        if norm1 == norm2:
            return 1.0
        
        # Check if one contains the other (e.g., "Atletico MG" vs "Atletico Mineiro")
        if norm1 in norm2 or norm2 in norm1:
            return 0.9
        
        # Calculate word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0.0
        
        # Jaccard similarity
        similarity = len(intersection) / len(union)
        
        return similarity
    
    def match_teams(self, betfair_home: str, betfair_away: str, 
                   live_home: str, live_away: str) -> bool:
        """
        Match team names between Betfair and Live API
        
        Args:
            betfair_home: Home team name from Betfair
            betfair_away: Away team name from Betfair
            live_home: Home team name from Live API
            live_away: Away team name from Live API
        
        Returns:
            True if teams match, False otherwise
        """
        # Match home teams
        home_similarity = self.calculate_team_similarity(betfair_home, live_home)
        
        # Match away teams
        away_similarity = self.calculate_team_similarity(betfair_away, live_away)
        
        # Both teams must match with high similarity (>= 0.7)
        if home_similarity >= 0.7 and away_similarity >= 0.7:
            logger.debug(f"Teams matched: '{betfair_home}' vs '{live_home}' ({home_similarity:.2f}), "
                        f"'{betfair_away}' vs '{live_away}' ({away_similarity:.2f})")
            return True
        
        # Try swapped (in case home/away are reversed)
        swapped_home_similarity = self.calculate_team_similarity(betfair_home, live_away)
        swapped_away_similarity = self.calculate_team_similarity(betfair_away, live_home)
        
        if swapped_home_similarity >= 0.7 and swapped_away_similarity >= 0.7:
            logger.debug(f"Teams matched (swapped): '{betfair_home}' vs '{live_away}' ({swapped_home_similarity:.2f}), "
                        f"'{betfair_away}' vs '{live_home}' ({swapped_away_similarity:.2f})")
            return True
        
        return False
    
    def normalize_competition_name(self, name: str) -> str:
        """
        Normalize competition name for matching
        
        Args:
            name: Competition name to normalize
        
        Returns:
            Normalized competition name
        """
        if not name:
            return ""
        
        # Convert to lowercase and strip
        normalized = name.lower().strip()
        
        # Remove common prefixes/suffixes and special characters
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def extract_league_name(self, competition_name: str) -> str:
        """
        Extract league name from competition name (remove country prefix if exists)
        
        Args:
            competition_name: Full competition name (e.g., "Italy-Serie A" or "Serie A")
        
        Returns:
            League name only
        """
        normalized = self.normalize_competition_name(competition_name)
        
        # Try to split by common separators
        parts = re.split(r'[-–—]', normalized)
        if len(parts) > 1:
            # Assume last part is league name
            league = parts[-1].strip()
        else:
            # No separator, assume whole name is league
            league = normalized
        
        # Normalize league name using mapping
        league = LEAGUE_NORMALIZATION.get(league, league)
        
        return league
    
    def match_competition(self, betfair_competition: str, live_competition: str) -> bool:
        """
        Match competition names with improved logic
        
        Args:
            betfair_competition: Competition name from Betfair
            live_competition: Competition name from Live API
        
        Returns:
            True if competitions match, False otherwise
        """
        if not betfair_competition or not live_competition:
            return False
        
        # Normalize competition names
        betfair_norm = self.normalize_competition_name(betfair_competition)
        live_norm = self.normalize_competition_name(live_competition)
        
        # Strategy 1: Exact match
        if betfair_norm == live_norm:
            return True
        
        # Strategy 2: Check manual mapping
        betfair_league = self.extract_league_name(betfair_competition)
        live_league = self.extract_league_name(live_competition)
        
        # Check if both normalize to same league name
        if betfair_league == live_league and betfair_league:
            return True
        
        # Check manual mapping
        for betfair_key, api_key in COMPETITION_MANUAL_MAPPING:
            if betfair_key in betfair_norm and api_key in live_norm:
                return True
            if api_key in betfair_norm and betfair_key in live_norm:
                return True
        
        # Strategy 3: Substring match (one contains the other)
        if betfair_norm in live_norm or live_norm in betfair_norm:
            # Only accept if substantial match (at least 4 characters)
            if len(betfair_norm) >= 4 and len(live_norm) >= 4:
                return True
        
        # Strategy 4: League name matching
        if betfair_league and live_league:
            # Exact league match
            if betfair_league == live_league:
                return True
            
            # Substring match for league names
            if betfair_league in live_league or live_league in betfair_league:
                if len(betfair_league) >= 3 and len(live_league) >= 3:
                    return True
        
        # Strategy 5: Word-based similarity (Jaccard)
        words1 = set(betfair_norm.split())
        words2 = set(live_norm.split())
        
        if not words1 or not words2:
            return False
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return False
        
        # Jaccard similarity (threshold: 0.6)
        similarity = len(intersection) / len(union)
        return similarity >= 0.6
    
    def match_time(self, betfair_time: Optional[datetime], live_time: Optional[datetime], 
                   tolerance_minutes: int = 30) -> bool:
        """
        Match kick-off times
        
        Args:
            betfair_time: Kick-off time from Betfair
            live_time: Kick-off time from Live API
            tolerance_minutes: Time tolerance in minutes (default: 30)
        
        Returns:
            True if times match within tolerance, False otherwise
        """
        if not betfair_time or not live_time:
            return True  # If time not available, don't use it as filter
        
        time_diff = abs((betfair_time - live_time).total_seconds() / 60)
        return time_diff <= tolerance_minutes
    
    def match_betfair_to_live_api(self, betfair_event: Dict[str, Any], 
                                  live_matches: List[Dict[str, Any]],
                                  betfair_competition_name: str = "") -> Optional[Dict[str, Any]]:
        """
        Match a Betfair event with a Live API match
        
        Args:
            betfair_event: Betfair event dictionary
            live_matches: List of live matches from Live API
            betfair_competition_name: Competition name from Betfair (optional)
        
        Returns:
            Matched Live API match dictionary, or None if no match
        """
        betfair_event_id = betfair_event.get("id", "")
        betfair_event_name = betfair_event.get("name", "")
        
        # Check cache first
        if betfair_event_id in self.match_cache:
            cached_match_id = self.match_cache[betfair_event_id]
            # Try to find cached match in current live matches
            for live_match in live_matches:
                if str(live_match.get("id", "")) == cached_match_id:
                    logger.debug(f"Using cached match for Betfair event {betfair_event_id}")
                    return live_match
        
        # Parse Betfair event name (format: "Team A v Team B")
        betfair_teams = betfair_event_name.split(" v ")
        if len(betfair_teams) != 2:
            logger.warning(f"Could not parse Betfair event name: {betfair_event_name}")
            return None
        
        betfair_home = betfair_teams[0].strip()
        betfair_away = betfair_teams[1].strip()
        
        # Get Betfair kick-off time if available
        betfair_time = None
        if "startTime" in betfair_event:
            try:
                betfair_time = datetime.fromisoformat(betfair_event["startTime"].replace("Z", "+00:00"))
            except:
                pass
        
        # Try to match with each live match
        best_match = None
        best_score = 0.0
        
        for live_match in live_matches:
            try:
                # Parse Live API match teams
                from football_api.parser import parse_match_teams, parse_match_competition
                live_home, live_away = parse_match_teams(live_match)
                live_competition = parse_match_competition(live_match)
                
                # Match teams
                teams_match = self.match_teams(betfair_home, betfair_away, live_home, live_away)
                if not teams_match:
                    continue
                
                # Match competition (if provided)
                competition_match = True
                if betfair_competition_name:
                    competition_match = self.match_competition(betfair_competition_name, live_competition)
                
                # Match time (if available)
                live_time = None
                if "kickoff" in live_match or "start_time" in live_match:
                    try:
                        time_str = live_match.get("kickoff") or live_match.get("start_time")
                        live_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except:
                        pass
                
                time_match = self.match_time(betfair_time, live_time)
                
                # Calculate match score
                score = 0.0
                if teams_match:
                    score += 0.6  # Teams matching is most important
                if competition_match:
                    score += 0.3
                if time_match:
                    score += 0.1
                
                if score > best_score:
                    best_score = score
                    best_match = live_match
                    
            except Exception as e:
                logger.warning(f"Error matching with live match: {str(e)}")
                continue
        
        # If match found, cache it
        if best_match and best_score >= 0.6:  # Minimum threshold
            live_match_id = str(best_match.get("id", ""))
            self.match_cache[betfair_event_id] = live_match_id
            logger.info(f"Matched Betfair event '{betfair_event_name}' (ID: {betfair_event_id}) "
                       f"with Live API match (ID: {live_match_id}, score: {best_score:.2f})")
            return best_match
        
        logger.debug(f"No match found for Betfair event '{betfair_event_name}' (ID: {betfair_event_id})")
        return None
    
    def clear_cache(self):
        """Clear the match cache"""
        self.match_cache.clear()
        logger.info("Match cache cleared")
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.match_cache)

