"""
Qualification Logic Module
Determines if a match qualifies for betting based on goals in 60-74 minute window
Handles VAR (cancelled goals) and 0-0 exception
Also handles early discard if match is out of target at minute 60 (based on Excel targets)
"""
import logging
import pandas as pd
from typing import List, Dict, Any, Tuple, Set, Optional
from config.competition_mapper import normalize_text

logger = logging.getLogger("BetfairBot")


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
                             zero_zero_exception_competitions: Set[str]) -> Tuple[bool, str]:
    """
    Check if 0-0 exception applies
    
    Args:
        score: Current score (e.g., "0-0", "1-0")
        current_minute: Current match minute
        competition_name: Competition name
        zero_zero_exception_competitions: Set of competitions with 0-0 exception
    
    Returns:
        (is_qualified, reason)
    """
    # Check if score is 0-0
    if score != "0-0":
        return False, "Score is not 0-0"
    
    # Check if in 60-74 minute window
    if not (60 <= current_minute <= 74):
        return False, f"Not in 60-74 window (current: {current_minute})"
    
    # Check if competition is in exception list
    if competition_name in zero_zero_exception_competitions:
        logger.info(f"0-0 exception applies for '{competition_name}' at minute {current_minute}")
        return True, "0-0 exception (competition allowed)"
    else:
        logger.debug(f"0-0 score but competition '{competition_name}' not in exception list")
        return False, "0-0 but competition not in exception list"


def get_excel_targets_for_competition(competition_name: str, excel_path: str) -> Set[str]:
    """
    Get all Result (score) targets from Excel for a specific competition
    Supports both old format (Competition column) and new format (Competition-Live column)
    
    Args:
        competition_name: Competition name from Live Score API (will be matched with Competition-Live or Competition)
        excel_path: Path to Excel file
    
    Returns:
        Set of Result values (scores) available for this competition, empty set if not found
    """
    try:
        df = pd.read_excel(excel_path)
        
        has_competition_live = 'Competition-Live' in df.columns
        has_competition_old = 'Competition' in df.columns
        
        if not has_competition_live and not has_competition_old:
            logger.warning(f"Neither 'Competition-Live' nor 'Competition' column found in Excel file")
            return set()
        
        if 'Result' not in df.columns:
            logger.warning(f"Column 'Result' not found in Excel file")
            return set()
        
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
        
        # Find matching rows - Priority: Competition-Live, then Competition
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
            logger.debug(f"No competition match found for: {competition_name} (normalized: {normalized_competition})")
            return set()
        
        # Get unique Result values
        results = matches['Result'].astype(str).str.strip().unique().tolist()
        return set(results)
        
    except FileNotFoundError:
        logger.warning(f"Excel file not found: {excel_path}")
        return set()
    except Exception as e:
        logger.error(f"Error reading Excel targets: {str(e)}")
        return set()


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


def is_out_of_target(score: str, current_minute: int, target_over: float,
                    competition_name: Optional[str] = None,
                    excel_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Check if match is out of target at minute 60
    
    Logic (per client requirements):
    - If Excel targets are provided: Check if current score + 1 goal OR +2 goals can create any score in Excel targets
    - Between minute 60 and 75, there could be 1 goal or even more than one goal
    - Therefore, we check ALL reasonable possible scorelines after +1 goal and +2 goals
    - If not in Excel targets: Match is out of target and can be discarded early
    
    Fallback logic (if Excel not available):
    - Current total goals >= (target_over + 0.5) at minute 60
    - Current total goals = target_over at minute 60 (one goal would exceed target)
    
    Args:
        score: Current score (e.g., "2-1", "0-0")
        current_minute: Current match minute
        target_over: Target Over X.5 value (e.g., 2.5 for Over 2.5)
        competition_name: Competition name (for Excel lookup)
        excel_path: Path to Excel file (Competitions_Results_Odds_Stake.xlsx)
    
    Returns:
        (is_out_of_target, reason)
    """
    if current_minute != 60:
        return False, "Not at minute 60"
    
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
                    return True, f"Score {score} at minute 60: possible scores after +1/+2 goals {sorted(possible_scores)} are not in Excel targets {sorted(excel_targets)} for {competition_name}"
                else:
                    # At least one possible score is in Excel targets → still in target
                    return False, f"Score {score} at minute 60: at least one possible score {sorted(matching_scores)} is in Excel targets"
            else:
                # Excel file not found or competition not found → fallback to old logic
                logger.debug(f"Excel targets not available for {competition_name}, using fallback logic")
        
        # Fallback logic: Check based on target_over only
        # Check if already out of target (total goals >= target + 0.5)
        # For Over 2.5: if total >= 3, already out of target
        if total_goals >= int(target_over) + 1:
            return True, f"Score {score} ({total_goals} goals) already exceeds target Over {target_over} at minute 60"
        
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
                excel_path: Optional[str] = None) -> Tuple[bool, str]:
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
    
    Returns:
        (is_qualified, reason)
    """
    # Early discard check: if at minute 60 and out of target, immediately disqualify
    if early_discard_enabled and target_over is not None and current_minute == 60:
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
            score, current_minute, competition_name, zero_zero_exception_competitions
        )
        if qualified:
            return True, reason
    
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

