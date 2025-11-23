"""
Tracking Services Module
Consolidated tracking services: Bet Tracker, Excel Writer, Skipped Matches Writer
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("BetfairBot")


# ============================================================================
# BET RECORD
# ============================================================================

class BetRecord:
    """Represents a single bet record"""
    
    def __init__(self, bet_id: str, match_id: str, competition: str,
                 market_name: str, selection: str, odds: float, stake: float,
                 bet_time: datetime, bankroll_before: float,
                 match_name: Optional[str] = None,
                 minute_of_entry: Optional[int] = None,
                 live_score_at_entry: Optional[str] = None,
                 target_score_used: Optional[str] = None,
                 best_back_under_x5: Optional[float] = None,
                 reference_odds_under_x5: Optional[float] = None,
                 best_lay_over_x5: Optional[float] = None,
                 final_lay_price: Optional[float] = None,
                 spread_ticks: Optional[int] = None,
                 liability_percent: Optional[float] = None,
                 liability_amount: Optional[float] = None):
        self.bet_id = bet_id
        self.match_id = match_id
        self.competition = competition
        self.market_name = market_name
        self.selection = selection
        self.odds = odds
        self.stake = stake
        self.bet_time = bet_time
        self.bankroll_before = bankroll_before
        
        self.match_name = match_name
        self.minute_of_entry = minute_of_entry
        self.live_score_at_entry = live_score_at_entry
        self.target_score_used = target_score_used
        self.best_back_under_x5 = best_back_under_x5
        self.reference_odds_under_x5 = reference_odds_under_x5
        self.best_lay_over_x5 = best_lay_over_x5
        self.final_lay_price = final_lay_price
        self.spread_ticks = spread_ticks
        self.liability_percent = liability_percent
        self.liability_amount = liability_amount
        
        self.outcome: Optional[str] = None
        self.profit_loss: Optional[float] = None
        self.bankroll_after: Optional[float] = None
        self.settled_at: Optional[datetime] = None
        self.status = "Pending"
    
    def settle(self, outcome: str, profit_loss: float, bankroll_after: float):
        """Settle bet with outcome"""
        self.outcome = outcome
        self.profit_loss = profit_loss
        self.bankroll_after = bankroll_after
        self.status = outcome
        self.settled_at = datetime.now()
        
        logger.info(f"Bet {self.bet_id} settled: {outcome}, P/L: {profit_loss:.2f}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Excel export"""
        return {
            "Bet_ID": self.bet_id,
            "Match_ID": self.match_id,
            "Match": self.match_name or "",
            "Competition": self.competition,
            "Minute_of_Entry": self.minute_of_entry if self.minute_of_entry is not None else "",
            "Live_Score_at_Entry": self.live_score_at_entry or "",
            "Target_Score_Used": self.target_score_used or "",
            "Market_Name": self.market_name,
            "Selection": self.selection,
            "Best_BACK_Under_X5": self.best_back_under_x5 if self.best_back_under_x5 is not None else "",
            "Reference_Under_X5_Odds": self.reference_odds_under_x5 if self.reference_odds_under_x5 is not None else "",
            "Best_LAY_Over_X5": self.best_lay_over_x5 if self.best_lay_over_x5 is not None else "",
            "Final_LAY_Price": self.final_lay_price if self.final_lay_price is not None else self.odds,
            "Spread_Ticks": self.spread_ticks if self.spread_ticks is not None else "",
            "Liability_Percent": self.liability_percent if self.liability_percent is not None else "",
            "Liability_Amount": self.liability_amount if self.liability_amount is not None else "",
            "Lay_Stake": self.stake,
            "Odds": self.odds,
            "Bet_Time": self.bet_time,
            "Starting_Bankroll": self.bankroll_before,
            "Outcome": self.outcome or "Pending",
            "Profit_Loss": self.profit_loss if self.profit_loss is not None else 0.0,
            "Updated_Bankroll": self.bankroll_after if self.bankroll_after is not None else self.bankroll_before,
            "Status": self.status,
            "Settled_At": self.settled_at if self.settled_at else None
        }


# ============================================================================
# BET TRACKER
# ============================================================================

class BetTracker:
    """Tracks all bets and manages bankroll"""
    
    def __init__(self, initial_bankroll: float = 0.0):
        self.bets: Dict[str, BetRecord] = {}
        self.current_bankroll = initial_bankroll
        self.initial_bankroll = initial_bankroll
    
    def record_bet(self, bet_id: str, match_id: str, competition: str,
                   market_name: str, selection: str, odds: float, stake: float,
                   match_name: Optional[str] = None,
                   minute_of_entry: Optional[int] = None,
                   live_score_at_entry: Optional[str] = None,
                   target_score_used: Optional[str] = None,
                   best_back_under_x5: Optional[float] = None,
                   reference_odds_under_x5: Optional[float] = None,
                   best_lay_over_x5: Optional[float] = None,
                   final_lay_price: Optional[float] = None,
                   spread_ticks: Optional[int] = None,
                   liability_percent: Optional[float] = None,
                   liability_amount: Optional[float] = None) -> BetRecord:
        """Record a new bet"""
        bankroll_before = self.current_bankroll
        
        bet_record = BetRecord(
            bet_id=bet_id,
            match_id=match_id,
            competition=competition,
            market_name=market_name,
            selection=selection,
            odds=odds,
            stake=stake,
            bet_time=datetime.now(),
            bankroll_before=bankroll_before,
            match_name=match_name,
            minute_of_entry=minute_of_entry,
            live_score_at_entry=live_score_at_entry,
            target_score_used=target_score_used,
            best_back_under_x5=best_back_under_x5,
            reference_odds_under_x5=reference_odds_under_x5,
            best_lay_over_x5=best_lay_over_x5,
            final_lay_price=final_lay_price,
            spread_ticks=spread_ticks,
            liability_percent=liability_percent,
            liability_amount=liability_amount
        )
        
        self.bets[bet_id] = bet_record
        self.current_bankroll -= stake
        bet_record.bankroll_after = self.current_bankroll
        
        logger.info(f"Bet recorded: {bet_id}, Stake: {stake:.2f}, Bankroll: {bankroll_before:.2f} -> {self.current_bankroll:.2f}")
        
        return bet_record
    
    def settle_bet(self, bet_id: str, outcome: str) -> Optional[BetRecord]:
        """Settle a bet with outcome"""
        bet_record = self.bets.get(bet_id)
        if not bet_record:
            logger.warning(f"Bet {bet_id} not found for settlement")
            return None
        
        if outcome == "Won":
            profit_loss = (bet_record.odds - 1) * bet_record.stake
        elif outcome == "Lost":
            profit_loss = -bet_record.stake
        elif outcome == "Void":
            profit_loss = 0.0
        else:
            logger.warning(f"Unknown outcome: {outcome}")
            profit_loss = 0.0
        
        bankroll_after = self.current_bankroll + profit_loss + bet_record.stake
        self.current_bankroll = bankroll_after
        
        bet_record.settle(outcome, profit_loss, bankroll_after)
        
        return bet_record
    
    def get_bet(self, bet_id: str) -> Optional[BetRecord]:
        """Get bet record by ID"""
        return self.bets.get(bet_id)
    
    def get_all_bets(self) -> List[BetRecord]:
        """Get all bet records"""
        return list(self.bets.values())
    
    def get_bets_by_competition(self, competition: str) -> List[BetRecord]:
        """Get all bets for a specific competition"""
        return [b for b in self.bets.values() if b.competition == competition]
    
    def get_bets_by_match_id(self, match_id: str) -> List[BetRecord]:
        """Get all bets for a specific match/event ID"""
        return [b for b in self.bets.values() if b.match_id == match_id]
    
    def get_performance_by_competition(self) -> Dict[str, Dict[str, Any]]:
        """Calculate performance statistics by competition"""
        performance = {}
        
        for bet in self.bets.values():
            comp = bet.competition
            if comp not in performance:
                performance[comp] = {
                    "total_bets": 0,
                    "won": 0,
                    "lost": 0,
                    "pending": 0,
                    "total_stake": 0.0,
                    "total_profit_loss": 0.0
                }
            
            stats = performance[comp]
            stats["total_bets"] += 1
            stats["total_stake"] += bet.stake
            
            if bet.outcome == "Won":
                stats["won"] += 1
                stats["total_profit_loss"] += bet.profit_loss or 0.0
            elif bet.outcome == "Lost":
                stats["lost"] += 1
                stats["total_profit_loss"] += bet.profit_loss or 0.0
            elif bet.outcome is None:
                stats["pending"] += 1
        
        return performance
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall betting statistics"""
        total_bets = len(self.bets)
        won = sum(1 for b in self.bets.values() if b.outcome == "Won")
        lost = sum(1 for b in self.bets.values() if b.outcome == "Lost")
        pending = sum(1 for b in self.bets.values() if b.outcome is None)
        
        total_stake = sum(b.stake for b in self.bets.values())
        total_profit_loss = sum(b.profit_loss or 0.0 for b in self.bets.values() if b.profit_loss is not None)
        
        return {
            "total_bets": total_bets,
            "won": won,
            "lost": lost,
            "pending": pending,
            "win_rate": (won / total_bets * 100) if total_bets > 0 else 0.0,
            "total_stake": total_stake,
            "total_profit_loss": total_profit_loss,
            "initial_bankroll": self.initial_bankroll,
            "current_bankroll": self.current_bankroll,
            "net_change": self.current_bankroll - self.initial_bankroll,
            "roi": ((self.current_bankroll - self.initial_bankroll) / self.initial_bankroll * 100) if self.initial_bankroll > 0 else 0.0
        }


# ============================================================================
# EXCEL WRITER
# ============================================================================

class ExcelWriter:
    """Writes bet tracking data to Excel file"""
    
    def __init__(self, excel_path: str):
        self.excel_path = Path(excel_path)
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
    
    def write_bet_record(self, bet_record):
        """Write a bet record to Excel"""
        if hasattr(bet_record, 'to_dict'):
            bet_record = bet_record.to_dict()
        self.append_bet_record(bet_record)
    
    def append_bet_record(self, bet_record: Dict[str, Any]):
        """Append a bet record to Excel file"""
        try:
            if self.excel_path.exists():
                df = pd.read_excel(self.excel_path)
            else:
                df = pd.DataFrame(columns=[
                    "Bet_ID", "Match_ID", "Match", "Competition",
                    "Minute_of_Entry", "Live_Score_at_Entry", "Target_Score_Used",
                    "Market_Name", "Selection",
                    "Best_BACK_Under_X5", "Reference_Under_X5_Odds",
                    "Best_LAY_Over_X5", "Final_LAY_Price",
                    "Spread_Ticks", "Liability_Percent", "Liability_Amount",
                    "Lay_Stake", "Odds",
                    "Bet_Time", "Starting_Bankroll",
                    "Outcome", "Profit_Loss", "Updated_Bankroll",
                    "Status", "Settled_At"
                ])
            
            if 'Bet_Time' in bet_record:
                if isinstance(bet_record['Bet_Time'], str):
                    try:
                        bet_record['Bet_Time'] = pd.to_datetime(bet_record['Bet_Time'])
                    except:
                        pass
            
            if 'Settled_At' in bet_record:
                if isinstance(bet_record['Settled_At'], str) and bet_record['Settled_At']:
                    try:
                        bet_record['Settled_At'] = pd.to_datetime(bet_record['Settled_At'])
                    except:
                        pass
                elif bet_record.get('Settled_At') == '' or bet_record.get('Settled_At') is None:
                    bet_record['Settled_At'] = None
            
            new_row = pd.DataFrame([bet_record])
            df = pd.concat([df, new_row], ignore_index=True)
            
            if 'Bet_Time' in df.columns:
                df['Bet_Time'] = pd.to_datetime(df['Bet_Time'], errors='coerce')
            if 'Settled_At' in df.columns:
                df['Settled_At'] = pd.to_datetime(df['Settled_At'], errors='coerce')
                df['Settled_At'] = df['Settled_At'].where(pd.notna(df['Settled_At']), None)
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                worksheet = writer.sheets['Sheet1']
                if 'Bet_Time' in df.columns:
                    worksheet.column_dimensions['H'].width = 20
                if 'Settled_At' in df.columns:
                    worksheet.column_dimensions['N'].width = 20
            
            logger.info(f"Bet record appended to Excel: {bet_record.get('Bet_ID', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error appending bet record to Excel: {str(e)}")
            raise
    
    def update_bet_record(self, bet_id: str, updates: Dict[str, Any]):
        """Update an existing bet record in Excel"""
        try:
            if not self.excel_path.exists():
                logger.warning(f"Excel file not found: {self.excel_path}")
                return
            
            df = pd.read_excel(self.excel_path)
            
            mask = df['Bet_ID'] == bet_id
            if not mask.any():
                logger.warning(f"Bet ID {bet_id} not found in Excel file")
                return
            
            for key, value in updates.items():
                if key in df.columns:
                    df.loc[mask, key] = value
            
            if 'Bet_Time' in df.columns:
                df['Bet_Time'] = pd.to_datetime(df['Bet_Time'], errors='coerce')
            if 'Settled_At' in df.columns:
                df['Settled_At'] = pd.to_datetime(df['Settled_At'], errors='coerce')
                df['Settled_At'] = df['Settled_At'].where(pd.notna(df['Settled_At']), None)
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                worksheet = writer.sheets['Sheet1']
                if 'Bet_Time' in df.columns:
                    worksheet.column_dimensions['H'].width = 20
                if 'Settled_At' in df.columns:
                    worksheet.column_dimensions['N'].width = 20
            
            logger.info(f"Bet record updated in Excel: {bet_id}")
            
        except Exception as e:
            logger.error(f"Error updating bet record in Excel: {str(e)}")
            raise
    
    def get_all_bets(self) -> pd.DataFrame:
        """Get all bet records from Excel"""
        try:
            if not self.excel_path.exists():
                return pd.DataFrame()
            
            df = pd.read_excel(self.excel_path)
            return df
            
        except Exception as e:
            logger.error(f"Error reading bets from Excel: {str(e)}")
            return pd.DataFrame()
    
    def get_performance_by_competition(self) -> pd.DataFrame:
        """Calculate performance by competition from Excel data"""
        try:
            df = self.get_all_bets()
            if df.empty:
                return pd.DataFrame()
            
            performance = df.groupby('Competition').agg({
                'Bet_ID': 'count',
                'Stake': 'sum',
                'Profit_Loss': 'sum',
                'Outcome': lambda x: (x == 'Won').sum()
            }).rename(columns={
                'Bet_ID': 'Total_Bets',
                'Stake': 'Total_Stake',
                'Profit_Loss': 'Total_Profit_Loss',
                'Outcome': 'Wins'
            })
            
            performance['Losses'] = performance['Total_Bets'] - performance['Wins']
            performance['Win_Rate'] = (performance['Wins'] / performance['Total_Bets'] * 100).round(2)
            performance['ROI'] = (performance['Total_Profit_Loss'] / performance['Total_Stake'] * 100).round(2)
            
            return performance
            
        except Exception as e:
            logger.error(f"Error calculating performance by competition: {str(e)}")
            return pd.DataFrame()


# ============================================================================
# SKIPPED MATCHES WRITER
# ============================================================================

class SkippedMatchesWriter:
    """Writes skipped matches data to Excel file"""
    
    def __init__(self, excel_path: str):
        self.excel_path = Path(excel_path)
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
    
    def write_skipped_match(self, skipped_data: Dict[str, Any]):
        """Write a skipped match record to Excel file"""
        try:
            if self.excel_path.exists():
                df = pd.read_excel(self.excel_path)
            else:
                df = pd.DataFrame(columns=[
                    "Date", "Match_Name", "Competition", "Minute_75_Score",
                    "Targets_List", "Reason", "BestBack", "BestLay", "Spread_Ticks",
                    "Current_Odds", "Timestamp"
                ])
            
            timestamp = skipped_data.get("timestamp", datetime.now())
            if isinstance(timestamp, str):
                try:
                    timestamp = pd.to_datetime(timestamp)
                except:
                    timestamp = datetime.now()
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.now()
            
            date_str = timestamp.strftime("%Y-%m-%d") if isinstance(timestamp, datetime) else datetime.now().strftime("%Y-%m-%d")
            
            targets_list = skipped_data.get("targets_list", "")
            if isinstance(targets_list, (list, set)):
                targets_list = ", ".join(sorted(str(t) for t in targets_list))
            
            new_row = {
                "Date": date_str,
                "Match_Name": skipped_data.get("match_name", ""),
                "Competition": skipped_data.get("competition", ""),
                "Minute_75_Score": skipped_data.get("minute_75_score", skipped_data.get("minute", "")),
                "Targets_List": targets_list,
                "Reason": skipped_data.get("reason", ""),
                "BestBack": skipped_data.get("best_back", 0.0),
                "BestLay": skipped_data.get("best_lay", 0.0),
                "Spread_Ticks": skipped_data.get("spread_ticks", 0.0),
                "Current_Odds": skipped_data.get("current_odds", 0.0),
                "Timestamp": timestamp
            }
            
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
            
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                worksheet = writer.sheets['Sheet1']
                if 'Timestamp' in df.columns:
                    worksheet.column_dimensions['J'].width = 20
            
            logger.info(f"Skipped match recorded: {skipped_data.get('match_name', 'N/A')} - {skipped_data.get('reason', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error writing skipped match to Excel: {str(e)}")
            raise


# ============================================================================
# TRACKING LIST LOGGER
# ============================================================================

def log_tracking_list(match_tracker_manager, excel_path: Optional[str] = None):
    """
    Log tracking list for all active trackers with real-time data
    
    Args:
        match_tracker_manager: MatchTrackerManager instance
        excel_path: Optional path to Excel file for target scores
    """
    if not match_tracker_manager:
        return
    
    from logic.match_tracker import MatchState
    
    # Cleanup discarded trackers before logging
    match_tracker_manager.cleanup_discarded()
    
    all_trackers = match_tracker_manager.get_all_trackers()
    # Filter out DISQUALIFIED and FINISHED trackers
    active_trackers = [t for t in all_trackers 
                     if t.state != MatchState.DISQUALIFIED 
                     and t.state != MatchState.FINISHED]
    
    if not active_trackers:
        return
    
    logger.info("")
    logger.info("📊 Tracking List (Betfair event name + Live event name + min + score)")
    
    # Get Excel path if not provided
    if not excel_path:
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
        excel_path = str(excel_path) if excel_path.exists() else None
    
    for idx, tracker in enumerate(active_trackers, 1):
        # Get target scores from Excel for this competition
        target_scores = []
        if excel_path:
            from logic.qualification import get_competition_targets
            targets = get_competition_targets(tracker.competition_name, excel_path)
            if targets:
                target_scores = sorted(list(targets))
        
        # Format target scores
        targets_str = ", ".join(target_scores) if target_scores else "N/A"
        
        # Format: "Betfair event name + Live API event name (min, score) [target scores]"
        # Use latest data from tracker (updated every 15s)
        betfair_name = tracker.betfair_event_name
        live_name = tracker.live_event_name
        log_line = f"{idx}. {betfair_name} + {live_name} (min {tracker.current_minute}, score {tracker.current_score}) [{targets_str}]"
        logger.info(log_line)
    
    logger.info("")

