"""
Excel Writer Module
Writes bet records to Excel file
"""
import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class ExcelWriter:
    """Writes bet tracking data to Excel file"""
    
    def __init__(self, excel_path: str):
        """
        Initialize Excel writer
        
        Args:
            excel_path: Path to Excel file
        """
        self.excel_path = Path(excel_path)
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Excel writer initialized: {excel_path}")
    
    def append_bet_record(self, bet_record: Dict[str, Any]):
        """
        Append a bet record to Excel file
        
        Args:
            bet_record: Bet record dictionary
        """
        try:
            # Try to read existing file
            if self.excel_path.exists():
                df = pd.read_excel(self.excel_path)
            else:
                # Create new DataFrame with columns
                df = pd.DataFrame(columns=[
                    "Bet_ID", "Match_ID", "Competition", "Market_Name", "Selection",
                    "Odds", "Stake", "Bet_Time", "Outcome", "Profit_Loss",
                    "Bankroll_Before", "Bankroll_After", "Status", "Settled_At"
                ])
            
            # Append new record
            new_row = pd.DataFrame([bet_record])
            df = pd.concat([df, new_row], ignore_index=True)
            
            # Save to Excel
            df.to_excel(self.excel_path, index=False)
            
            logger.info(f"Bet record appended to Excel: {bet_record.get('Bet_ID', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error appending bet record to Excel: {str(e)}")
            raise
    
    def update_bet_record(self, bet_id: str, updates: Dict[str, Any]):
        """
        Update an existing bet record in Excel
        
        Args:
            bet_id: Bet ID
            updates: Dictionary of fields to update
        """
        try:
            if not self.excel_path.exists():
                logger.warning(f"Excel file not found: {self.excel_path}")
                return
            
            df = pd.read_excel(self.excel_path)
            
            # Find row with matching Bet_ID
            mask = df['Bet_ID'] == bet_id
            if not mask.any():
                logger.warning(f"Bet ID {bet_id} not found in Excel file")
                return
            
            # Update fields
            for key, value in updates.items():
                if key in df.columns:
                    df.loc[mask, key] = value
            
            # Save to Excel
            df.to_excel(self.excel_path, index=False)
            
            logger.info(f"Bet record updated in Excel: {bet_id}")
            
        except Exception as e:
            logger.error(f"Error updating bet record in Excel: {str(e)}")
            raise
    
    def get_all_bets(self) -> pd.DataFrame:
        """
        Get all bet records from Excel
        
        Returns:
            DataFrame with all bet records
        """
        try:
            if not self.excel_path.exists():
                return pd.DataFrame()
            
            df = pd.read_excel(self.excel_path)
            return df
            
        except Exception as e:
            logger.error(f"Error reading bets from Excel: {str(e)}")
            return pd.DataFrame()
    
    def get_performance_by_competition(self) -> pd.DataFrame:
        """
        Calculate performance by competition from Excel data
        
        Returns:
            DataFrame with performance statistics by competition
        """
        try:
            df = self.get_all_bets()
            if df.empty:
                return pd.DataFrame()
            
            # Group by competition
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

