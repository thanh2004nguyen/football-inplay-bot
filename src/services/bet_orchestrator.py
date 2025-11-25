"""
Bet Orchestrator Service
Handles bet execution orchestration and notifications
"""
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from logic.match_tracker import MatchTracker, MatchState
from logic.bet_executor import execute_lay_bet
from logic.qualification import get_competition_targets, normalize_score, load_competition_map_from_excel

logger = logging.getLogger("BetfairBot")


class BetOrchestrator:
    """Service for orchestrating bet execution"""
    
    def __init__(self, market_service, betting_service, bet_tracker, excel_writer,
                 skipped_matches_writer, sound_notifier, telegram_notifier, config: Dict[str, Any]):
        """
        Initialize Bet Orchestrator
        
        Args:
            market_service: Market service
            betting_service: Betting service
            bet_tracker: Bet tracker
            excel_writer: Excel writer
            skipped_matches_writer: Skipped matches writer
            sound_notifier: Sound notifier
            telegram_notifier: Telegram notifier
            config: Bot configuration
        """
        self.market_service = market_service
        self.betting_service = betting_service
        self.bet_tracker = bet_tracker
        self.excel_writer = excel_writer
        self.skipped_matches_writer = skipped_matches_writer
        self.sound_notifier = sound_notifier
        self.telegram_notifier = telegram_notifier
        self.config = config
        
        # Get Excel path
        project_root = Path(__file__).parent.parent.parent
        self.excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    
    def attempt_bet(self, tracker: MatchTracker) -> bool:
        """
        Attempt to place bet for a tracker
        
        Args:
            tracker: Match tracker
        
        Returns:
            True if bet was placed successfully, False otherwise
        """
        # Check conditions
        if not (tracker.state == MatchState.READY_FOR_BET and 
                self.betting_service and 
                75 <= tracker.current_minute < 76 and
                not tracker.bet_placed and
                not getattr(tracker, 'bet_skipped', False)):
            return False
        
        logger.info(f"🎯 Attempting bet for '{tracker.betfair_event_name}': state={tracker.state.value}, minute={tracker.current_minute}, score={tracker.current_score}")
        
        match_tracking_config = self.config.get("match_tracking", {})
        target_over = match_tracking_config.get("target_over", 2.5)
        bet_execution_config = self.config.get("bet_execution", {})
        
        logger.info(f"🎲 ATTEMPTING BET: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score}, competition: {tracker.competition_name})")
        
        # Execute bet
        bet_result = execute_lay_bet(
            market_service=self.market_service,
            betting_service=self.betting_service,
            event_id=tracker.betfair_event_id,
            event_name=tracker.betfair_event_name,
            target_over=target_over,
            bet_config=bet_execution_config,
            competition_name=tracker.competition_name,
            current_score=tracker.current_score,
            excel_path=str(self.excel_path)
        )
        
        if bet_result and bet_result.get("success"):
            # Mark bet as placed
            tracker.bet_placed = True
            tracker.bet_id = bet_result.get("betId", "")
            
            # Record bet
            bet_record = self._record_bet(tracker, bet_result)
            
            # Console output
            self._print_bet_details(tracker, bet_result, bet_record)
            
            # Notifications
            self._send_notifications(tracker, bet_result, bet_record)
            
            logger.info(f"✅ BET PLACED SUCCESSFULLY: {tracker.betfair_event_name} - BetId={bet_result.get('betId')}, Stake={bet_result.get('stake')}, Liability={bet_result.get('liability')}, LayPrice={bet_result.get('layPrice')}")
            return True
        else:
            # Mark as skipped
            tracker.bet_skipped = True
            skip_reason = "Unknown reason"
            if bet_result and isinstance(bet_result, dict):
                skip_reason = bet_result.get("reason", bet_result.get("skip_reason", "Unknown reason"))
            
            logger.warning(f"❌ BET SKIPPED: {tracker.betfair_event_name} (min {tracker.current_minute}, score {tracker.current_score}) - Reason: {skip_reason}")
            
            # Record skipped match
            self._record_skipped_match(tracker, bet_result, skip_reason)
            return False
    
    def _record_bet(self, tracker: MatchTracker, bet_result: Dict[str, Any]) -> Optional[Any]:
        """Record bet in BetTracker"""
        if not self.bet_tracker:
            return None
        
        target_score_used = tracker.current_score
        reference_odds_under_x5 = None
        liability_percent = None
        
        if self.excel_path.exists():
            try:
                df = pd.read_excel(self.excel_path)
                normalized_score = normalize_score(tracker.current_score)
                for idx, row in df.iterrows():
                    comp_name = None
                    if 'Competition-Live' in df.columns:
                        comp_name = str(row.get('Competition-Live', '')).strip()
                    elif 'Competition' in df.columns:
                        comp_name = str(row.get('Competition', '')).strip()
                    
                    if comp_name == tracker.competition_name:
                        result = str(row.get('Result', '')).strip()
                        if normalize_score(result) == normalized_score:
                            if 'Min_Odds' in df.columns or 'Min Odds' in df.columns:
                                min_odds_col = 'Min_Odds' if 'Min_Odds' in df.columns else 'Min Odds'
                                ref_odds = row.get(min_odds_col)
                                if pd.notna(ref_odds):
                                    reference_odds_under_x5 = float(ref_odds)
                            if 'Stake' in df.columns:
                                stake_val = row.get('Stake')
                                if pd.notna(stake_val):
                                    liability_percent = float(stake_val)
                            break
            except Exception as e:
                logger.warning(f"Error reading Excel for bet record: {str(e)}")
        
        bet_record = self.bet_tracker.record_bet(
            bet_id=bet_result.get("betId", ""),
            match_id=tracker.betfair_event_id,
            competition=tracker.competition_name,
            market_name=bet_result.get("marketName", ""),
            selection=bet_result.get("runnerName", ""),
            odds=bet_result.get("layPrice", 0.0),
            stake=bet_result.get("stake", 0.0),
            match_name=tracker.betfair_event_name,
            minute_of_entry=tracker.current_minute,
            live_score_at_entry=tracker.current_score,
            target_score_used=target_score_used,
            best_back_under_x5=bet_result.get("bestBackPrice"),
            reference_odds_under_x5=reference_odds_under_x5,
            best_lay_over_x5=bet_result.get("bestLayPrice"),
            final_lay_price=bet_result.get("layPrice"),
            spread_ticks=bet_result.get("spread_ticks"),
            liability_percent=liability_percent,
            liability_amount=bet_result.get("liability")
        )
        
        # Write to Excel if enabled
        if self.excel_writer:
            self.excel_writer.write_bet_record(bet_record)
        
        return bet_record
    
    def _print_bet_details(self, tracker: MatchTracker, bet_result: Dict[str, Any], bet_record: Optional[Any]):
        """Print bet details to console"""
        print(f"\n[BET PLACED]")
        print(f"Match: {tracker.betfair_event_name}")
        print(f"Competition: {tracker.competition_name}")
        print(f"Minute: {tracker.current_minute}'")
        print(f"Score: {tracker.current_score}")
        print(f"Market: {bet_result.get('marketName', 'N/A')} (LAY)")
        lay_price = bet_result.get('layPrice', 0.0)
        best_lay = bet_result.get('bestLayPrice', 0.0)
        print(f"Lay price: {lay_price:.2f} (best lay {best_lay:.2f} + 2 ticks)")
        liability = bet_result.get('liability', 0.0)
        liability_percent = bet_record.liability_percent if bet_record else None
        if liability_percent:
            print(f"Liability: {liability:.2f} ({liability_percent:.1f}% of bankroll)")
        else:
            print(f"Liability: {liability:.2f}")
        print(f"Lay stake: {bet_result.get('stake', 0.0):.2f}")
        spread_ticks = bet_result.get('spread_ticks', 0)
        print(f"Spread: {spread_ticks} ticks")
        best_back_under = bet_result.get('bestBackPrice', 0.0)
        reference_odds = bet_record.reference_odds_under_x5 if bet_record else None
        if reference_odds:
            print(f"Condition: Under back {best_back_under:.2f} >= reference {reference_odds:.2f} → OK")
        else:
            print(f"Condition: Under back {best_back_under:.2f} (reference N/A)")
        print(f"BetId: {bet_result.get('betId', 'N/A')}\n")
    
    def _send_notifications(self, tracker: MatchTracker, bet_result: Dict[str, Any], bet_record: Optional[Any]):
        """Send notifications for bet placed"""
        # Play sound
        if self.sound_notifier:
            self.sound_notifier.play_bet_placed_sound()
        
        # Send Telegram notification
        if self.telegram_notifier:
            try:
                bankroll_before = bet_record.bankroll_before if bet_record else 0.0
                bet_result_with_info = bet_result.copy()
                bet_result_with_info["eventName"] = tracker.betfair_event_name
                bet_result_with_info["referenceOdds"] = bet_record.reference_odds_under_x5 if bet_record else None
                bet_result_with_info["liabilityPercent"] = bet_record.liability_percent if bet_record else None
                self.telegram_notifier.send_bet_placed_notification(
                    bet_result_with_info,
                    competition=tracker.competition_name,
                    minute=tracker.current_minute,
                    score=tracker.current_score,
                    bankroll_before=bankroll_before
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram bet placed notification: {str(e)}")
        
        # Check if bet is matched
        size_matched = bet_result.get("sizeMatched", 0.0)
        if size_matched and size_matched > 0:
            if self.sound_notifier:
                self.sound_notifier.play_bet_matched_sound()
            
            if self.telegram_notifier:
                try:
                    bet_result_with_info = bet_result.copy()
                    bet_result_with_info["eventName"] = tracker.betfair_event_name
                    self.telegram_notifier.send_bet_matched_notification(bet_result_with_info)
                except Exception as e:
                    logger.error(f"Failed to send Telegram bet matched notification: {str(e)}")
            
            logger.info(f"Bet matched immediately: BetId={bet_result.get('betId')}, SizeMatched={size_matched}")
    
    def _record_skipped_match(self, tracker: MatchTracker, bet_result: Optional[Dict[str, Any]], skip_reason: str):
        """Record skipped match"""
        if not self.skipped_matches_writer:
            return
        
        # Get targets list from Excel
        targets_list = set()
        if self.excel_path.exists():
            targets_list = get_competition_targets(tracker.competition_name, str(self.excel_path))
        
        skipped_data = {
            "match_name": tracker.betfair_event_name,
            "competition": tracker.competition_name,
            "minute": tracker.current_minute if tracker.current_minute >= 0 else "N/A",
            "minute_75_score": tracker.current_score,
            "targets_list": targets_list,
            "status": tracker.state.value if hasattr(tracker.state, 'value') else str(tracker.state),
            "timestamp": datetime.now()
        }
        
        if bet_result and isinstance(bet_result, dict):
            skipped_data["reason"] = bet_result.get("reason", bet_result.get("skip_reason", skip_reason))
            skipped_data["best_back"] = bet_result.get("bestBackPrice")
            skipped_data["best_lay"] = bet_result.get("bestLayPrice")
            skipped_data["spread_ticks"] = bet_result.get("spread_ticks")
            skipped_data["current_odds"] = bet_result.get("bestLayPrice") or bet_result.get("calculatedLayPrice")
        else:
            skipped_data["reason"] = skip_reason
            skipped_data["best_back"] = None
            skipped_data["best_lay"] = None
            skipped_data["spread_ticks"] = None
            skipped_data["current_odds"] = None
        
        try:
            self.skipped_matches_writer.write_skipped_match(skipped_data)
            logger.info(f"Skipped match recorded: {tracker.betfair_event_name} - {skipped_data['reason']}")
        except Exception as e:
            logger.error(f"Error writing skipped match: {str(e)}")

