"""
Bet Tracker Module
Tracks bets, outcomes, and calculates bankroll
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class BetRecord:
    """Represents a single bet record"""
    
    def __init__(self, bet_id: str, match_id: str, competition: str,
                 market_name: str, selection: str, odds: float, stake: float,
                 bet_time: datetime, bankroll_before: float):
        """
        Initialize bet record
        
        Args:
            bet_id: Unique bet ID
            match_id: Match/Event ID
            competition: Competition name
            market_name: Market name (e.g., "Over/Under 2.5 Goals")
            selection: Selection name (e.g., "Over 2.5")
            odds: Odds at time of bet
            stake: Stake amount
            bet_time: When bet was placed
            bankroll_before: Bankroll before bet
        """
        self.bet_id = bet_id
        self.match_id = match_id
        self.competition = competition
        self.market_name = market_name
        self.selection = selection
        self.odds = odds
        self.stake = stake
        self.bet_time = bet_time
        self.bankroll_before = bankroll_before
        
        # To be updated later
        self.outcome: Optional[str] = None  # "Won", "Lost", "Pending", "Void"
        self.profit_loss: Optional[float] = None
        self.bankroll_after: Optional[float] = None
        self.settled_at: Optional[datetime] = None
        self.status = "Pending"
    
    def settle(self, outcome: str, profit_loss: float, bankroll_after: float):
        """
        Settle bet with outcome
        
        Args:
            outcome: "Won", "Lost", "Void"
            profit_loss: Profit or loss amount
            bankroll_after: Bankroll after bet settlement
        """
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
            "Competition": self.competition,
            "Market_Name": self.market_name,
            "Selection": self.selection,
            "Odds": self.odds,
            "Stake": self.stake,
            "Bet_Time": self.bet_time.isoformat(),
            "Outcome": self.outcome or "Pending",
            "Profit_Loss": self.profit_loss if self.profit_loss is not None else 0.0,
            "Bankroll_Before": self.bankroll_before,
            "Bankroll_After": self.bankroll_after if self.bankroll_after is not None else self.bankroll_before,
            "Status": self.status,
            "Settled_At": self.settled_at.isoformat() if self.settled_at else ""
        }


class BetTracker:
    """Tracks all bets and manages bankroll"""
    
    def __init__(self, initial_bankroll: float = 0.0):
        """
        Initialize bet tracker
        
        Args:
            initial_bankroll: Initial bankroll amount
        """
        self.bets: Dict[str, BetRecord] = {}  # Key: bet_id
        self.current_bankroll = initial_bankroll
        self.initial_bankroll = initial_bankroll
        
        logger.info(f"Bet tracker initialized with bankroll: {initial_bankroll:.2f}")
    
    def record_bet(self, bet_id: str, match_id: str, competition: str,
                   market_name: str, selection: str, odds: float, stake: float) -> BetRecord:
        """
        Record a new bet
        
        Args:
            bet_id: Unique bet ID
            match_id: Match/Event ID
            competition: Competition name
            market_name: Market name
            selection: Selection name
            odds: Odds at time of bet
            stake: Stake amount
        
        Returns:
            BetRecord instance
        """
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
            bankroll_before=bankroll_before
        )
        
        self.bets[bet_id] = bet_record
        
        # Update bankroll (subtract stake)
        self.current_bankroll -= stake
        
        logger.info(f"Bet recorded: {bet_id}, Stake: {stake:.2f}, Bankroll: {bankroll_before:.2f} -> {self.current_bankroll:.2f}")
        
        return bet_record
    
    def settle_bet(self, bet_id: str, outcome: str) -> Optional[BetRecord]:
        """
        Settle a bet with outcome
        
        Args:
            bet_id: Bet ID
            outcome: "Won", "Lost", "Void"
        
        Returns:
            BetRecord instance, or None if not found
        """
        bet_record = self.bets.get(bet_id)
        if not bet_record:
            logger.warning(f"Bet {bet_id} not found for settlement")
            return None
        
        # Calculate profit/loss
        if outcome == "Won":
            profit_loss = (bet_record.odds - 1) * bet_record.stake
        elif outcome == "Lost":
            profit_loss = -bet_record.stake
        elif outcome == "Void":
            profit_loss = 0.0  # Stake returned
        else:
            logger.warning(f"Unknown outcome: {outcome}")
            profit_loss = 0.0
        
        # Update bankroll
        bankroll_after = self.current_bankroll + profit_loss + bet_record.stake
        self.current_bankroll = bankroll_after
        
        # Settle bet
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
        """
        Calculate performance statistics by competition
        
        Returns:
            Dictionary with competition as key and stats as value
        """
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

