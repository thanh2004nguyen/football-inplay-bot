"""
Qualification Logic Module
Determines if a match qualifies for betting based on goals in 60-74 minute window
Handles VAR (cancelled goals) and 0-0 exception
Also handles early discard if match is out of target at minute 60 (based on Excel targets)
"""
import logging
import pandas as pd
import re
from typing import List, Dict, Any, Tuple, Set, Optional
from config.competition_mapper import normalize_text

logger = logging.getLogger("BetfairBot")

# Cache for competition maps (competition_name -> {targets, min_odds, stake, competition_id})
_competition_map_cache: Dict[str, Dict[str, Any]] = {}
_competition_id_map_cache: Dict[str, str] = {}  # {competition_id: competition_name}
_excel_path_cache: Optional[str] = None


def normalize_score(score: str) -> str:
    """
    Normalize score format for comparison
    - Remove spaces
    - Convert ':' to '-'
    - Strip whitespace
    
    Args:
        score: Score string (e.g., "1 : 0", "1-0", "2:1")
    
    Returns:
        Normalized score (e.g., "1-0", "2-1")
    """
    if not score:
        return ""
    # Remove spaces, convert : to -, strip
    normalized = score.strip().replace(" ", "").replace(":", "-")
    return normalized


def filter_cancelled_goals(goals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out cancelled goals (VAR)
    
    Args:
        goals: List of goal dictionaries
    
    Returns:
        List of valid (non-cancelled) goals
    """
    valid_goals = []
    
    for goal in goals:
        cancelled = goal.get('cancelled', False)
        
        # Handle string values
        if isinstance(cancelled, str):
            cancelled = cancelled.lower() in ['true', 'yes', '1', 'cancelled']
        
        if not cancelled:
            valid_goals.append(goal)
        else:
            minute = goal.get('minute', 'N/A')
            logger.debug(f"Filtered out cancelled goal at minute {minute} (VAR)")
    
    return valid_goals


def check_goal_in_window(goals: List[Dict[str, Any]], start_minute: int, end_minute: int) -> bool:
    """
    Check if there's a valid goal in the specified minute window
    
    Args:
        goals: List of goal dictionaries (should already be filtered for cancelled)
        start_minute: Start of window (e.g., 60)
        end_minute: End of window (e.g., 74)
    
    Returns:
        True if there's at least one goal in the window, False otherwise
    """
    for goal in goals:
        minute = goal.get('minute', 0)
        if start_minute <= minute <= end_minute:
            return True
    
    return False


def check_zero_zero_exception(score: str, current_minute: int, 
                             competition_name: str,
                             zero_zero_exception_competitions: Set[str],
                             excel_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Check if 0-0 exception applies
    
    Special case: If 0-0 is in the target list (from Excel) and the match is 0-0 
    at minute 60, then the match should be considered a target immediately (it should get the green dot),
    even if no goal has been scored between 60 and 74 yet.
    
    Per client requirement:
    - If 0-0 is in target list and match is 0-0 at minute 60: match stays TARGET (TRACKING) 
      even if no goal is scored between 60-74
    - At minute 75, if still 0-0 and all other conditions OK, it becomes TARGET (READY_FOR_BET)
    - A match should be "Disqualified (no goal in 60-74, no 0-0 exception)" only when 
      0-0 is NOT in the target list
    
    Args:
        score: Current score (e.g., "0-0", "1-0")
        current_minute: Current match minute
        competition_name: Competition name
        zero_zero_exception_competitions: Set of competitions with 0-0 exception (fallback)
        excel_path: Path to Excel file (to check if 0-0 is in targets)
    
    Returns:
        (is_qualified, reason)
    """
    # Check if score is 0-0
    if score != "0-0":
        return False, "Score is not 0-0"
    
    # Check if in 60-74 minute window
    if not (60 <= current_minute <= 74):
        return False, f"Not in 60-74 window (current: {current_minute})"
    
    # Special case: If 0-0 is in targets (from Excel), qualify immediately
    # This applies for the entire 60-74 window, not just minute 60
    # Per client requirement: If 0-0 is in target list and match is 0-0 at minute 60,
    # match stays TARGET (TRACKING) even if no goal is scored between 60-74
    if excel_path:
        from logic.qualification import get_competition_targets, normalize_score
        target_scores = get_competition_targets(competition_name, excel_path)
        if target_scores:
            normalized_targets = {normalize_score(t) for t in target_scores}
            normalized_score = normalize_score(score)
            if normalized_score in normalized_targets:
                logger.info(f"0-0 exception: score 0-0 is in targets for '{competition_name}' at minute {current_minute}")
                return True, "0-0 exception (score in targets)"
    
    # Check if competition is in exception list (fallback for old logic)
    if competition_name in zero_zero_exception_competitions:
        logger.info(f"0-0 exception applies for '{competition_name}' at minute {current_minute}")
        return True, "0-0 exception (competition allowed)"
    else:
        logger.debug(f"0-0 score but competition '{competition_name}' not in exception list and 0-0 not in targets")
        return False, "0-0 but competition not in exception list and 0-0 not in targets"


def is_score_reached_in_window(current_score: str, score_at_minute_60: Optional[str],
                               goals: List[Dict[str, Any]], start_minute: int, end_minute: int,
                               var_check_enabled: bool = True,
                               score_after_goal_in_window: Optional[str] = None) -> bool:
    """
    Check if current score was reached by a goal scored between start_minute and end_minute (inclusive)
    
    This function determines if the current score is different from the score at minute 60,
    and if that change was caused by a goal in the 60-74 window.
    
    Args:
        current_score: Current score (e.g., "2-1")
        score_at_minute_60: Score at minute 60 (None if not yet at minute 60)
        goals: List of all goals (may include cancelled)
        start_minute: Start of goal detection window (e.g., 60)
        end_minute: End of goal detection window (e.g., 74)
        var_check_enabled: Whether to filter cancelled goals
        score_after_goal_in_window: Score after goal in 60-74 window (if available, more accurate)
    
    Returns:
        True if score was reached by a goal in the window, False otherwise
    """
    # Filter cancelled goals if VAR check is enabled
    if var_check_enabled:
        valid_goals = filter_cancelled_goals(goals)
    else:
        valid_goals = goals
    
    # If we have score_after_goal_in_window, use it for more accurate check
    if score_after_goal_in_window is not None:
        # If current score matches the score after goal in window, it was reached in the window
        if current_score == score_after_goal_in_window:
            return True
        # If current score is different, it might have changed after the window (goal after 74)
        # So it was NOT reached in the window
        return False
    
    # Fallback: If we don't have score_after_goal_in_window, use less accurate method
    # If we don't have score at minute 60, we can't determine if score was reached in window
    if score_at_minute_60 is None:
        return False
    
    # If current score is same as score at minute 60, it was NOT reached in the window
    if current_score == score_at_minute_60:
        return False
    
    # Check if there's a goal in the window that could have changed the score
    goals_in_window = [g for g in valid_goals if start_minute <= g.get('minute', 0) <= end_minute]
    
    if not goals_in_window:
        return False
    
    # If there are goals in the window and score changed, we assume it was reached in the window
    # This is less accurate but works if we don't have score_after_goal_in_window
    return True


def load_competition_map_from_excel(excel_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load competition map from Excel: competition -> {targets, min_odds, stake}
    Cache the result in memory
    
    Args:
        excel_path: Path to Excel file
    
    Returns:
        Dictionary: {competition_name: {"targets": Set[str], "min_odds": float, "stake": float}}
    """
    global _competition_map_cache, _excel_path_cache
    
    # Return cached if same Excel file
    if _excel_path_cache == excel_path and _competition_map_cache:
        return _competition_map_cache
    
    try:
        # Read Excel with dtype=str for Result column to prevent auto-parsing
        # This ensures "1-2" stays as "1-2" and doesn't become a date or number
        df = pd.read_excel(excel_path, dtype={'Result': str})
        
        has_competition_live = 'Competition-Live' in df.columns
        has_competition_old = 'Competition' in df.columns
        
        if not has_competition_live and not has_competition_old:
            logger.warning(f"Neither 'Competition-Live' nor 'Competition' column found in Excel file")
            return {}
        
        if 'Result' not in df.columns:
            logger.warning(f"Column 'Result' not found in Excel file")
            return {}
        
        # Check for Min_Odds and Stake columns (optional)
        has_min_odds = 'Min_Odds' in df.columns or 'Min Odds' in df.columns
        min_odds_column = 'Min_Odds' if 'Min_Odds' in df.columns else ('Min Odds' if 'Min Odds' in df.columns else None)
        has_stake = 'Stake' in df.columns
        
        competition_map = {}  # {competition_name: {targets, min_odds, stake, competition_id}}
        competition_id_map = {}  # {competition_id: competition_name} for ID-based matching
        
        # Check if Competition-Betfair column exists (for ID matching)
        has_competition_betfair = 'Competition-Betfair' in df.columns
        
        # Process each row
        for idx, row in df.iterrows():
            # Get competition name (priority: Competition-Live, then Competition)
            competition_name = None
            competition_id_from_excel = None
            
            if has_competition_live and pd.notna(row.get('Competition-Live')):
                competition_name = str(row['Competition-Live']).strip()
            elif has_competition_old and pd.notna(row.get('Competition')):
                competition_name = str(row['Competition']).strip()
            
            # Get Competition-Betfair for ID matching
            if has_competition_betfair and pd.notna(row.get('Competition-Betfair')):
                betfair_comp = str(row['Competition-Betfair']).strip()
                # Extract ID if format is "ID_Name"
                if "_" in betfair_comp:
                    try:
                        parts = betfair_comp.split("_", 1)
                        competition_id_from_excel = parts[0].strip()
                        # Use Competition-Betfair name if Competition-Live/Competition not available
                        if not competition_name:
                            competition_name = betfair_comp
                    except:
                        if not competition_name:
                            competition_name = betfair_comp
                else:
                    if not competition_name:
                        competition_name = betfair_comp
            
            if not competition_name:
                continue
            
            # Get Result (normalized)
            result = None
            if pd.notna(row.get('Result')):
                # Convert to string first to avoid Excel auto-parsing numbers/dates
                raw_result = row.get('Result')
                # If it's a number (Excel parsed it), convert back to string format
                if isinstance(raw_result, (int, float)):
                    # This shouldn't happen for scores, but handle it
                    logger.warning(f"Excel Result column contains number instead of string: {raw_result} (row {idx})")
                    result = None
                else:
                    raw_str = str(raw_result).strip()
                    result = normalize_score(raw_str)
                    # Debug: Log if we see suspicious values
                    if result and len(result) > 3 and result.count("-") == 1:
                        # Check if it looks like a valid score (e.g., "1-2", "0-0", "2-1")
                        parts = result.split("-")
                        if len(parts) == 2:
                            try:
                                home = int(parts[0])
                                away = int(parts[1])
                                # Valid score format
                            except ValueError:
                                # Invalid format - log warning
                                logger.warning(f"Excel Result '{raw_str}' normalized to '{result}' - suspicious format (row {idx}, competition: {competition_name})")
            
            if not result:
                continue
            
            # Get Min_Odds (optional)
            min_odds = None
            if has_min_odds and min_odds_column and pd.notna(row.get(min_odds_column)):
                try:
                    min_odds = float(row[min_odds_column])
                except (ValueError, TypeError):
                    pass
            
            # Get Stake (optional)
            stake = None
            if has_stake and pd.notna(row.get('Stake')):
                try:
                    stake = float(row['Stake'])
                except (ValueError, TypeError):
                    pass
            
            # Add to map
            if competition_name not in competition_map:
                competition_map[competition_name] = {
                    "targets": set(),
                    "min_odds": min_odds,
                    "stake": stake,
                    "competition_id": competition_id_from_excel
                }
            
            competition_map[competition_name]["targets"].add(result)
            
            # Also create ID mapping if we have ID
            if competition_id_from_excel:
                competition_id_map[competition_id_from_excel] = competition_name
        
        # Cache the result (include ID map in cache)
        _competition_map_cache = competition_map
        _competition_id_map_cache = competition_id_map
        _excel_path_cache = excel_path
        
        # Log removed - not needed
        return competition_map
        
    except FileNotFoundError:
        logger.warning(f"Excel file not found: {excel_path}")
        return {}
    except Exception as e:
        logger.error(f"Error loading competition map from Excel: {str(e)}")
        return {}


def get_competition_targets(competition_name: str, excel_path: str, competition_id: Optional[str] = None) -> Set[str]:
    """
    Get target scores for a competition from cached map
    Supports both "ID_Name" format and "Name" format
    Also supports matching by competition ID if provided
    
    Args:
        competition_name: Competition name (e.g., "79_Segunda Division" or "Segunda Division")
        excel_path: Path to Excel file
        competition_id: Optional competition ID from Betfair (for ID-based matching)
    
    Returns:
        Set of normalized target scores
    """
    # Load map if not cached
    competition_map = load_competition_map_from_excel(excel_path)
    
    if not competition_map:
        return set()
    
    # Try matching by ID first (most accurate)
    if competition_id:
        # Check if ID is in cached ID map
        global _competition_id_map_cache
        if competition_id in _competition_id_map_cache:
            excel_comp_name = _competition_id_map_cache[competition_id]
            if excel_comp_name in competition_map:
                logger.debug(f"Matched competition by ID: {competition_id} -> {excel_comp_name}")
                return competition_map[excel_comp_name]["targets"]
        
        # Also try matching ID in competition_map directly
        for excel_comp_name, comp_data in competition_map.items():
            excel_comp_id = comp_data.get("competition_id")
            if excel_comp_id and str(excel_comp_id) == str(competition_id):
                logger.debug(f"Matched competition by ID in map: {competition_id} -> {excel_comp_name}")
                return comp_data["targets"]
            
            # Try matching "ID_Name" format
            if "_" in excel_comp_name:
                try:
                    excel_parts = excel_comp_name.split("_", 1)
                    excel_id = excel_parts[0].strip()
                    if str(excel_id) == str(competition_id):
                        logger.debug(f"Matched competition by ID in name format: {competition_id} -> {excel_comp_name}")
                        return comp_data["targets"]
                except:
                    pass
    
    # Normalize competition name for matching
    normalized_competition = normalize_text(competition_name)
    
    # Extract ID and name if format is "ID_Name"
    competition_id_from_name = None
    competition_name_only = competition_name
    if "_" in competition_name:
        parts = competition_name.split("_", 1)
        try:
            competition_id_from_name = parts[0].strip()
            competition_name_only = parts[1].strip()
        except:
            pass
    
    # Try exact match first
    if competition_name in competition_map:
        return competition_map[competition_name]["targets"]
    
    # Try normalized match
    for excel_comp_name, comp_data in competition_map.items():
        if normalize_text(excel_comp_name) == normalized_competition:
            return comp_data["targets"]
        
        # If competition_name is "ID_Name" format, try matching just the name part
        if competition_id_from_name and competition_name_only:
            if excel_comp_name == f"{competition_id_from_name}_{competition_name_only}":
                return comp_data["targets"]
            if normalize_text(excel_comp_name) == normalize_text(competition_name_only):
                return comp_data["targets"]
            
            # If Excel has "ID_Name" format, extract and match name part
            if "_" in excel_comp_name:
                try:
                    excel_parts = excel_comp_name.split("_", 1)
                    excel_name = excel_parts[1].strip()
                    if normalize_text(excel_name) == normalize_text(competition_name_only):
                        return comp_data["targets"]
                except:
                    pass
    
    logger.debug(f"No competition match found for: {competition_name} (ID: {competition_id})")
    return set()


def get_excel_targets_for_competition(competition_name: str, excel_path: str) -> Set[str]:
    """
    Get all Result (score) targets from Excel for a specific competition
    Supports both old format (Competition column) and new format (Competition-Live column)
    Uses cached map for better performance
    
    Args:
        competition_name: Competition name from Live Score API (will be matched with Competition-Live or Competition)
        excel_path: Path to Excel file
    
    Returns:
        Set of Result values (scores) available for this competition, empty set if not found
    """
    # Use new cached function
    return get_competition_targets(competition_name, excel_path)


def get_possible_scores_after_one_goal(current_score: str) -> Set[str]:
    """
    Get all possible scores after one more goal is scored
    
    Args:
        current_score: Current score (e.g., "1-1", "0-0", "2-1")
    
    Returns:
        Set of possible scores after one goal (e.g., {"2-1", "1-2"} for "1-1")
    """
    try:
        parts = current_score.split("-")
        if len(parts) != 2:
            return set()
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        
        # One goal can be scored by home team or away team
        possible_scores = {
            f"{home_goals + 1}-{away_goals}",  # Home team scores
            f"{home_goals}-{away_goals + 1}"   # Away team scores
        }
        
        return possible_scores
        
    except (ValueError, IndexError) as e:
        logger.warning(f"Error parsing score '{current_score}': {str(e)}")
        return set()


def calculate_max_goals_needed(current_score: str, target_scores: Set[str]) -> int:
    """
    Calculate the minimum number of goals needed to reach any target score from current score.
    
    For each target score, calculate the minimum number of goals required to reach it.
    Returns the maximum of these minimums (worst case scenario).
    
    Example:
    - Current: "1-0", Targets: {"1-3", "2-1"}
    - To reach "1-3": need 3 goals (0 home + 3 away)
    - To reach "2-1": need 1 goal (1 home + 0 away)
    - Max: 3 goals
    
    Args:
        current_score: Current score (e.g., "1-0", "0-0")
        target_scores: Set of target scores (e.g., {"1-3", "2-1"})
    
    Returns:
        Maximum number of goals needed to reach any target (minimum 1, default 2 if no targets)
    """
    if not target_scores:
        return 2  # Default fallback
    
    try:
        parts = current_score.split("-")
        if len(parts) != 2:
            return 2  # Default fallback
        
        current_home = int(parts[0].strip())
        current_away = int(parts[1].strip())
        
        max_goals_needed = 0  # Start from 0, will be updated if any reachable target found
        
        for target_score in target_scores:
            try:
                target_parts = normalize_score(target_score).split("-")
                if len(target_parts) != 2:
                    continue
                
                target_home = int(target_parts[0].strip())
                target_away = int(target_parts[1].strip())
                
                # Check if target is reachable (target >= current for both home and away)
                # We can only add goals, not subtract them
                if target_home < current_home or target_away < current_away:
                    # Target is not reachable (would require reducing goals, which is impossible)
                    continue
                
                # Calculate goals needed for this target
                home_goals_needed = target_home - current_home
                away_goals_needed = target_away - current_away
                total_goals_needed = home_goals_needed + away_goals_needed
                
                # Update max if this target needs more goals
                if total_goals_needed > max_goals_needed:
                    max_goals_needed = total_goals_needed
                    
            except (ValueError, IndexError):
                continue
        
        # If no reachable targets found, return 0 (shouldn't happen in practice)
        # Otherwise, ensure at least 1 goal if max_goals_needed is 0 (current score already matches a target)
        # Cap at reasonable limit (e.g., 5 goals) to avoid excessive computation
        if max_goals_needed == 0:
            # Current score already matches a target, but we're checking if we can reach OTHER targets
            # Return 1 as minimum to check if we can reach any other target
            return 1
        return min(max_goals_needed, 5)
        
    except (ValueError, IndexError) as e:
        logger.warning(f"Error calculating max goals needed for score '{current_score}': {str(e)}")
        return 2  # Default fallback


def get_possible_scores_after_multiple_goals(current_score: str, max_goals: int = 2) -> Set[str]:
    """
    Get all possible scores after multiple goals (up to max_goals) are scored
    
    This function considers all reasonable possible scorelines that could occur
    between minute 60 and 75, including:
    - +1 goal scenarios
    - +2 goals scenarios
    - (optionally +3 goals if max_goals >= 3)
    
    Example: If current score is "1-1" and max_goals=2:
    - After 1 goal: {"2-1", "1-2"}
    - After 2 goals: {"3-1", "1-3", "2-2"}
    - Total: {"2-1", "1-2", "3-1", "1-3", "2-2"}
    
    Args:
        current_score: Current score (e.g., "1-1", "0-0", "2-1")
        max_goals: Maximum number of goals to consider (default: 2)
    
    Returns:
        Set of all possible scores after 1 to max_goals goals
    """
    try:
        parts = current_score.split("-")
        if len(parts) != 2:
            return set()
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        
        all_possible_scores = set()
        
        # Generate all possible score combinations for 1 to max_goals goals
        # For each number of goals (1 to max_goals), consider all ways to distribute them
        for total_goals_to_add in range(1, max_goals + 1):
            # For each distribution of goals (home goals + away goals = total_goals_to_add)
            for home_goals_to_add in range(total_goals_to_add + 1):
                away_goals_to_add = total_goals_to_add - home_goals_to_add
                
                new_home = home_goals + home_goals_to_add
                new_away = away_goals + away_goals_to_add
                
                possible_score = f"{new_home}-{new_away}"
                all_possible_scores.add(possible_score)
        
        return all_possible_scores
        
    except (ValueError, IndexError) as e:
        logger.warning(f"Error parsing score '{current_score}': {str(e)}")
        return set()


def is_impossible_match_at_60(score: str, competition_name: str, excel_path: str, current_minute: int = 60) -> Tuple[bool, str]:
    """
    Check if match is "impossible" from minute 0 to 60 - can never return to target results
    
    Strict logic: A match is impossible if:
    1. Current score already has more goals than allowed by Excel targets, OR
    2. Current score + 1 goal would push it permanently out of ALL target results
    
    This is stricter than is_out_of_target - it checks if even a single goal would
    make the match permanently invalid for all target results.
    
    Args:
        score: Current score (e.g., "2-1", "0-0")
        competition_name: Competition name (for Excel lookup)
        excel_path: Path to Excel file (Competitions_Results_Odds_Stake.xlsx)
        current_minute: Current minute (0-60)
    
    Returns:
        (is_impossible, reason)
    """
    try:
        # Parse score
        parts = score.split("-")
        if len(parts) != 2:
            return False, "Invalid score format"
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        
        # Get Excel targets
        excel_targets = get_excel_targets_for_competition(competition_name, excel_path)
        if not excel_targets:
            logger.debug(f"is_impossible_match_at_60: No Excel targets found for competition '{competition_name}' at path '{excel_path}'")
            return False, "No Excel targets available"
        
        # Normalize current score
        normalized_current = normalize_score(score)
        
        # Check 1: Current score already out of targets
        normalized_targets = {normalize_score(t) for t in excel_targets}
        logger.debug(f"is_impossible_match_at_60: Score '{score}' (normalized: '{normalized_current}'), Targets: {sorted(excel_targets)} (normalized: {sorted(normalized_targets)}), Competition: '{competition_name}'")
        if normalized_current not in normalized_targets:
            logger.debug(f"is_impossible_match_at_60: Score '{score}' is NOT in targets {sorted(excel_targets)} → IMPOSSIBLE")
            return True, f"Score {score} at minute {current_minute} is already out of targets {sorted(excel_targets)}"
        
        # Check 2: Current score + 1 goal would push it out of ALL targets
        # Get all possible scores after exactly 1 goal
        possible_after_1_goal = get_possible_scores_after_multiple_goals(score, max_goals=1)
        
        # Check if ANY score after 1 goal is still in targets
        matching_after_1_goal = possible_after_1_goal & normalized_targets
        
        if not matching_after_1_goal:
            # Even 1 goal would push it out of ALL targets → impossible
            return True, f"Score {score} at minute {current_minute}: after 1 goal, all possible scores {sorted(possible_after_1_goal)} are out of targets {sorted(excel_targets)}"
        
        # Match can still reach targets with 1 goal → not impossible
        return False, f"Score {score} at minute {current_minute}: can still reach targets {sorted(matching_after_1_goal)} with 1 goal"
        
    except Exception as e:
        logger.warning(f"Error checking impossible match: {str(e)}")
        return False, f"Error: {str(e)}"


def is_out_of_target(score: str, current_minute: int, target_over: float,
                    competition_name: Optional[str] = None,
                    excel_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Check if match is out of target from minute 0 to 60
    
    Logic (per client requirements):
    - If Excel targets are provided: Check if current score + 1 goal OR +2 goals can create any score in Excel targets
    - Between minute 60 and 75, there could be 1 goal or even more than one goal
    - Therefore, we check ALL reasonable possible scorelines after +1 goal and +2 goals
    - If not in Excel targets: Match is out of target and can be discarded early
    
    Fallback logic (if Excel not available):
    - Current total goals >= (target_over + 0.5) at minute 0-60
    - Current total goals = target_over at minute 0-60 (one goal would exceed target)
    
    Args:
        score: Current score (e.g., "2-1", "0-0")
        current_minute: Current match minute (0-60)
        target_over: Target Over X.5 value (e.g., 2.5 for Over 2.5)
        competition_name: Competition name (for Excel lookup)
        excel_path: Path to Excel file (Competitions_Results_Odds_Stake.xlsx)
    
    Returns:
        (is_out_of_target, reason)
    """
    if current_minute < 0 or current_minute > 60:
        return False, f"Not in range 0-60 (current: {current_minute})"
    
    try:
        # Parse score
        parts = score.split("-")
        if len(parts) != 2:
            return False, "Invalid score format"
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        total_goals = home_goals + away_goals
        
        # If Excel path and competition name provided, use Excel-based check
        if excel_path and competition_name:
            excel_targets = get_excel_targets_for_competition(competition_name, excel_path)
            
            if excel_targets:
                # Get possible scores after +1 goal and +2 goals (as per client request)
                # This considers all reasonable possible scorelines between minute 60 and 75
                possible_scores = get_possible_scores_after_multiple_goals(score, max_goals=2)
                
                # Check if any possible score is in Excel targets
                matching_scores = possible_scores & excel_targets
                
                if not matching_scores:
                    # None of the possible scores (after +1 or +2 goals) are in Excel targets → out of target
                    return True, f"Score {score} at minute {current_minute}: possible scores after +1/+2 goals {sorted(possible_scores)} are not in Excel targets {sorted(excel_targets)} for {competition_name}"
                else:
                    # At least one possible score is in Excel targets → still in target
                    return False, f"Score {score} at minute {current_minute}: at least one possible score {sorted(matching_scores)} is in Excel targets"
            else:
                # Excel file not found or competition not found → fallback to old logic
                logger.debug(f"Excel targets not available for {competition_name}, using fallback logic")
        
        # Fallback logic: Check based on target_over only
        # Check if already out of target (total goals >= target + 0.5)
        # For Over 2.5: if total >= 3, already out of target
        if total_goals >= int(target_over) + 1:
            return True, f"Score {score} ({total_goals} goals) already exceeds target Over {target_over} at minute {current_minute}"
        
        # Check if one goal would make it out of target
        # For Over 2.5: if total = 2, one goal would make it 3 (out of target)
        if total_goals == int(target_over):
            return True, f"Score {score} ({total_goals} goals) at target Over {target_over} - one goal in 60-74 would exceed target"
        
        return False, f"Score {score} ({total_goals} goals) still within target Over {target_over}"
        
    except (ValueError, IndexError) as e:
        logger.warning(f"Error parsing score '{score}': {str(e)}")
        return False, f"Error parsing score: {str(e)}"


def is_qualified(score: str, 
                goals: List[Dict[str, Any]],
                current_minute: int,
                start_minute: int,
                end_minute: int,
                competition_name: str,
                zero_zero_exception_competitions: Set[str],
                var_check_enabled: bool = True,
                target_over: Optional[float] = None,
                early_discard_enabled: bool = True,
                excel_path: Optional[str] = None,
                strict_discard_at_60: bool = False) -> Tuple[bool, str]:
    """
    Check if match is qualified for betting
    
    Args:
        score: Current score (e.g., "0-0", "2-1")
        goals: List of all goals (may include cancelled)
        current_minute: Current match minute
        start_minute: Start of goal detection window (e.g., 60)
        end_minute: End of goal detection window (e.g., 74)
        competition_name: Competition name
        zero_zero_exception_competitions: Set of competitions with 0-0 exception
        var_check_enabled: Whether to filter cancelled goals
        target_over: Target Over X.5 value (e.g., 2.5)
        early_discard_enabled: Whether to enable early discard at minute 60
        excel_path: Path to Excel file (for early discard check based on Excel targets)
        strict_discard_at_60: If True, use strict discard logic (impossible matches)
    
    Returns:
        (is_qualified, reason)
    """
    # Strict discard check from minute 0 to 60: remove "impossible" matches
    if strict_discard_at_60 and 0 <= current_minute <= 60 and excel_path and competition_name:
        impossible, reason = is_impossible_match_at_60(score, competition_name, excel_path, current_minute)
        if impossible:
            # Log removed
            return False, f"Impossible match: {reason}"
    
    # Early discard check: if from minute 0 to 60 and out of target, immediately disqualify
    if early_discard_enabled and target_over is not None and 0 <= current_minute <= 60:
        out_of_target, reason = is_out_of_target(score, current_minute, target_over, 
                                                competition_name, excel_path)
        if out_of_target:
            logger.info(f"Match out of target at minute 60: {reason}")
            return False, f"Out of target: {reason}"
    
    # Filter cancelled goals if VAR check is enabled
    if var_check_enabled:
        valid_goals = filter_cancelled_goals(goals)
    else:
        valid_goals = goals
    
    # Check 0-0 exception first (only if in window)
    if 60 <= current_minute <= 74:
        qualified, reason = check_zero_zero_exception(
            score, current_minute, competition_name, zero_zero_exception_competitions, excel_path
        )
        if qualified:
            return True, reason
        
        # Check if current score is in target scores (not just 0-0)
        # If score is already in targets at minute 60-74, qualify immediately
        # This handles cases like: score 1-0 @ 60' with targets [0-0, 1-0, 1-1] → qualify
        if excel_path and competition_name:
            target_scores = get_competition_targets(competition_name, excel_path)
            if target_scores:
                normalized_targets = {normalize_score(t) for t in target_scores}
                normalized_score = normalize_score(score)
                if normalized_score in normalized_targets:
                    logger.info(f"Score in targets: score {score} is in targets {sorted(target_scores)} for '{competition_name}' at minute {current_minute}")
                    return True, f"Score {score} is in targets {sorted(target_scores)}"
    
    # Check for goals in 60-74 window
    if check_goal_in_window(valid_goals, start_minute, end_minute):
        # Find the goal in the window
        goal_in_window = None
        for goal in valid_goals:
            minute = goal.get('minute', 0)
            if start_minute <= minute <= end_minute:
                goal_in_window = goal
                break
        
        if goal_in_window:
            minute = goal_in_window.get('minute', 'N/A')
            team = goal_in_window.get('team', 'N/A')
            return True, f"Goal in {start_minute}-{end_minute} window (minute {minute}, team: {team})"
    
    return False, "No qualification (no goal in window, no 0-0 exception)"

