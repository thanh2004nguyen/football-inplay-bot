"""
Formatter utilities for console output
"""
from typing import List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger("BetfairBot")


def format_tracking_table(trackers: List[Any], excel_path: Optional[str] = None) -> str:
    """
    Format tracking matches as a table for console output (MỤC 6)
    
    Args:
        trackers: List of MatchTracker instances
        excel_path: Path to Excel file to get target scores
    
    Returns:
        Formatted table string
    """
    from logic.qualification import get_competition_targets, normalize_score
    
    if not trackers:
        return "  No matches being tracked"
    
    # Sort by minute (descending) then by competition
    sorted_trackers = sorted(trackers, key=lambda t: (-t.current_minute if t.current_minute >= 0 else 999, t.competition_name))
    
    lines = []
    lines.append("  " + "=" * 110)
    lines.append(f"  {'Match':<40} | {'Min':<5} | {'Score':<12} | {'Targets':<25} | {'State':<25}")
    lines.append("  " + "-" * 110)
    
    for tracker in sorted_trackers:
        # Get target scores from Excel
        target_scores = set()
        if excel_path:
            target_scores = get_competition_targets(tracker.competition_name, excel_path)
        
        # Format targets (MỤC 6.4)
        if target_scores:
            targets_sorted = sorted(target_scores)
            targets_str = ", ".join(targets_sorted)
            # Limit length to fit in column
            if len(targets_str) > 23:
                targets_str = targets_str[:20] + "..."
        else:
            targets_str = "No targets"
        
        # Check if current score is in targets
        is_target = False
        if target_scores and tracker.current_minute >= 60:
            normalized_score = normalize_score(tracker.current_score)
            normalized_targets = {normalize_score(t) for t in target_scores}
            is_target = normalized_score in normalized_targets
        
        # Format match name (truncate if too long)
        match_name = tracker.betfair_event_name[:38]
        if len(tracker.betfair_event_name) > 38:
            match_name += ".."
        
        # Format minute
        minute_str = f"{tracker.current_minute}'" if tracker.current_minute >= 0 else "N/A"
        
        # Format score (highlight if target)
        score_str = tracker.current_score
        if is_target:
            score_str = f"🟢 {score_str}"  # Green highlight
        
        # Format state (MỤC 6.6)
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
        
        # MỤC 6.5: If score is in targets, mark as TARGET in state
        if is_target:
            state_str = f"TARGET ({state_str})"
        
        # Build line
        line = f"  {match_name:<40} | {minute_str:<5} | {score_str:<12} | {targets_str:<25} | {state_str:<25}"
        lines.append(line)
    
    lines.append("  " + "=" * 110)
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

