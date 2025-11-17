"""
Bet utilities for processing bets and outcomes
"""
from typing import Optional, Any
import logging
import re

logger = logging.getLogger("BetfairBot")


def determine_bet_outcome(final_score: str, selection: str, target_over: Optional[float] = None) -> str:
    """
    Determine bet outcome from final score for Over/Under markets
    
    Args:
        final_score: Final match score (e.g., "2-1", "0-0")
        selection: Bet selection (e.g., "Under 2.5", "Over 2.5")
        target_over: Target Over X.5 value (e.g., 2.5 for Over 2.5)
    
    Returns:
        "Won", "Lost", or "Void"
    """
    try:
        # Parse final score
        parts = final_score.split("-")
        if len(parts) != 2:
            logger.warning(f"Invalid score format: {final_score}")
            return "Void"
        
        home_goals = int(parts[0].strip())
        away_goals = int(parts[1].strip())
        total_goals = home_goals + away_goals
        
        # Extract target from selection if target_over not provided
        if target_over is None:
            # Try to extract from selection (e.g., "Over 2.5" -> 2.5)
            match = re.search(r'(\d+\.?\d*)', selection)
            if match:
                target_over = float(match.group(1))
            else:
                logger.warning(f"Could not extract target from selection: {selection}")
                return "Void"
        
        # Determine outcome based on selection type
        selection_lower = selection.lower()
        
        if "over" in selection_lower:
            # Over X.5: Won if total_goals > target_over
            if total_goals > target_over:
                return "Won"
            else:
                return "Lost"
        elif "under" in selection_lower:
            # Under X.5: Won if total_goals < target_over
            if total_goals < target_over:
                return "Won"
            else:
                return "Lost"
        else:
            logger.warning(f"Unknown selection type: {selection}")
            return "Void"
            
    except (ValueError, IndexError) as e:
        logger.warning(f"Error determining bet outcome: {str(e)}")
        return "Void"


def process_finished_matches(match_tracker_manager, bet_tracker, excel_writer, 
                             target_over: Optional[float] = None,
                             telegram_notifier: Optional[Any] = None):
    """
    Process finished matches: settle bets and export to Excel
    
    Args:
        match_tracker_manager: Match tracker manager
        bet_tracker: Bet tracker instance (None if not initialized)
        excel_writer: Excel writer instance (None if not initialized)
        target_over: Target Over X.5 value for determining bet outcomes
        telegram_notifier: Telegram notifier instance (optional)
    """
    from logic.match_tracker import MatchState
    
    if not bet_tracker or not excel_writer:
        return
    
    # Get all finished trackers
    all_trackers = match_tracker_manager.get_all_trackers()
    finished_trackers = [t for t in all_trackers if t.state == MatchState.FINISHED]
    
    for tracker in finished_trackers:
        # Get final score
        final_score = tracker.current_score
        
        # Find bets for this match
        bets = bet_tracker.get_bets_by_match_id(tracker.betfair_event_id)
        
        if bets:
            logger.info(f"Processing {len(bets)} bet(s) for finished match: {tracker.betfair_event_name} (Final: {final_score})")
            
            for bet_record in bets:
                # Skip if already settled
                if bet_record.outcome is not None:
                    continue
                
                # Determine outcome
                outcome = determine_bet_outcome(
                    final_score=final_score,
                    selection=bet_record.selection,
                    target_over=target_over
                )
                
                # Settle bet
                settled_bet = bet_tracker.settle_bet(bet_record.bet_id, outcome)
                
                if settled_bet:
                    # Send Telegram notification for Won/Lost bets only
                    if telegram_notifier and outcome in ["Won", "Lost"]:
                        try:
                            telegram_notifier.send_bet_settled_notification(
                                bet_record=settled_bet,
                                outcome=outcome,
                                profit_loss=settled_bet.profit_loss,
                                final_score=final_score,
                                event_name=tracker.betfair_event_name
                            )
                        except Exception as e:
                            logger.error(f"Failed to send Telegram bet settled notification: {str(e)}")
                    
                    # Export to Excel
                    try:
                        bet_dict = settled_bet.to_dict()
                        excel_writer.append_bet_record(bet_dict)
                        logger.info(f"Bet {settled_bet.bet_id} settled and exported: {outcome}, P/L: {settled_bet.profit_loss:.2f}")
                    except Exception as e:
                        logger.error(f"Error exporting bet {settled_bet.bet_id} to Excel: {str(e)}")

