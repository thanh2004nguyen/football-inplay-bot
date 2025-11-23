"""
Live API Services Module
Consolidated Live Score API services: Client, Matcher, Parser
"""
import requests
import time
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("BetfairBot")

# ============================================================================
# PARSER FUNCTIONS
# ============================================================================

def parse_match_score(match_data: Dict[str, Any]) -> str:
    """Parse current score from match data"""
    try:
        # First try: Check if "score" field exists directly (from /scores/events.json endpoint)
        if "score" in match_data:
            score_str = str(match_data["score"]).strip()
            if score_str and score_str != "":
                # Format could be "2-0", "2 - 0", "2:0", "0-0", etc.
                # Remove spaces and try different separators
                score_clean = score_str.replace(" ", "").replace(":", "-")
                parts = score_clean.split("-")
                if len(parts) >= 2:
                    try:
                        home_score = int(parts[0])
                        away_score = int(parts[1])
                        return f"{home_score}-{away_score}"
                    except (ValueError, IndexError):
                        pass
        
        # Second try: Check "scores" dict (from /matches/live.json endpoint)
        if "scores" in match_data and isinstance(match_data["scores"], dict):
            score_str = match_data["scores"].get("score", "")
            if score_str:
                parts = score_str.replace(" ", "").split("-")
                if len(parts) == 2:
                    try:
                        home_score = int(parts[0])
                        away_score = int(parts[1])
                        return f"{home_score}-{away_score}"
                    except ValueError:
                        pass
        
        home_score = None
        away_score = None
        
        if "home_score" in match_data:
            home_score = match_data["home_score"]
        elif "score_home" in match_data:
            home_score = match_data["score_home"]
        elif "home" in match_data and isinstance(match_data["home"], dict):
            home_score = match_data["home"].get("score")
        
        if "away_score" in match_data:
            away_score = match_data["away_score"]
        elif "score_away" in match_data:
            away_score = match_data["score_away"]
        elif "away" in match_data and isinstance(match_data["away"], dict):
            away_score = match_data["away"].get("score")
        
        if home_score is None:
            home_score = 0
        if away_score is None:
            away_score = 0
        
        return f"{home_score}-{away_score}"
        
    except Exception as e:
        logger.warning(f"Error parsing match score: {str(e)}")
        return "0-0"


def parse_match_minute(match_data: Dict[str, Any]) -> int:
    """Parse current match minute from match data"""
    try:
        time_str = match_data.get("time", "")
        
        if not time_str:
            return -1
        
        time_str_upper = str(time_str).upper().strip()
        if time_str_upper == "HT":
            return 45
        elif time_str_upper == "FT":
            return 90
        elif time_str_upper == "AET":
            return 120
        elif time_str_upper == "AP":
            return 120
        
        status = match_data.get("status", "").upper()
        if "NOT STARTED" in status or "SCHEDULED" in status or "POSTPONED" in status:
            return -1
        
        try:
            minute = int(time_str)
            if 0 <= minute <= 120:
                return minute
            else:
                if len(str(time_str)) == 4 and minute > 1000:
                    logger.debug(f"Time field '{time_str}' appears to be kickoff time, not current minute")
                    return -1
                return minute
        except ValueError:
            minute_str = ''.join(filter(str.isdigit, str(time_str)))
            if minute_str:
                minute = int(minute_str)
                if 0 <= minute <= 120:
                    return minute
                if len(minute_str) == 4 and minute > 1000:
                    logger.debug(f"Time field '{time_str}' appears to be kickoff time, not current minute")
                    return -1
        
        if status == "IN PLAY" or "LIVE" in status:
            return 0
        
        return -1
        
    except Exception as e:
        logger.warning(f"Error parsing match minute: {str(e)}")
        return -1


def parse_goals_timeline(match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse goal timeline from match data"""
    goals = []
    
    try:
        goals_data = None
        
        if "goals" in match_data:
            goals_data = match_data["goals"]
        elif "events" in match_data:
            events = match_data["events"]
            if isinstance(events, list):
                goals_data = [e for e in events if e.get("type", "").lower() == "goal"]
        elif "timeline" in match_data:
            timeline = match_data["timeline"]
            if isinstance(timeline, list):
                goals_data = [e for e in timeline if e.get("event_type", "").lower() == "goal"]
        
        if not goals_data:
            return goals
        
        for goal_data in goals_data:
            try:
                goal = {}
                
                minute = goal_data.get("minute") or goal_data.get("time") or goal_data.get("min")
                if isinstance(minute, str):
                    minute = ''.join(filter(str.isdigit, minute))
                    minute = int(minute) if minute else None
                goal["minute"] = int(minute) if minute is not None else 0
                
                team = goal_data.get("team", "").lower()
                if "home" in team or goal_data.get("is_home", False):
                    goal["team"] = "home"
                elif "away" in team or goal_data.get("is_away", False):
                    goal["team"] = "away"
                else:
                    goal["team"] = "home"
                
                if "player" in goal_data:
                    goal["player"] = goal_data["player"]
                elif "player_name" in goal_data:
                    goal["player"] = goal_data["player_name"]
                
                cancelled = goal_data.get("cancelled", False)
                if isinstance(cancelled, str):
                    cancelled = cancelled.lower() in ["true", "yes", "1", "cancelled"]
                goal["cancelled"] = bool(cancelled)
                
                goals.append(goal)
                
            except Exception as e:
                logger.warning(f"Error parsing individual goal: {str(e)}")
                continue
        
        logger.debug(f"Parsed {len(goals)} goal(s) from match data")
        return goals
        
    except Exception as e:
        logger.warning(f"Error parsing goals timeline: {str(e)}")
        return []


def parse_match_teams(match_data: Dict[str, Any]) -> tuple:
    """Parse team names from match data"""
    try:
        home_team = None
        away_team = None
        
        if "home" in match_data and isinstance(match_data["home"], dict):
            home_team = match_data["home"].get("name")
        
        if "away" in match_data and isinstance(match_data["away"], dict):
            away_team = match_data["away"].get("name")
        
        if not home_team:
            if "home_team" in match_data:
                home_team = match_data["home_team"]
            elif "home_name" in match_data:
                home_team = match_data["home_name"]
        
        if not away_team:
            if "away_team" in match_data:
                away_team = match_data["away_team"]
            elif "away_name" in match_data:
                away_team = match_data["away_name"]
        
        if not home_team:
            home_team = "Home Team"
        if not away_team:
            away_team = "Away Team"
        
        return (home_team, away_team)
        
    except Exception as e:
        logger.warning(f"Error parsing team names: {str(e)}")
        return ("Home Team", "Away Team")


def parse_match_competition(match_data: Dict[str, Any]) -> str:
    """Parse competition/league name from match data"""
    try:
        competition_name = None
        competition_id = None
        
        if "competition" in match_data:
            comp_obj = match_data["competition"]
            if isinstance(comp_obj, dict):
                competition_id = comp_obj.get("id")
                competition_name = comp_obj.get("name")
        
        if not competition_name:
            if "league" in match_data:
                competition_name = match_data["league"]
            elif "competition_name" in match_data:
                competition_name = match_data["competition_name"]
            elif "league_name" in match_data:
                competition_name = match_data["league_name"]
            elif "tournament" in match_data:
                competition_name = match_data["tournament"]
            
            if isinstance(competition_name, dict):
                competition_id = competition_name.get("id")
                competition_name = competition_name.get("name") or competition_name.get("title")
        
        if not competition_name:
            return ""
        
        if competition_id:
            return f"{competition_id}_{competition_name}"
        else:
            return competition_name
        
    except Exception as e:
        logger.warning(f"Error parsing competition name: {str(e)}")
        return ""


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Rate limiter to enforce API request limits"""
    
    def __init__(self, requests_per_day: int):
        self.requests_per_day = requests_per_day
        self.requests_per_hour = requests_per_day / 24
        self.requests_today = 0
        self.requests_this_hour = 0
        self.last_reset_date = datetime.now().date()
        self.last_reset_hour = datetime.now().hour
        self.request_times = []
        
    def _reset_if_needed(self):
        """Reset counters if day or hour has changed"""
        now = datetime.now()
        current_date = now.date()
        current_hour = now.hour
        
        if current_date != self.last_reset_date:
            self.requests_today = 0
            self.last_reset_date = current_date
            logger.info(f"Rate limiter: Daily counter reset (limit: {self.requests_per_day}/day)")
        
        if current_hour != self.last_reset_hour:
            self.requests_this_hour = 0
            self.last_reset_hour = current_hour
            cutoff = now - timedelta(hours=1)
            self.request_times = [t for t in self.request_times if t > cutoff]
            logger.debug(f"Rate limiter: Hourly counter reset (limit: {self.requests_per_hour:.1f}/hour)")
    
    def can_make_request(self) -> bool:
        """Check if a request can be made without exceeding limits"""
        self._reset_if_needed()
        
        if self.requests_today >= self.requests_per_day:
            logger.warning(f"Rate limit exceeded: {self.requests_today}/{self.requests_per_day} requests today")
            return False
        
        if self.requests_this_hour >= self.requests_per_hour:
            logger.warning(f"Rate limit exceeded: {self.requests_this_hour:.1f}/{self.requests_per_hour:.1f} requests this hour")
            return False
        
        return True
    
    def record_request(self):
        """Record that a request was made"""
        self._reset_if_needed()
        self.requests_today += 1
        self.requests_this_hour += 1
        self.request_times.append(datetime.now())
        logger.debug(f"Rate limiter: {self.requests_today}/{self.requests_per_day} requests today, {self.requests_this_hour:.1f}/{self.requests_per_hour:.1f} this hour")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status"""
        self._reset_if_needed()
        return {
            "requests_today": self.requests_today,
            "requests_per_day": self.requests_per_day,
            "remaining_today": self.requests_per_day - self.requests_today,
            "requests_this_hour": self.requests_this_hour,
            "requests_per_hour": self.requests_per_hour,
            "remaining_this_hour": max(0, self.requests_per_hour - self.requests_this_hour)
        }


# ============================================================================
# LIVE SCORE CLIENT
# ============================================================================

class LiveScoreClient:
    """Client for live-score-api.com"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://livescore-api.com/api-client", 
                 rate_limit_per_day: int = 1500):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')
        self.rate_limiter = RateLimiter(rate_limit_per_day)
        
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 2) -> Optional[Dict[str, Any]]:
        """Make API request with rate limiting, error handling, and retry logic"""
        if not self.rate_limiter.can_make_request():
            logger.error("Rate limit exceeded, cannot make request")
            return None
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Making request to: {url} (attempt {attempt + 1}/{max_retries + 1})")
                response = self.session.get(url, params=params, timeout=30)
                
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                if not response.text or not response.text.strip():
                    logger.error(f"Empty response from Live Score API: {url}")
                    return None
                
                logger.debug(f"Response preview: {response.text[:200]}")
                
                response.raise_for_status()
                
                try:
                    result = response.json()
                    self.rate_limiter.record_request()
                    return result
                except ValueError as json_error:
                    logger.error(f"Invalid JSON response from Live Score API: {str(json_error)}")
                    logger.error(f"Response text (first 500 chars): {response.text[:500]}")
                    return None
            
            except requests.exceptions.HTTPError as e:
                error_text = e.response.text[:500] if e.response.text else "No response text"
                logger.error(f"HTTP error in Live Score API request: {e.response.status_code}")
                logger.error(f"Error response: {error_text}")
                logger.error(f"Request URL: {url}")
                return None
            
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                error_str = str(e)
                is_connection_error = False
                
                if isinstance(e, requests.exceptions.ConnectionError):
                    if "RemoteDisconnected" in error_str or "ConnectionResetError" in error_str or "10054" in error_str:
                        is_connection_error = True
                
                if is_connection_error or isinstance(e, requests.exceptions.Timeout):
                    if attempt < max_retries:
                        import random
                        delay = random.uniform(0.5, 1.0)
                        logger.warning(f"Connection error in Live Score API request (attempt {attempt + 1}/{max_retries + 1}): {error_str}")
                        logger.warning(f"Retrying in {delay:.2f} seconds...")
                        logger.warning(f"Request URL: {url}")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"LiveScore API connection error after {max_retries + 1} attempts: {error_str}")
                        logger.error(f"Request URL: {url}")
                        logger.warning("LiveScore API not reachable for this cycle, skipping this poll")
                        return None
                else:
                    logger.error(f"Connection error in Live Score API request: {error_str}")
                    logger.error(f"Request URL: {url}")
                    return None
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error in Live Score API request: {str(e)}")
                logger.error(f"Request URL: {url}")
                return None
            
            except Exception as e:
                logger.error(f"Unexpected error in Live Score API request: {str(e)}", exc_info=True)
                return None
        
        logger.error(f"LiveScore API request failed after {max_retries + 1} attempts")
        logger.warning("LiveScore API not reachable for this cycle, skipping this poll")
        return None
    
    def get_live_matches(self, competition_ids: List[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Get list of currently live matches"""
        logger.debug("Fetching live matches from Live Score API")
        
        params = {
            "key": self.api_key,
            "secret": self.api_secret
        }
        
        if competition_ids:
            competition_id_str = ",".join(str(cid) for cid in competition_ids)
            logger.debug(f"Filtering Live API matches by competition IDs: {competition_id_str}")
            params["competition_id"] = competition_id_str
        
        result = self._make_request("/matches/live.json", params=params)
        
        if result is None:
            return None
        
        if isinstance(result, dict):
            if result.get("success") and "data" in result:
                matches = result["data"].get("match", [])
                
                if not isinstance(matches, list):
                    return []
                
                live_matches = []
                allowed_competition_ids = set(competition_ids) if competition_ids else None
                
                for match in matches:
                    if allowed_competition_ids:
                        comp_str = parse_match_competition(match)
                        match_comp_id = None
                        if comp_str and "_" in comp_str:
                            try:
                                match_comp_id = comp_str.split("_", 1)[0].strip()
                            except:
                                pass
                        
                        if match_comp_id and match_comp_id not in allowed_competition_ids:
                            logger.debug(f"Skipping match (competition not in filter): {match.get('home', {}).get('name', 'N/A')} v {match.get('away', {}).get('name', 'N/A')} - Competition ID: {match_comp_id}")
                            continue
                    
                    status = str(match.get("status", "")).upper()
                    
                    if "NOT STARTED" in status or "SCHEDULED" in status or "POSTPONED" in status:
                        logger.debug(f"Skipping match (not started): {match.get('home', {}).get('name', 'N/A')} v {match.get('away', {}).get('name', 'N/A')} - Status: {status}")
                        continue
                    
                    if "FINISHED" in status:
                        logger.debug(f"Skipping match (finished): {match.get('home', {}).get('name', 'N/A')} v {match.get('away', {}).get('name', 'N/A')} - Status: {status}")
                        continue
                    
                    minute = parse_match_minute(match)
                    # Filter out matches at minute 90 or above (match finished or about to finish)
                    if minute < 0 or minute >= 90:
                        logger.debug(f"Skipping match (not live or finished): {match.get('home', {}).get('name', 'N/A')} v {match.get('away', {}).get('name', 'N/A')} - Minute: {minute}")
                        continue
                    
                    live_matches.append(match)
                
                logger.debug(f"Retrieved {len(matches)} match(es) from API, filtered to {len(live_matches)} live match(es)")
                return live_matches
            else:
                logger.warning(f"API response indicates failure or unexpected structure: {result}")
                return []
        
        return []
    
    def get_match_details(self, match_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific match"""
        logger.debug(f"Fetching match details for match ID: {match_id}")
        
        # Try to convert match_id to int if it's a string number
        try:
            match_id_int = int(match_id)
            match_id_param = match_id_int
        except (ValueError, TypeError):
            match_id_param = match_id
        
        params = {
            "key": self.api_key,
            "secret": self.api_secret,
            "id": match_id_param
        }
        result = self._make_request("/scores/events.json", params=params)
        
        if result and isinstance(result, dict):
            if result.get("success") and "data" in result:
                match_data = result["data"]
                # The /scores/events.json endpoint may return data in a different structure
                # Check if it's a match object or if we need to extract from a nested structure
                if isinstance(match_data, dict):
                    # If data has a "match" key, use that
                    if "match" in match_data:
                        match_data = match_data["match"]
                    # If data is already a match object, use it directly
                    logger.debug(f"Retrieved match details for match ID: {match_id} - structure: {list(match_data.keys())[:5] if isinstance(match_data, dict) else 'not dict'}")
                    return match_data
        
        logger.warning(f"Failed to get match details for match ID: {match_id} - result: {result}")
        return None
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        return self.rate_limiter.get_status()


# ============================================================================
# MATCH MATCHER
# ============================================================================

LEAGUE_NORMALIZATION = {
    "serie a": "serie a", "serie b": "serie b", "premier league": "premier league",
    "championship": "championship", "league one": "league 1", "league two": "league 2",
    "ligue 2": "ligue 2", "national": "national", "bundesliga 1": "bundesliga",
    "bundesliga": "bundesliga", "3rd liga": "3. liga", "3. liga": "3. liga",
    "eredivisie": "eredivisie", "ekstraklasa": "ekstraklasa", "segunda liga": "segunda liga",
    "liga 1": "liga i", "liga i": "liga i", "liga 2": "liga ii", "liga ii": "liga ii",
    "prva liga": "prva liga", "prvaliga": "prva liga", "2. snl": "2nd snl",
    "2nd snl": "2nd snl", "2. liga": "2nd liga", "2nd liga": "2nd liga",
    "super league": "super league", "superliga": "superliga", "allsvenskan": "allsvenskan",
    "challenge league": "challenge league", "1. lig": "1st lig", "1st lig": "1st lig",
    "mls": "major league soccer", "major league soccer": "major league soccer",
    "vtora liga": "vtora liga", "division 1": "division 1", "division 2": "division 2",
    "primera division": "primera division", "segunda division": "segunda division",
    "chinese league": "chinese super league", "chinese super league": "chinese super league",
    "j. league 2": "j. league 2", "eliteserien": "eliteserien", "regionalliga": "regionalliga",
    "championnat national": "championnat national",
}

COMPETITION_MANUAL_MAPPING = {
    ("romania liga 1", "liga i"), ("romania liga 2", "liga ii"),
    ("spain primera division", "primera division"), ("argentina primera division", "primera division"),
    ("italy serie b", "serie b"), ("brazil brasilero serie b", "serie b"),
    ("china chinese league", "super league"), ("england championship", "championship"),
    ("scotland championship", "championship"), ("england league one", "league 1"),
    ("england league two", "league 2"),
}


class MatchMatcher:
    """Matches Betfair events with Live Score API matches"""
    
    def __init__(self):
        self.match_cache: Dict[str, str] = {}
    
    def normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for matching"""
        if not team_name:
            return ""
        
        normalized = team_name.lower()
        
        common_words = [
            'fc', 'cf', 'ac', 'sc', 'united', 'city', 'town', 'rovers', 
            'athletic', 'sporting', 'club', 'cfr', 'cf', 'fc', 'ac', 'sc',
            'tiger', 'tigers', 'lions', 'eagles', 'wolves', 'bears'
        ]
        pattern = r'\b(' + '|'.join(common_words) + r')\b'
        normalized = re.sub(pattern, '', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def calculate_team_similarity(self, team1: str, team2: str) -> float:
        """Calculate similarity between two team names"""
        if not team1 or not team2:
            return 0.0
        
        norm1 = self.normalize_team_name(team1)
        norm2 = self.normalize_team_name(team2)
        
        if norm1 == norm2:
            return 1.0
        
        if norm1 in norm2 or norm2 in norm1:
            shorter = min(len(norm1), len(norm2))
            longer = max(len(norm1), len(norm2))
            if shorter > 0 and longer > 0:
                containment_ratio = shorter / longer
                return 0.85 + (containment_ratio * 0.1)
        
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0.0
        
        jaccard_sim = len(intersection) / len(union)
        
        if words1.issubset(words2) or words2.issubset(words1):
            smaller_set = min(len(words1), len(words2))
            if smaller_set > 0:
                subset_sim = len(intersection) / smaller_set
                significant_words = [w for w in intersection if len(w) >= 4]
                if significant_words:
                    return max(jaccard_sim, subset_sim, 0.75)
                return max(jaccard_sim, subset_sim, 0.65)
        
        significant_words1 = {w for w in words1 if len(w) >= 4}
        significant_words2 = {w for w in words2 if len(w) >= 4}
        significant_intersection = significant_words1.intersection(significant_words2)
        
        if significant_intersection:
            significant_ratio = len(significant_intersection) / max(len(significant_words1), len(significant_words2), 1)
            combined_sim = (jaccard_sim * 0.6) + (significant_ratio * 0.4)
            return max(jaccard_sim, combined_sim, 0.70)
        
        for word1 in words1:
            if len(word1) >= 4:
                for word2 in words2:
                    if len(word2) >= 4:
                        if word1 in word2 or word2 in word1:
                            return max(jaccard_sim, 0.65)
        
        if len(norm1) >= 3 and len(norm2) >= 3:
            prefix1 = norm1[:min(4, len(norm1))]
            prefix2 = norm2[:min(4, len(norm2))]
            if prefix1 == prefix2:
                return max(jaccard_sim, 0.65)
        
        return jaccard_sim
    
    def match_teams(self, betfair_home: str, betfair_away: str, 
                   live_home: str, live_away: str) -> bool:
        """Match team names between Betfair and Live API"""
        home_similarity = self.calculate_team_similarity(betfair_home, live_home)
        away_similarity = self.calculate_team_similarity(betfair_away, live_away)
        
        # Very lenient thresholds to match more cases
        threshold = 0.30
        
        if home_similarity >= threshold and away_similarity >= threshold:
            logger.debug(f"Teams matched: '{betfair_home}' vs '{live_home}' ({home_similarity:.2f}), "
                        f"'{betfair_away}' vs '{live_away}' ({away_similarity:.2f})")
            return True
        
        swapped_home_similarity = self.calculate_team_similarity(betfair_home, live_away)
        swapped_away_similarity = self.calculate_team_similarity(betfair_away, live_home)
        
        if swapped_home_similarity >= threshold and swapped_away_similarity >= threshold:
            logger.debug(f"Teams matched (swapped): '{betfair_home}' vs '{live_away}' ({swapped_home_similarity:.2f}), "
                        f"'{betfair_away}' vs '{live_home}' ({swapped_away_similarity:.2f})")
            return True
        
        return False
    
    def normalize_competition_name(self, name: str) -> str:
        """Normalize competition name for matching"""
        if not name:
            return ""
        
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def extract_league_name(self, competition_name: str) -> str:
        """Extract league name from competition name"""
        normalized = self.normalize_competition_name(competition_name)
        
        parts = re.split(r'[-–—]', normalized)
        if len(parts) > 1:
            league = parts[-1].strip()
        else:
            league = normalized
        
        league = LEAGUE_NORMALIZATION.get(league, league)
        
        return league
    
    def match_competition(self, betfair_competition: str, live_competition: str) -> bool:
        """Match competition names"""
        if not betfair_competition or not live_competition:
            return False
        
        betfair_norm = self.normalize_competition_name(betfair_competition)
        live_norm = self.normalize_competition_name(live_competition)
        
        if betfair_norm == live_norm:
            return True
        
        betfair_league = self.extract_league_name(betfair_competition)
        live_league = self.extract_league_name(live_competition)
        
        if betfair_league == live_league and betfair_league:
            return True
        
        for betfair_key, api_key in COMPETITION_MANUAL_MAPPING:
            if betfair_key in betfair_norm and api_key in live_norm:
                return True
            if api_key in betfair_norm and betfair_key in live_norm:
                return True
        
        if betfair_norm in live_norm or live_norm in betfair_norm:
            if len(betfair_norm) >= 4 and len(live_norm) >= 4:
                return True
        
        if betfair_league and live_league:
            if betfair_league == live_league:
                return True
            
            if betfair_league in live_league or live_league in betfair_league:
                if len(betfair_league) >= 3 and len(live_league) >= 3:
                    return True
        
        words1 = set(betfair_norm.split())
        words2 = set(live_norm.split())
        
        if not words1 or not words2:
            return False
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return False
        
        similarity = len(intersection) / len(union)
        return similarity >= 0.6
    
    def match_time(self, betfair_time: Optional[datetime], live_time: Optional[datetime], 
                   tolerance_minutes: int = 30) -> bool:
        """Match kick-off times"""
        if not betfair_time or not live_time:
            return True
        
        time_diff = abs((betfair_time - live_time).total_seconds() / 60)
        return time_diff <= tolerance_minutes
    
    def match_betfair_to_live_api(self, betfair_event: Dict[str, Any], 
                                  live_matches: List[Dict[str, Any]],
                                  betfair_competition_name: str = "",
                                  betfair_to_live_mapping: Dict[int, str] = None) -> Optional[Dict[str, Any]]:
        """Match a Betfair event with a Live API match"""
        betfair_event_id = betfair_event.get("id", "")
        betfair_event_name = betfair_event.get("name", "")
        
        if betfair_event_id in self.match_cache:
            cached_match_id = self.match_cache[betfair_event_id]
            for live_match in live_matches:
                if str(live_match.get("id", "")) == cached_match_id:
                    logger.debug(f"Using cached match for Betfair event {betfair_event_id}")
                    return live_match
        
        betfair_competition_id = None
        if "competition" in betfair_event:
            comp_obj = betfair_event.get("competition", {})
            if isinstance(comp_obj, dict) and comp_obj:
                betfair_competition_id = comp_obj.get("id")
                if betfair_competition_id is not None:
                    try:
                        betfair_competition_id = int(betfair_competition_id)
                    except (ValueError, TypeError):
                        betfair_competition_id = None
                if not betfair_competition_id:
                    logger.warning(f"⚠️  Competition object found for '{betfair_event_name}' but no ID field: {comp_obj}")
                    logger.warning(f"   Competition object keys: {list(comp_obj.keys()) if isinstance(comp_obj, dict) else 'N/A'}")
        else:
            logger.warning(f"⚠️  No 'competition' key in betfair_event for '{betfair_event_name}'")
            logger.warning(f"   Betfair event keys: {list(betfair_event.keys())}")
        
        live_api_competition_id = None
        if betfair_competition_id and betfair_to_live_mapping:
            try:
                betfair_comp_id_int = int(betfair_competition_id)
                live_api_competition_id = betfair_to_live_mapping.get(betfair_comp_id_int)
            except (ValueError, TypeError):
                pass
        
        # If no mapping found, try to match by team names only (fallback)
        if not live_api_competition_id:
            if betfair_competition_id:
                logger.debug(f"No Live API competition ID mapping found for Betfair competition ID {betfair_competition_id}, trying team name matching as fallback")
            else:
                logger.debug(f"Betfair competition ID not available for event '{betfair_event_name}', trying team name matching as fallback")
            
            # Fallback: Try to match by team names only (without competition ID filter)
            if betfair_home_team and betfair_away_team:
                for live_match in live_matches:
                    try:
                        live_home_team, live_away_team = parse_match_teams(live_match)
                        if self.match_teams(betfair_home_team, betfair_away_team, live_home_team, live_away_team):
                            # Also check time if available
                            if betfair_time and ("kickoff" in live_match or "start_time" in live_match):
                                try:
                                    time_str = live_match.get("kickoff") or live_match.get("start_time")
                                    live_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                                    if not self.match_time(betfair_time, live_time, tolerance_minutes=60):
                                        continue
                                except:
                                    pass
                            
                            logger.debug(f"Matched '{betfair_event_name}' with '{live_home_team} v {live_away_team}' by team names only (no competition ID mapping)")
                            self.match_cache[betfair_event_id] = str(live_match.get("id", ""))
                            return live_match
                    except:
                        continue
            
            return None
        
        betfair_home_team = None
        betfair_away_team = None
        if betfair_event_name and " v " in betfair_event_name:
            try:
                parts = betfair_event_name.split(" v ", 1)
                betfair_home_team = parts[0].strip() if len(parts) > 0 else None
                betfair_away_team = parts[1].strip() if len(parts) > 1 else None
            except:
                pass
        
        betfair_time = None
        if "startTime" in betfair_event:
            try:
                betfair_time = datetime.fromisoformat(betfair_event["startTime"].replace("Z", "+00:00"))
            except:
                pass
        
        best_match = None
        best_score = 0.0
        
        # Count matches in the same competition
        matches_in_same_competition = []
        for live_match in live_matches:
            try:
                live_competition = parse_match_competition(live_match)
                live_match_competition_id = None
                if live_competition and "_" in live_competition:
                    try:
                        parts = live_competition.split("_", 1)
                        live_match_competition_id = parts[0].strip()
                        if not live_match_competition_id.isdigit():
                            live_match_competition_id = None
                    except:
                        pass
                
                if live_api_competition_id and live_match_competition_id and live_api_competition_id == live_match_competition_id:
                    matches_in_same_competition.append(live_match)
            except:
                pass
        
        # If only one match in the same competition, match with it (even if team names don't match)
        if len(matches_in_same_competition) == 1 and live_api_competition_id:
            single_match = matches_in_same_competition[0]
            live_home, live_away = parse_match_teams(single_match)
            logger.debug(f"Only one match in competition {live_api_competition_id}, matching '{betfair_event_name}' with '{live_home} v {live_away}' (team names may not match)")
            self.match_cache[betfair_event_id] = str(single_match.get("id", ""))
            return single_match
        
        for live_match in live_matches:
            try:
                live_competition = parse_match_competition(live_match)
                
                live_match_competition_id = None
                if live_competition and "_" in live_competition:
                    try:
                        parts = live_competition.split("_", 1)
                        live_match_competition_id = parts[0].strip()
                        if not live_match_competition_id.isdigit():
                            live_match_competition_id = None
                    except:
                        pass
                
                # First filter by competition ID - must match
                if live_api_competition_id and live_match_competition_id:
                    if live_api_competition_id != live_match_competition_id:
                        continue
                else:
                    continue
                
                # If competition ID matches, try to match teams
                teams_match = False
                if betfair_home_team and betfair_away_team:
                    live_home_team, live_away_team = parse_match_teams(live_match)
                    teams_match = self.match_teams(
                        betfair_home_team, betfair_away_team,
                        live_home_team, live_away_team
                    )
                    
                    # If teams don't match, try time-based matching if available
                    if not teams_match and betfair_time:
                        if "kickoff" in live_match or "start_time" in live_match:
                            try:
                                time_str = live_match.get("kickoff") or live_match.get("start_time")
                                live_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                                if self.match_time(betfair_time, live_time, tolerance_minutes=60):
                                    teams_match = True
                                    logger.debug(f"Teams matched based on competition ID + time: '{betfair_home_team} v {betfair_away_team}' vs '{live_home_team} v {live_away_team}'")
                            except:
                                pass
                    
                    if not teams_match:
                        continue
                elif not betfair_time:
                    continue
                
                # Calculate score for best match selection
                score = 1.0
                if teams_match:
                    score += 1.0
                if betfair_time and ("kickoff" in live_match or "start_time" in live_match):
                    try:
                        time_str = live_match.get("kickoff") or live_match.get("start_time")
                        live_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        if self.match_time(betfair_time, live_time, tolerance_minutes=30):
                            score += 0.1
                    except:
                        pass
                
                if score > best_score:
                    best_score = score
                    best_match = live_match
                    
            except Exception as e:
                logger.warning(f"Error matching with live match: {str(e)}")
                continue
        
        if best_match:
            live_match_id = str(best_match.get("id", ""))
            self.match_cache[betfair_event_id] = live_match_id
            return best_match
        
        # Fallback: If no match found with competition ID, try matching by team names only
        # (in case competition ID mapping is wrong or event is in different competition)
        if betfair_home_team and betfair_away_team:
            if live_api_competition_id:
                logger.debug(f"No match found with competition ID {live_api_competition_id}, trying team name matching as fallback for '{betfair_event_name}'")
            else:
                logger.debug(f"No competition ID mapping, trying team name matching as fallback for '{betfair_event_name}'")
            
            best_fallback_match = None
            best_fallback_similarity = 0.0
            
            for live_match in live_matches:
                try:
                    live_home_team, live_away_team = parse_match_teams(live_match)
                    
                    # Calculate similarity to find best match
                    home_sim = self.calculate_team_similarity(betfair_home_team, live_home_team)
                    away_sim = self.calculate_team_similarity(betfair_away_team, live_away_team)
                    swapped_home_sim = self.calculate_team_similarity(betfair_home_team, live_away_team)
                    swapped_away_sim = self.calculate_team_similarity(betfair_away_team, live_home_team)
                    
                    normal_avg = (home_sim + away_sim) / 2
                    swapped_avg = (swapped_home_sim + swapped_away_sim) / 2
                    match_sim = max(normal_avg, swapped_avg)
                    
                    # Use threshold 0.30 for fallback matching
                    if match_sim >= 0.30:
                        if match_sim > best_fallback_similarity:
                            best_fallback_similarity = match_sim
                            best_fallback_match = live_match
                except Exception as e:
                    logger.debug(f"Error in fallback matching: {str(e)}")
                    continue
            
            if best_fallback_match:
                live_home, live_away = parse_match_teams(best_fallback_match)
                logger.info(f"✓ Matched '{betfair_event_name}' with '{live_home} v {live_away}' by team names only (similarity: {best_fallback_similarity:.2f}, competition ID: {live_api_competition_id or 'N/A'})")
                self.match_cache[betfair_event_id] = str(best_fallback_match.get("id", ""))
                return best_fallback_match
            else:
                logger.debug(f"No team name match found in fallback for '{betfair_event_name}' (Betfair: '{betfair_home_team} v {betfair_away_team}')")
        
        return None
    
    def analyze_rejection_reason(self, betfair_event: Dict[str, Any], 
                                 live_matches: List[Dict[str, Any]],
                                 betfair_competition_name: str = "",
                                 betfair_to_live_mapping: Dict[int, str] = None) -> str:
        """Analyze why a Betfair event was not matched"""
        if not live_matches:
            return "No Live API matches available"
        
        betfair_competition_id = None
        if "competition" in betfair_event:
            comp_obj = betfair_event.get("competition", {})
            if isinstance(comp_obj, dict):
                betfair_competition_id = comp_obj.get("id")
        
        live_api_competition_id = None
        if betfair_competition_id and betfair_to_live_mapping:
            try:
                betfair_comp_id_int = int(betfair_competition_id)
                live_api_competition_id = betfair_to_live_mapping.get(betfair_comp_id_int)
            except (ValueError, TypeError):
                pass
        
        # Extract Betfair team names
        betfair_home_team = None
        betfair_away_team = None
        betfair_event_name = betfair_event.get("name", "")
        if betfair_event_name and " v " in betfair_event_name:
            try:
                parts = betfair_event_name.split(" v ", 1)
                betfair_home_team = parts[0].strip() if len(parts) > 0 else None
                betfair_away_team = parts[1].strip() if len(parts) > 1 else None
            except:
                pass
        
        competition_id_found = False
        competition_ids_in_live = set()
        time_match_found = False
        team_match_found = False
        
        for live_match in live_matches:
            try:
                live_competition = parse_match_competition(live_match)
                
                live_match_competition_id = None
                if live_competition and "_" in live_competition:
                    try:
                        parts = live_competition.split("_", 1)
                        live_match_competition_id = parts[0].strip()
                        if live_match_competition_id.isdigit():
                            competition_ids_in_live.add(live_match_competition_id)
                            
                            if live_api_competition_id and live_match_competition_id == live_api_competition_id:
                                competition_id_found = True
                    except:
                        pass
                
                # Check team names if competition ID matches
                if competition_id_found and betfair_home_team and betfair_away_team:
                    live_home_team, live_away_team = parse_match_teams(live_match)
                    if self.match_teams(betfair_home_team, betfair_away_team, live_home_team, live_away_team):
                        team_match_found = True
                
                betfair_time = None
                if "startTime" in betfair_event:
                    try:
                        betfair_time = datetime.fromisoformat(betfair_event["startTime"].replace("Z", "+00:00"))
                    except:
                        pass
                
                live_time = None
                if "kickoff" in live_match or "start_time" in live_match:
                    try:
                        time_str = live_match.get("kickoff") or live_match.get("start_time")
                        live_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except:
                        pass
                
                time_match = self.match_time(betfair_time, live_time, tolerance_minutes=30)
                if time_match:
                    time_match_found = True
                    
            except Exception as e:
                logger.debug(f"Error analyzing rejection for live match: {str(e)}")
                continue
        
        reasons = []
        if not betfair_competition_id:
            reasons.append("Betfair competition ID not available")
        elif not live_api_competition_id:
            reasons.append(f"No Live API competition ID mapping found for Betfair competition ID {betfair_competition_id}")
        elif not competition_id_found:
            if competition_ids_in_live:
                reasons.append(f"Live API competition ID mismatch (Expected: {live_api_competition_id}, Found in Live API: {', '.join(sorted(list(competition_ids_in_live))[:5])}{'...' if len(competition_ids_in_live) > 5 else ''})")
            else:
                reasons.append(f"Live API competition ID {live_api_competition_id} not found in Live API matches")
        elif betfair_home_team and betfair_away_team and not team_match_found:
            # Competition ID found but team names don't match
            # Find potential matches and calculate similarity scores
            # Only show matches with reasonable similarity (> 0.3) to avoid confusion
            best_match_info = None
            best_similarity = 0.0
            potential_teams = []
            min_similarity_threshold = 0.3  # Only consider matches with at least 30% similarity
            
            for live_match in live_matches:
                try:
                    live_competition = parse_match_competition(live_match)
                    live_match_competition_id = None
                    if live_competition and "_" in live_competition:
                        parts = live_competition.split("_", 1)
                        live_match_competition_id = parts[0].strip()
                        if live_match_competition_id.isdigit() and live_match_competition_id == live_api_competition_id:
                            live_home, live_away = parse_match_teams(live_match)
                            
                            # Calculate similarity for this match
                            home_sim = self.calculate_team_similarity(betfair_home_team, live_home)
                            away_sim = self.calculate_team_similarity(betfair_away_team, live_away)
                            swapped_home_sim = self.calculate_team_similarity(betfair_home_team, live_away)
                            swapped_away_sim = self.calculate_team_similarity(betfair_away_team, live_home)
                            
                            # Use best similarity (normal or swapped)
                            normal_avg = (home_sim + away_sim) / 2
                            swapped_avg = (swapped_home_sim + swapped_away_sim) / 2
                            match_sim = max(normal_avg, swapped_avg)
                            
                            # Only consider matches with reasonable similarity
                            if match_sim > best_similarity and match_sim >= min_similarity_threshold:
                                best_similarity = match_sim
                                best_match_info = {
                                    "live_home": live_home,
                                    "live_away": live_away,
                                    "home_sim": home_sim,
                                    "away_sim": away_sim,
                                    "swapped_home_sim": swapped_home_sim,
                                    "swapped_away_sim": swapped_away_sim,
                                    "swapped": swapped_avg > normal_avg
                                }
                            
                            # Only add to potential teams if similarity is reasonable
                            if match_sim >= min_similarity_threshold:
                                potential_teams.append(f"{live_home} v {live_away}")
                                if len(potential_teams) >= 3:  # Limit to 3 examples
                                    break
                except:
                    pass
            
            if best_match_info:
                # Show detailed team name comparison
                if best_match_info['swapped']:
                    reason_detail = f"Team names mismatch: Betfair '{betfair_home_team}' vs Live '{best_match_info['live_away']}' (sim: {best_match_info['swapped_home_sim']:.2f}), Betfair '{betfair_away_team}' vs Live '{best_match_info['live_home']}' (sim: {best_match_info['swapped_away_sim']:.2f})"
                else:
                    reason_detail = f"Team names mismatch: Betfair '{betfair_home_team}' vs Live '{best_match_info['live_home']}' (sim: {best_match_info['home_sim']:.2f}), Betfair '{betfair_away_team}' vs Live '{best_match_info['live_away']}' (sim: {best_match_info['away_sim']:.2f})"
                reasons.append(reason_detail)
            elif potential_teams:
                reasons.append(f"Team names mismatch (Betfair: '{betfair_home_team} v {betfair_away_team}', Live API potential matches: {', '.join(potential_teams)})")
            else:
                # No matches found with reasonable similarity - check if there are any matches in this competition at all
                all_teams_in_competition = []
                for live_match in live_matches:
                    try:
                        live_competition = parse_match_competition(live_match)
                        live_match_competition_id = None
                        if live_competition and "_" in live_competition:
                            parts = live_competition.split("_", 1)
                            live_match_competition_id = parts[0].strip()
                            if live_match_competition_id.isdigit() and live_match_competition_id == live_api_competition_id:
                                live_home, live_away = parse_match_teams(live_match)
                                all_teams_in_competition.append(f"{live_home} v {live_away}")
                                if len(all_teams_in_competition) >= 5:  # Limit to 5 examples
                                    break
                    except:
                        pass
                
                if all_teams_in_competition:
                    # Check if there's a time-based match (maybe the match hasn't started yet or team names are different)
                    betfair_time_str = ""
                    if betfair_event.get("startTime"):
                        try:
                            betfair_time = datetime.fromisoformat(betfair_event["startTime"].replace("Z", "+00:00"))
                            betfair_time_str = f" (kickoff: {betfair_time.strftime('%H:%M')})"
                        except:
                            pass
                    
                    # Event exists in Betfair but not in Live API (not live yet or finished)
                    # Show available matches in this competition for reference
                    reasons.append(f"Event not live in Live API (Betfair: '{betfair_home_team} v {betfair_away_team}'{betfair_time_str}, Live API matches in this competition: {', '.join(all_teams_in_competition)})")
                else:
                    reasons.append(f"Event not live in Live API (Betfair: '{betfair_home_team} v {betfair_away_team}', no live matches found in Live API for this competition ID {live_api_competition_id})")
        
        if betfair_event.get("startTime") and not time_match_found:
            reasons.append("Kick-off time mismatch (no matches within 30 minutes)")
        
        if not reasons:
            return "Unknown reason"
        
        return "; ".join(reasons)
    
    def clear_cache(self):
        """Clear the match cache"""
        self.match_cache.clear()
        logger.info("Match cache cleared")
    
    def get_cache_size(self) -> int:
        """Get current cache size"""
        return len(self.match_cache)

