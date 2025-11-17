"""
Formatter utilities for console output
"""
from typing import List, Any, Optional, Dict
from datetime import datetime
import logging

logger = logging.getLogger("BetfairBot")


def format_tracking_table(trackers: List[Any], excel_path: Optional[str] = None) -> str:
    """
    Format tracking matches as a table for console output (MỤC 6)
    
    Format matches client requirements:
    [1] Tracking 3 match(es) from minute 60-74:
    ============================================================================================================
    Match | Min | Score | Targets | State
    ------------------------------------------------------------------------------------------------------------
    Gremio v Vasco da Gama | 67' | 🟢 2-1 | 1-1, 2-1, 2-2 | TARGET (TRACKING)
    ============================================================================================================
    
    Args:
        trackers: List of MatchTracker instances
        excel_path: Path to Excel file to get target scores
    
    Returns:
        Formatted table string
    """
    from logic.qualification import get_competition_targets, normalize_score
    
    if not trackers:
        return "No matches being tracked"
    
    # Sort by minute (descending) then by competition
    sorted_trackers = sorted(trackers, key=lambda t: (-t.current_minute if t.current_minute >= 0 else 999, t.competition_name))
    
    lines = []
    # Border: 108 characters (matching example format)
    border = "=" * 108
    separator = "-" * 108
    lines.append(border)
    lines.append("Match | Min | Score | Targets | State")
    lines.append(separator)
    
    for tracker in sorted_trackers:
        # Get target scores from Excel
        target_scores = set()
        if excel_path:
            target_scores = get_competition_targets(tracker.competition_name, excel_path)
        
        # Format targets (MỤC 6.4)
        # Show all targets, no truncation (as per client example)
        if target_scores:
            targets_sorted = sorted(target_scores)
            targets_str = ", ".join(targets_sorted)
        else:
            targets_str = "No targets"
        
        # Check if current score is in targets
        is_target = False
        if target_scores and tracker.current_minute >= 60:
            normalized_score = normalize_score(tracker.current_score)
            normalized_targets = {normalize_score(t) for t in target_scores}
            is_target = normalized_score in normalized_targets
        
        # Check if score was reached in 60-74 window (for green dot logic)
        # Green dot should only appear if:
        # 1. Current score is in targets, AND
        # 2. Score was reached by a goal between 60-74, OR it's 0-0 at minute 60 and 0-0 is in targets
        should_show_green_dot = False
        if is_target:
            from logic.qualification import is_score_reached_in_window, normalize_score as norm_score, get_competition_targets
            
            # Check if 0-0 exception at minute 60 (special case)
            is_zero_zero_at_60 = (tracker.current_minute == 60 and 
                                 tracker.current_score == "0-0" and
                                 excel_path and
                                 norm_score("0-0") in {norm_score(t) for t in get_competition_targets(tracker.competition_name, excel_path)})
            
            if is_zero_zero_at_60:
                should_show_green_dot = True
            elif tracker.qualified:
                # Check if score was reached in 60-74 window
                score_reached_in_window = is_score_reached_in_window(
                    tracker.current_score,
                    tracker.score_at_minute_60,
                    tracker.goals,
                    tracker.start_minute,
                    tracker.end_minute,
                    tracker.var_check_enabled,
                    tracker.score_after_goal_in_window
                )
                should_show_green_dot = score_reached_in_window
        
        # Format match name (no truncation, show full name as per client example)
        match_name = tracker.betfair_event_name
        
        # Format minute
        minute_str = f"{tracker.current_minute}'" if tracker.current_minute >= 0 else "N/A"
        
        # Format score (highlight if target and reached in window)
        score_str = tracker.current_score
        if should_show_green_dot:
            score_str = f"🟢 {score_str}"  # Green highlight
        
        # Format state (MỤC 6.6)
        # Per client example: "TARGET (TRACKING)" format
        if tracker.state.value == "DISQUALIFIED":
            state_str = f"DISCARDED({tracker.discard_reason or 'unknown'})"
        elif tracker.state.value == "READY_FOR_BET":
            state_str = "READY_FOR_BET"
        elif tracker.state.value == "QUALIFIED":
            state_str = "QUALIFIED"
        elif tracker.state.value == "MONITORING_60_74":
            state_str = "TRACKING"
        elif tracker.state.value == "WAITING_60":
            state_str = "WAITING_60"
        else:
            state_str = tracker.state.value
        
        # MỤC 6.7: Calculate last update (seconds ago) and mark STALE if needed
        time_diff = (datetime.now() - tracker.last_update).total_seconds()
        if time_diff > 120:  # Stale if > 2 minutes
            state_str += " [STALE]"
        
        # MỤC 6.5: If score is in targets AND reached in 60-74 window, mark as TARGET in state
        # Format: "TARGET (TRACKING)" as per client example
        if should_show_green_dot:
            state_str = f"TARGET ({state_str})"
        
        # Build line - format matching client example (no fixed width, use | separators)
        line = f"{match_name} | {minute_str} | {score_str} | {targets_str} | {state_str}"
        lines.append(line)
    
    lines.append(border)
    return "\n".join(lines)


def format_skipped_matches_section(skipped_matches: List[Dict[str, Any]]) -> str:
    """
    Format skipped matches section for console output
    
    Format per client requirements:
    [SKIPPED] Gremio v Vasco da Gama – Reason: spread > 4 ticks
    [SKIPPED] Palmeiras v EC Vitoria – Reason: Under price below reference odds
    
    Args:
        skipped_matches: List of skipped match dictionaries with:
            - match_name: str
            - reason: str
    
    Returns:
        Formatted string with skipped matches section
    """
    if not skipped_matches:
        return ""
    
    lines = []
    for skipped in skipped_matches:
        match_name = skipped.get("match_name", "N/A")
        reason = skipped.get("reason", "Unknown reason")
        lines.append(f"[SKIPPED] {match_name} – Reason: {reason}")
    
    return "\n".join(lines)


def format_boxed_message(message: str) -> str:
    """
    Format a message with a box border
    
    Args:
        message: Message to display in box
    
    Returns:
        Formatted string with box border
    """
    # Calculate box width (minimum 60, or message length + 4 for padding)
    width = max(60, len(message) + 4)
    
    # Create box
    top_border = "┌" + "─" * (width - 2) + "┐"
    bottom_border = "└" + "─" * (width - 2) + "┘"
    
    # Center message in box
    padding = (width - len(message) - 2) // 2
    left_padding = " " * padding
    right_padding = " " * (width - len(message) - 2 - padding)
    content = f"│{left_padding}{message}{right_padding}│"
    
    return f"{top_border}\n{content}\n{bottom_border}"

