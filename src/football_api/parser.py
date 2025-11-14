"""
Live Score API Parser
Parse API responses to extract match data (score, minute, goals, etc.)
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("BetfairBot")


def parse_match_score(match_data: Dict[str, Any]) -> str:
    """
    Parse current score from match data
    
    According to API documentation, score format is: "0 - 1" (with spaces)
    
    Args:
        match_data: Match data dictionary from API
    
    Returns:
        Score string in format "home_score-away_score" (e.g., "2-1", "0-0")
    """
    try:
        # API format: scores.score = "0 - 1" (with spaces and dashes)
        if "scores" in match_data and isinstance(match_data["scores"], dict):
            score_str = match_data["scores"].get("score", "")
            if score_str:
                # Parse "0 - 1" format
                parts = score_str.replace(" ", "").split("-")
                if len(parts) == 2:
                    try:
                        home_score = int(parts[0])
                        away_score = int(parts[1])
                        return f"{home_score}-{away_score}"
                    except ValueError:
                        pass
        
        # Fallback: try other formats
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
        
        # Default to 0-0 if not found
        if home_score is None:
            home_score = 0
        if away_score is None:
            away_score = 0
        
        return f"{home_score}-{away_score}"
        
    except Exception as e:
        logger.warning(f"Error parsing match score: {str(e)}")
        return "0-0"


def parse_match_minute(match_data: Dict[str, Any]) -> int:
    """
    Parse current match minute from match data
    
    According to API documentation, time field can be:
    - Number string: "43" (current minute)
    - "HT" (half time break)
    - "FT" (finished, 90 minutes)
    - "AET" (after extra time, 120 minutes)
    - "AP" (after penalties)
    
    Args:
        match_data: Match data dictionary from API
    
    Returns:
        Current minute (0-90+), or -1 if not found/not live
    """
    try:
        # API format: time = "43" (string) or "HT", "FT", "AET", "AP"
        time_str = match_data.get("time", "")
        
        if not time_str:
            return -1
        
        # Handle special statuses
        time_str_upper = str(time_str).upper().strip()
        if time_str_upper == "HT":
            return 45  # Half time
        elif time_str_upper == "FT":
            return 90  # Full time
        elif time_str_upper == "AET":
            return 120  # After extra time
        elif time_str_upper == "AP":
            return 120  # After penalties (treat as 120)
        
        # Check status first - if NOT STARTED, return -1 immediately
        status = match_data.get("status", "").upper()
        if "NOT STARTED" in status or "SCHEDULED" in status or "POSTPONED" in status:
            return -1  # Match not started yet
        
        # Try to parse as integer
        try:
            minute = int(time_str)
            # Validate minute is reasonable (0-120 for football matches)
            if 0 <= minute <= 120:
                return minute
            else:
                # If minute > 120, might be kickoff time (e.g., 1030 = 10:30)
                # Check if it looks like time format (4 digits)
                if len(str(time_str)) == 4 and minute > 1000:
                    logger.debug(f"Time field '{time_str}' appears to be kickoff time, not current minute")
                    return -1
                return minute  # Still return it but log warning
        except ValueError:
            # Try to extract number from string
            minute_str = ''.join(filter(str.isdigit, str(time_str)))
            if minute_str:
                minute = int(minute_str)
                # Validate minute is reasonable
                if 0 <= minute <= 120:
                    return minute
                # If > 120, might be kickoff time
                if len(minute_str) == 4 and minute > 1000:
                    logger.debug(f"Time field '{time_str}' appears to be kickoff time, not current minute")
                    return -1
        
        # Check status to determine if live
        if status == "IN PLAY" or "LIVE" in status:
            return 0  # Live but minute not available, return 0 as default
        
        return -1  # Not live or minute not found
        
    except Exception as e:
        logger.warning(f"Error parsing match minute: {str(e)}")
        return -1


def parse_goals_timeline(match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse goal timeline from match data
    
    Args:
        match_data: Match data dictionary from API
    
    Returns:
        List of goal dictionaries with structure:
        [
            {
                "minute": 45,
                "team": "home" or "away",
                "player": "Player Name" (optional),
                "cancelled": False (optional, for VAR)
            },
            ...
        ]
    """
    goals = []
    
    try:
        # Try different possible field names for goals
        goals_data = None
        
        if "goals" in match_data:
            goals_data = match_data["goals"]
        elif "events" in match_data:
            # Filter for goal events
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
                
                # Parse minute
                minute = goal_data.get("minute") or goal_data.get("time") or goal_data.get("min")
                if isinstance(minute, str):
                    minute = ''.join(filter(str.isdigit, minute))
                    minute = int(minute) if minute else None
                goal["minute"] = int(minute) if minute is not None else 0
                
                # Parse team (home or away)
                team = goal_data.get("team", "").lower()
                if "home" in team or goal_data.get("is_home", False):
                    goal["team"] = "home"
                elif "away" in team or goal_data.get("is_away", False):
                    goal["team"] = "away"
                else:
                    # Try to determine from player or other fields
                    goal["team"] = "home"  # Default
                
                # Parse player name (optional)
                if "player" in goal_data:
                    goal["player"] = goal_data["player"]
                elif "player_name" in goal_data:
                    goal["player"] = goal_data["player_name"]
                
                # Parse cancelled status (VAR)
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
    """
    Parse team names from match data
    
    According to API documentation:
    - home: object with "name" field
    - away: object with "name" field
    
    Args:
        match_data: Match data dictionary from API
    
    Returns:
        Tuple of (home_team_name, away_team_name)
    """
    try:
        home_team = None
        away_team = None
        
        # API format: home.name and away.name
        if "home" in match_data and isinstance(match_data["home"], dict):
            home_team = match_data["home"].get("name")
        
        if "away" in match_data and isinstance(match_data["away"], dict):
            away_team = match_data["away"].get("name")
        
        # Fallback: try other formats
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
        
        # Default values
        if not home_team:
            home_team = "Home Team"
        if not away_team:
            away_team = "Away Team"
        
        return (home_team, away_team)
        
    except Exception as e:
        logger.warning(f"Error parsing team names: {str(e)}")
        return ("Home Team", "Away Team")


def parse_match_competition(match_data: Dict[str, Any]) -> str:
    """
    Parse competition/league name from match data
    Returns format: "ID_Name" (e.g., "4_Serie A") if ID is available, otherwise just "Name"
    
    According to API documentation:
    - competition: object with "id" and "name" fields
    
    Args:
        match_data: Match data dictionary from API
    
    Returns:
        Competition in format "ID_Name" if ID available, or just "Name" if no ID, or empty string if not found
    """
    try:
        competition_name = None
        competition_id = None
        
        # API format: competition.id and competition.name
        if "competition" in match_data:
            comp_obj = match_data["competition"]
            if isinstance(comp_obj, dict):
                competition_id = comp_obj.get("id")
                competition_name = comp_obj.get("name")
        
        # Fallback: try other formats
        if not competition_name:
            if "league" in match_data:
                competition_name = match_data["league"]
            elif "competition_name" in match_data:
                competition_name = match_data["competition_name"]
            elif "league_name" in match_data:
                competition_name = match_data["league_name"]
            elif "tournament" in match_data:
                competition_name = match_data["tournament"]
            
            # If competition is a dict, get name and id
            if isinstance(competition_name, dict):
                competition_id = competition_name.get("id")
                competition_name = competition_name.get("name") or competition_name.get("title")
        
        if not competition_name:
            return ""
        
        # Return format: "ID_Name" if ID is available, otherwise just "Name"
        if competition_id:
            return f"{competition_id}_{competition_name}"
        else:
            return competition_name
        
    except Exception as e:
        logger.warning(f"Error parsing competition name: {str(e)}")
        return ""

