"""
Match Tracker Module
Tracks match state and updates match data from Live Score API
"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger("BetfairBot")


class MatchState(Enum):
    """Match tracking states"""
    WAITING_60 = "WAITING_60"              # Waiting for minute 60
    MONITORING_60_74 = "MONITORING_60_74"  # Monitoring minutes 60-74
    QUALIFIED = "QUALIFIED"                # Match qualified (goal in 60-74 or 0-0 exception)
    DISQUALIFIED = "DISQUALIFIED"          # Match disqualified (no goal, no 0-0 exception)
    READY_FOR_BET = "READY_FOR_BET"        # Ready to place bet (minute 75+)
    FINISHED = "FINISHED"                  # Match finished


class MatchTracker:
    """Tracks a single match's state and data"""
    
    def __init__(self, betfair_event_id: str, betfair_event_name: str,
                 live_match_id: str, competition_name: str,
                 start_minute: int = 60, end_minute: int = 74,
                 zero_zero_exception_competitions: set = None,
                 var_check_enabled: bool = True,
                 target_over: float = None,
                 early_discard_enabled: bool = True,
                 strict_discard_at_60: bool = False,
                 discard_delay_minutes: int = 4,
                 live_event_name: str = None):
        """
        Initialize match tracker
        
        Args:
            betfair_event_id: Betfair event ID
            betfair_event_name: Betfair event name (e.g., "Team A v Team B")
            live_match_id: Live Score API match ID
            competition_name: Competition name
            start_minute: Start of goal detection window (default: 60)
            end_minute: End of goal detection window (default: 74)
            zero_zero_exception_competitions: Set of competitions with 0-0 exception
            var_check_enabled: Whether to check for cancelled goals (VAR)
            live_event_name: Live API event name (e.g., "Team A v Team B")
        """
        self.betfair_event_id = betfair_event_id
        self.betfair_event_name = betfair_event_name
        self.live_match_id = live_match_id
        self.live_event_name = live_event_name or betfair_event_name  # Fallback to Betfair name if not provided
        self.competition_name = competition_name
        self.start_minute = start_minute
        self.end_minute = end_minute
        self.zero_zero_exception_competitions = zero_zero_exception_competitions or set()
        self.var_check_enabled = var_check_enabled
        self.target_over = target_over
        self.early_discard_enabled = early_discard_enabled
        self.strict_discard_at_60 = strict_discard_at_60
        self.discard_delay_minutes = discard_delay_minutes
        
        # Discard candidate tracking (for VAR delay)
        self.discard_candidate_since: Optional[datetime] = None  # When match became discard candidate
        self.discard_candidate_reason: Optional[str] = None  # Reason for discard candidate
        self.discard_candidate_score: Optional[str] = None  # Score when marked as discard candidate
        
        # Match data
        self.current_score = "0-0"
        self.current_minute = -1
        self.goals: List[Dict[str, Any]] = []
        self.last_goal_count = 0
        self.score_at_minute_60: Optional[str] = None  # Track score at minute 60 to check if score was reached in 60-74 window
        self.score_after_goal_in_window: Optional[str] = None  # Track score after goal in 60-74 window to verify current score
        
        # State
        self.state = MatchState.WAITING_60
        self.qualified = False
        self.qualification_reason = ""
        self.discard_reason: Optional[str] = None  # Reason for discard (e.g., "score-not-target", "minute>75", "stale")
        
        # Timestamps
        self.created_at = datetime.now()
        self.last_update = datetime.now()
        self.qualified_at: Optional[datetime] = None
        
        # Bet placement tracking (Milestone 3)
        self.bet_placed = False
        self.bet_skipped = False  # Track if bet was skipped to prevent retry
        self.bet_id: Optional[str] = None
        
        # Log removed - not needed
    
    def update_match_data(self, score: str, minute: int, goals: List[Dict[str, Any]]):
        """
        Update match data from Live Score API
        
        Args:
            score: Current score (e.g., "2-1")
            minute: Current match minute
            goals: List of goals (may include cancelled)
        """
        self.current_score = score
        self.current_minute = minute
        self.goals = goals
        self.last_update = datetime.now()
        
        # Check for new goals
        current_goal_count = len([g for g in goals if not g.get('cancelled', False)])
        if current_goal_count > self.last_goal_count:
            new_goal_count = current_goal_count - self.last_goal_count
            logger.info(f"Match {self.betfair_event_name}: {new_goal_count} new goal(s) detected (total: {current_goal_count})")
            self.last_goal_count = current_goal_count
    
    def update_state(self, excel_path: Optional[str] = None):
        """
        Update match state based on current data
        
        Args:
            excel_path: Path to Excel file (for early discard check based on Excel targets)
        """
        from logic.qualification import is_qualified, get_competition_targets, normalize_score
        
        # Check if match is finished
        # IMPORTANT: Don't mark as FINISHED if match is QUALIFIED and hasn't reached minute 75 yet
        # This allows QUALIFIED matches to continue tracking until minute 75 for bet placement
        if self.current_minute < 0 or self.current_minute > 90:
            # Only mark as FINISHED if:
            # 1. Match is not QUALIFIED (can finish early)
            # 2. OR match is QUALIFIED but has already passed minute 75 (bet window closed)
            # 3. OR match is READY_FOR_BET and minute > 90 (match truly finished)
            should_finish = False
            
            if self.state == MatchState.QUALIFIED:
                # If QUALIFIED, only finish if minute > 90 AND (bet already placed OR minute > 75)
                # This ensures we don't finish a QUALIFIED match before it can reach minute 75
                if self.current_minute > 90:
                    if self.bet_placed or self.current_minute > 75:
                        should_finish = True
                    else:
                        # Match is QUALIFIED but minute is invalid (> 90) before reaching 75
                        # This shouldn't happen, but log a warning
                        logger.warning(f"⚠️ Match {self.betfair_event_name}: Invalid minute {self.current_minute} but QUALIFIED and hasn't reached 75 yet - keeping tracker alive")
                        should_finish = False
                elif self.current_minute < 0:
                    # Negative minute means match not started or invalid - can finish
                    should_finish = True
            elif self.state == MatchState.READY_FOR_BET:
                # If READY_FOR_BET, can finish if minute > 90 (match truly finished)
                if self.current_minute > 90:
                    should_finish = True
                elif self.current_minute < 0:
                    should_finish = True
            else:
                # For other states (WAITING_60, MONITORING_60_74, DISQUALIFIED), can finish normally
                should_finish = True
            
            if should_finish:
                if self.state != MatchState.FINISHED:
                    self.state = MatchState.FINISHED
                    # No log needed - tracking list will handle it
                return
            else:
                # Don't finish yet - continue tracking
                logger.debug(f"Match {self.betfair_event_name}: Not finishing yet (minute {self.current_minute}, state {self.state.value})")
                return
        
        # MỤC 3.4: Discard if minute > 74 (unless bet already placed OR match is QUALIFIED/READY_FOR_BET)
        # IMPORTANT: If match is QUALIFIED, allow it to reach minute 75 to transition to READY_FOR_BET
        # IMPORTANT: Skip this check for MONITORING_60_74 state - will check after qualification check
        if self.current_minute > 74:
            # If bet already placed, continue tracking until match finished
            if self.bet_placed:
                # Match finished check is handled below
                pass
            # If match is QUALIFIED or READY_FOR_BET, allow it to continue (need to reach minute 75 for bet)
            elif self.state == MatchState.QUALIFIED or self.state == MatchState.READY_FOR_BET:
                # Allow match to continue - it will transition to READY_FOR_BET at minute 75
                # or place bet during minute 75
                pass
            # IMPORTANT: Skip check for MONITORING_60_74 - will check after qualification check below
            elif self.state == MatchState.MONITORING_60_74:
                # Skip this check - will check after qualification check to avoid disqualifying
                # matches that have goals but haven't been qualified yet due to timing
                pass
            elif self.state != MatchState.DISQUALIFIED:
                # Match is not QUALIFIED and minute > 74 - discard
                self.state = MatchState.DISQUALIFIED
                self.discard_reason = f"minute {self.current_minute} > 74 (not qualified)"
                logger.info(f"✘ {self.betfair_event_name}: DISQUALIFIED - minute {self.current_minute} > 74 (not qualified)")
                return
            else:
                # Already DISQUALIFIED, nothing to do
                pass
        
        # MỤC 3.3: Discard if current_score cannot reach targets (check every update from minute 0 onwards)
        # Logic: Only discard if score is NOT in targets AND cannot reach targets by adding enough goals
        # IMPORTANT: Check continuously, not just 0-74, to catch score changes that make match impossible
        # IMPORTANT: This check must run BEFORE state transitions and regardless of current state
        # IMPORTANT: Do NOT discard 0-0 scores at early minutes (< 60) as 0-0 is normal for new matches
        # IMPORTANT: Do NOT discard matches that are already QUALIFIED or READY_FOR_BET - once qualified, they should remain qualified until match ends
        if self.current_minute >= 0 and excel_path and self.state != MatchState.DISQUALIFIED and self.state != MatchState.FINISHED and self.state != MatchState.QUALIFIED and self.state != MatchState.READY_FOR_BET:
            from logic.qualification import get_possible_scores_after_multiple_goals, calculate_max_goals_needed
            normalized_score = normalize_score(self.current_score)
            target_scores = get_competition_targets(self.competition_name, excel_path)
            
            if target_scores:  # Only check if targets exist
                normalized_targets = {normalize_score(t) for t in target_scores}
                
                # Skip discard check for 0-0 scores at early minutes (< 60) - 0-0 is normal for new matches
                if normalized_score == "0-0" and self.current_minute < 60:
                    logger.debug(f"Score check: Match '{self.betfair_event_name}', Score '0-0' at minute {self.current_minute} - skipping discard check (normal for early match)")
                # Check 1: Is current score already in targets?
                elif normalized_score in normalized_targets:
                    # Score is in targets → Check if adding 1 goal would exit all targets
                    # IMPORTANT: If adding 1 goal would make ALL possible scores exit targets, disqualify
                    # This handles cases like: 1-0 with targets [1-0] → adding 1 goal → 2-0 or 1-1 → both exit targets
                    # IMPORTANT: This check only runs for matches NOT yet QUALIFIED/READY_FOR_BET (see condition above)
                    possible_scores_after_1_goal = get_possible_scores_after_multiple_goals(self.current_score, max_goals=1)
                    normalized_possible_after_1 = {normalize_score(s) for s in possible_scores_after_1_goal}
                    matching_after_1_goal = normalized_possible_after_1 & normalized_targets
                    
                    if not matching_after_1_goal:
                        # Adding 1 goal would exit ALL targets → DISCARD
                        # This means match is at target but any goal would make it impossible to stay in targets
                        # IMPORTANT: Only discard if match is not yet QUALIFIED or READY_FOR_BET
                        self.state = MatchState.DISQUALIFIED
                        self.discard_reason = f"score-would-exit-targets: score {self.current_score} @ {self.current_minute} is in targets {sorted(target_scores)}, but adding 1 goal would exit all targets"
                        self.qualified = False
                        logger.info(f"✘ {self.betfair_event_name}: DISQUALIFIED - score {self.current_score} @ {self.current_minute}' is in targets {sorted(target_scores)}, but adding 1 goal would exit all targets")
                        return
                    else:
                        # At least one possible score after 1 goal is still in targets → OK
                        logger.debug(f"Score check: Match '{self.betfair_event_name}', Score '{self.current_score}' is in targets {sorted(target_scores)} and can stay in targets after 1 goal → OK")
                else:
                    # Score not in targets → Calculate max_goals needed dynamically based on target scores
                    max_goals_needed = calculate_max_goals_needed(self.current_score, target_scores)
                    logger.debug(f"Score check: Match '{self.betfair_event_name}', Score '{self.current_score}' needs max {max_goals_needed} goals to reach targets {sorted(target_scores)}")
                    
                    # Check if can reach targets by adding up to max_goals_needed goals
                    possible_scores = get_possible_scores_after_multiple_goals(self.current_score, max_goals=max_goals_needed)
                    normalized_possible = {normalize_score(s) for s in possible_scores}
                    matching_scores = normalized_possible & normalized_targets
                    
                    if not matching_scores:
                        # Cannot reach any target even with max_goals_needed goals → DISCARD
                        # IMPORTANT: Only discard if match is not yet QUALIFIED or READY_FOR_BET
                        # (This check is skipped for QUALIFIED/READY_FOR_BET matches - see condition above)
                        self.state = MatchState.DISQUALIFIED
                        self.discard_reason = f"score-cannot-reach-targets: score {self.current_score} at minute {self.current_minute} cannot reach any target {sorted(target_scores)} even with {max_goals_needed} goals"
                        self.qualified = False
                        logger.info(f"✘ {self.betfair_event_name}: DISQUALIFIED - score {self.current_score} @ {self.current_minute}' cannot reach targets {sorted(target_scores)} even with {max_goals_needed} goals")
                        return
                    else:
                        # Can reach targets with max_goals_needed goals → OK, don't discard
                        logger.debug(f"Score check: Match '{self.betfair_event_name}', Score '{self.current_score}' can reach targets {sorted(matching_scores)} with up to {max_goals_needed} goals → OK")
            else:
                # No targets found - log warning but don't discard (might be new competition not in Excel yet)
                logger.debug(f"No targets found for competition '{self.competition_name}' at minute {self.current_minute} - skipping discard check")
        
        # State transitions
        if self.state == MatchState.WAITING_60:
            if self.current_minute >= self.start_minute:
                self.state = MatchState.MONITORING_60_74
                # Store score at minute 60 to check if later score was reached in 60-74 window
                if self.current_minute == 60 and self.score_at_minute_60 is None:
                    self.score_at_minute_60 = self.current_score
                # Log removed
        
        # Also store score at minute 60 if we're already in MONITORING_60_74 state and it's exactly minute 60
        if self.state == MatchState.MONITORING_60_74 and self.current_minute == 60 and self.score_at_minute_60 is None:
            self.score_at_minute_60 = self.current_score
        
        elif self.state == MatchState.MONITORING_60_74:
            # Check if we have a discard candidate and if delay has passed
            if self.discard_candidate_since is not None:
                # Re-check if match is still impossible (even if score unchanged, might have been qualified)
                strict_discard = getattr(self, 'strict_discard_at_60', False)
                still_impossible = False
                
                if strict_discard and excel_path:
                    from logic.qualification import is_impossible_match_at_60
                    still_impossible, new_reason = is_impossible_match_at_60(
                        self.current_score, 
                        self.competition_name, 
                        excel_path
                    )
                    
                    # Check if score changed (VAR might have cancelled a goal)
                    if self.current_score != self.discard_candidate_score:
                        if not still_impossible:
                            # Match is no longer impossible - clear discard candidate (VAR cancelled goal)
                            logger.info(f"Match {self.betfair_event_name}: Score changed from {self.discard_candidate_score} to {self.current_score} - match no longer impossible, clearing discard candidate (VAR check)")
                            self.discard_candidate_since = None
                            self.discard_candidate_reason = None
                            self.discard_candidate_score = None
                        else:
                            # Still impossible but score changed - update candidate info
                            logger.info(f"Match {self.betfair_event_name}: Score changed from {self.discard_candidate_score} to {self.current_score} but still impossible - updating discard candidate")
                            self.discard_candidate_reason = new_reason
                            self.discard_candidate_score = self.current_score
                    elif not still_impossible:
                        # Score unchanged but match is no longer impossible (shouldn't happen, but safe check)
                        logger.info(f"Match {self.betfair_event_name}: Match no longer impossible - clearing discard candidate")
                        self.discard_candidate_since = None
                        self.discard_candidate_reason = None
                        self.discard_candidate_score = None
                    else:
                        # Still impossible and score unchanged - check if delay has passed
                        delay_duration = timedelta(minutes=self.discard_delay_minutes)
                        if datetime.now() - self.discard_candidate_since >= delay_duration:
                            # Delay has passed - now discard the match
                            self.state = MatchState.DISQUALIFIED
                            self.discard_reason = f"impossible-match-after-delay: {self.discard_candidate_reason}"
                            logger.info(f"Match {self.betfair_event_name}: DISQUALIFIED after {self.discard_delay_minutes} minute delay - {self.discard_candidate_reason}")
                            return
                        else:
                            # Still waiting for delay - log status
                            elapsed = (datetime.now() - self.discard_candidate_since).total_seconds() / 60
                            remaining = self.discard_delay_minutes - elapsed
                            logger.debug(f"Match {self.betfair_event_name}: Waiting for discard delay ({remaining:.1f} minutes remaining) - {self.discard_candidate_reason}")
                else:
                    # Can't check - if score changed, clear candidate to be safe
                    if self.current_score != self.discard_candidate_score:
                        logger.info(f"Match {self.betfair_event_name}: Score changed from {self.discard_candidate_score} to {self.current_score} - clearing discard candidate")
                        self.discard_candidate_since = None
                        self.discard_candidate_reason = None
                        self.discard_candidate_score = None
                    else:
                        # Score unchanged - check if delay has passed
                        delay_duration = timedelta(minutes=self.discard_delay_minutes)
                        if datetime.now() - self.discard_candidate_since >= delay_duration:
                            # Delay has passed - now discard the match
                            self.state = MatchState.DISQUALIFIED
                            self.discard_reason = f"impossible-match-after-delay: {self.discard_candidate_reason}"
                            logger.info(f"Match {self.betfair_event_name}: DISQUALIFIED after {self.discard_delay_minutes} minute delay - {self.discard_candidate_reason}")
                            return
                        else:
                            # Still waiting for delay - log status
                            elapsed = (datetime.now() - self.discard_candidate_since).total_seconds() / 60
                            remaining = self.discard_delay_minutes - elapsed
                            logger.debug(f"Match {self.betfair_event_name}: Waiting for discard delay ({remaining:.1f} minutes remaining) - {self.discard_candidate_reason}")
            
            # Check qualification
            if not self.qualified:
                # Get strict_discard_at_60 from config (passed via update_state)
                strict_discard = getattr(self, 'strict_discard_at_60', False)
                
                qualified, reason = is_qualified(
                    score=self.current_score,
                    goals=self.goals,
                    current_minute=self.current_minute,
                    start_minute=self.start_minute,
                    end_minute=self.end_minute,
                    competition_name=self.competition_name,
                    zero_zero_exception_competitions=self.zero_zero_exception_competitions,
                    var_check_enabled=self.var_check_enabled,
                    target_over=self.target_over,
                    early_discard_enabled=self.early_discard_enabled,
                    excel_path=excel_path,
                    strict_discard_at_60=strict_discard
                )
                
                # If out of target at minute 60, immediately disqualify (not related to strict discard)
                if not qualified and "Out of target" in reason:
                    self.state = MatchState.DISQUALIFIED
                    logger.info(f"Match {self.betfair_event_name}: DISQUALIFIED - {reason}")
                    return
                
                # Check for strict discard (impossible match) - but use delay instead of immediate discard
                if not qualified and "Impossible match" in reason and strict_discard:
                    # Mark as discard candidate instead of discarding immediately
                    if self.discard_candidate_since is None:
                        # First time marking as discard candidate
                        self.discard_candidate_since = datetime.now()
                        self.discard_candidate_reason = reason
                        self.discard_candidate_score = self.current_score
                        # Log removed
                    # If already a discard candidate, continue waiting (handled above)
                    return
                
                if qualified:
                    # Clear discard candidate if match becomes qualified (goal scored or 0-0 exception)
                    if self.discard_candidate_since is not None:
                        logger.info(f"Match {self.betfair_event_name}: Match qualified - clearing discard candidate")
                        self.discard_candidate_since = None
                        self.discard_candidate_reason = None
                        self.discard_candidate_score = None
                    
                    self.qualified = True
                    self.qualification_reason = reason
                    self.qualified_at = datetime.now()
                    # Store score after qualification (when goal in 60-74 or 0-0 exception)
                    # This helps verify if current score was reached in the window
                    if "Goal in" in reason or "0-0 exception" in reason:
                        self.score_after_goal_in_window = self.current_score
                    self.state = MatchState.QUALIFIED
                    logger.info(f"Match {self.betfair_event_name}: QUALIFIED - {reason}")
            
            # IMPORTANT: Check minute > 74 AFTER qualification check
            # This ensures matches with goals in 60-74 window get a chance to be qualified
            # before being disqualified due to minute > 74
            if self.current_minute > 74:
                if self.qualified:
                    # Match is qualified - allow it to continue to READY_FOR_BET
                    pass
                elif self.state != MatchState.DISQUALIFIED:
                    # Match is not qualified and minute > 74 - discard
                    # Check why it wasn't qualified: no goal in 60-74 or no 0-0 exception
                    from logic.qualification import check_goal_in_window, filter_cancelled_goals
                    
                    # Check if there was a goal in 60-74 window
                    if self.var_check_enabled:
                        valid_goals = filter_cancelled_goals(self.goals)
                    else:
                        valid_goals = self.goals
                    has_goal_in_window = check_goal_in_window(valid_goals, self.start_minute, self.end_minute)
                    
                    # Check if 0-0 exception could apply
                    has_zero_zero_exception = False
                    if excel_path and self.current_score == "0-0":
                        from logic.qualification import get_competition_targets, normalize_score
                        target_scores = get_competition_targets(self.competition_name, excel_path)
                        if target_scores:
                            normalized_targets = {normalize_score(t) for t in target_scores}
                            normalized_score = normalize_score(self.current_score)
                            has_zero_zero_exception = normalized_score in normalized_targets
                    
                    # Build detailed reason
                    if not has_goal_in_window and not has_zero_zero_exception:
                        reason_detail = f"no goal in {self.start_minute}-{self.end_minute} window, no 0-0 exception"
                    elif not has_goal_in_window:
                        reason_detail = f"no goal in {self.start_minute}-{self.end_minute} window (score {self.current_score} is not 0-0 or 0-0 not in targets)"
                    elif not has_zero_zero_exception:
                        reason_detail = f"goal detected but not qualified (possibly VAR cancelled), no 0-0 exception"
                    else:
                        reason_detail = f"not qualified (unknown reason)"
                    
                    self.state = MatchState.DISQUALIFIED
                    self.discard_reason = f"minute {self.current_minute} > 74 ({reason_detail})"
                    logger.info(f"✘ {self.betfair_event_name}: DISQUALIFIED - minute {self.current_minute} > 74 ({reason_detail})")
                    return
            
            # Check if window passed
            if self.current_minute > self.end_minute:
                if self.qualified:
                    self.state = MatchState.READY_FOR_BET
                    logger.info(f"Match {self.betfair_event_name}: Ready for bet (minute {self.current_minute})")
                else:
                    self.state = MatchState.DISQUALIFIED
                    # Check if 0-0 is in target list to determine correct message
                    has_zero_zero_in_targets = False
                    if excel_path and self.current_score == "0-0":
                        target_scores = get_competition_targets(self.competition_name, excel_path)
                        if target_scores:
                            normalized_targets = {normalize_score(t) for t in target_scores}
                            normalized_score = normalize_score(self.current_score)
                            has_zero_zero_in_targets = normalized_score in normalized_targets
                    
                    if has_zero_zero_in_targets:
                        # 0-0 is in targets, so this shouldn't happen (should have been qualified at minute 60)
                        # But if it did, show a different message
                        logger.info(f"✘ Match {self.betfair_event_name}: Disqualified (no goal in {self.start_minute}-{self.end_minute})")
                    else:
                        # 0-0 is NOT in targets, so "no 0-0 exception" is correct
                        logger.info(f"✘ Match {self.betfair_event_name}: Disqualified (no goal in {self.start_minute}-{self.end_minute}, no 0-0 exception)")
        
        elif self.state == MatchState.QUALIFIED:
            # Check if ready for bet (minute 75 only: 75:00 to 75:59)
            # Entry window is the full 75th minute (75:00 to 75:59)
            # IMPORTANT: Re-check if current score is still in targets at minute 75
            logger.debug(f"Match {self.betfair_event_name}: QUALIFIED state - current_minute={self.current_minute}, checking if ready for bet...")
            
            if 75 <= self.current_minute < 76:
                logger.info(f"Match {self.betfair_event_name}: Minute {self.current_minute} is in bet window (75-76), checking score...")
                # Re-check if current score is still in targets
                if excel_path:
                    from logic.qualification import get_competition_targets, normalize_score
                    normalized_score = normalize_score(self.current_score)
                    target_scores = get_competition_targets(self.competition_name, excel_path)
                    
                    if target_scores:
                        normalized_targets = {normalize_score(t) for t in target_scores}
                        
                        if normalized_score not in normalized_targets:
                            # Score is no longer in targets - disqualify
                            self.state = MatchState.DISQUALIFIED
                            self.discard_reason = "score-not-target-at-75"
                            self.qualified = False
                            logger.info(f"Match {self.betfair_event_name}: DISQUALIFIED at minute 75 - score {self.current_score} not in targets {sorted(target_scores)}")
                            return
                        else:
                            logger.debug(f"Match {self.betfair_event_name}: Score {self.current_score} is still in targets {sorted(target_scores)}")
                
                # Score is still in targets, proceed to READY_FOR_BET
                self.state = MatchState.READY_FOR_BET
                logger.info(f"✅ Match {self.betfair_event_name}: READY FOR BET (minute {self.current_minute}, score {self.current_score})")
            elif self.current_minute > 75 and not self.bet_placed:
                # Minute 75 has passed and bet was not placed - mark as expired
                # Per client requirement: if conditions never all true during entire 75th minute, match is expired
                self.state = MatchState.DISQUALIFIED
                self.discard_reason = "expired-minute-75"
                self.qualified = False
                logger.warning(f"⚠️ Match {self.betfair_event_name}: EXPIRED - minute {self.current_minute} > 75, bet not placed during minute 75")
            elif self.current_minute < 75:
                # Still waiting for minute 75
                logger.debug(f"Match {self.betfair_event_name}: QUALIFIED but waiting for minute 75 (current: {self.current_minute})")
        
        elif self.state == MatchState.READY_FOR_BET:
            # Check if minute 75 has passed without bet placement
            if self.current_minute > 75 and not self.bet_placed:
                # Minute 75 has passed and bet was not placed - mark as expired
                self.state = MatchState.DISQUALIFIED
                self.discard_reason = "expired-minute-75"
                self.qualified = False
                logger.info(f"Match {self.betfair_event_name}: EXPIRED - minute {self.current_minute} > 75, bet not placed during minute 75")
                return
            
            # Continue checking if score is still in targets during minute 75
            # If a goal is scored during minute 75 and moves score outside targets, remove TARGET status
            if 75 <= self.current_minute < 76 and excel_path:
                from logic.qualification import get_competition_targets, normalize_score
                normalized_score = normalize_score(self.current_score)
                target_scores = get_competition_targets(self.competition_name, excel_path)
                
                if target_scores:
                    normalized_targets = {normalize_score(t) for t in target_scores}
                    
                    if normalized_score not in normalized_targets:
                        # Score is no longer in targets - disqualify
                        self.state = MatchState.DISQUALIFIED
                        self.discard_reason = "score-not-target-during-75"
                        self.qualified = False
                        logger.info(f"Match {self.betfair_event_name}: DISQUALIFIED during minute 75 - score {self.current_score} not in targets {sorted(target_scores)}")
                        return
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current match status
        
        Returns:
            Dictionary with match status information
        """
        return {
            "betfair_event_id": self.betfair_event_id,
            "betfair_event_name": self.betfair_event_name,
            "live_match_id": self.live_match_id,
            "competition": self.competition_name,
            "current_score": self.current_score,
            "current_minute": self.current_minute,
            "state": self.state.value,
            "qualified": self.qualified,
            "qualification_reason": self.qualification_reason,
            "discard_reason": self.discard_reason,
            "goals_count": len([g for g in self.goals if not g.get('cancelled', False)]),
            "last_update": self.last_update.isoformat(),
            "qualified_at": self.qualified_at.isoformat() if self.qualified_at else None
        }
    
    def is_ready_for_bet(self) -> bool:
        """Check if match is ready for bet placement"""
        return self.state == MatchState.READY_FOR_BET and self.qualified


class MatchTrackerManager:
    """Manages multiple match trackers"""
    
    def __init__(self):
        """Initialize match tracker manager"""
        self.trackers: Dict[str, MatchTracker] = {}  # Key: betfair_event_id
        # Logging moved to main.py setup checklist
    
    def add_tracker(self, tracker: MatchTracker):
        """
        Add a match tracker
        
        Args:
            tracker: MatchTracker instance
        """
        self.trackers[tracker.betfair_event_id] = tracker
        # Log removed - not needed
    
    def get_tracker(self, betfair_event_id: str) -> Optional[MatchTracker]:
        """
        Get tracker for a match
        
        Args:
            betfair_event_id: Betfair event ID
        
        Returns:
            MatchTracker instance, or None if not found
        """
        return self.trackers.get(betfair_event_id)
    
    def remove_tracker(self, betfair_event_id: str):
        """
        Remove tracker for a match
        
        Args:
            betfair_event_id: Betfair event ID
        """
        if betfair_event_id in self.trackers:
            tracker = self.trackers.pop(betfair_event_id)
            # Log removed - not needed
    
    def get_all_trackers(self) -> List[MatchTracker]:
        """Get all active trackers"""
        return list(self.trackers.values())
    
    def get_ready_for_bet(self) -> List[MatchTracker]:
        """Get all trackers ready for bet placement"""
        return [t for t in self.trackers.values() if t.is_ready_for_bet()]
    
    def cleanup_finished(self):
        """Remove trackers for finished matches"""
        finished = [event_id for event_id, tracker in self.trackers.items() 
                   if tracker.state == MatchState.FINISHED]
        for event_id in finished:
            self.remove_tracker(event_id)
    
    def cleanup_discarded(self):
        """Remove trackers for discarded matches (MỤC 3.7)"""
        discarded = [event_id for event_id, tracker in self.trackers.items() 
                     if tracker.state == MatchState.DISQUALIFIED]
        for event_id in discarded:
            self.remove_tracker(event_id)
