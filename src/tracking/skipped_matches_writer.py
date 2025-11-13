"""
Skipped Matches Writer Module
Writes skipped matches to Excel file for analysis
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class SkippedMatchesWriter:
    """Writes skipped matches data to Excel file"""
    
    def __init__(self, excel_path: str):
        """
        Initialize skipped matches writer
        
        Args:
            excel_path: Path to Excel file (e.g., "competitions/Skipped Matches.xlsx")
        """
        self.excel_path = Path(excel_path)
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Skipped matches writer initialized: {excel_path}")
    
    def write_skipped_match(self, skipped_data: Dict[str, Any]):
        """
        Write a skipped match record to Excel file
        
        Args:
            skipped_data: Dictionary containing:
                - match_name: str
                - competition: str
                - minute: int or str
                - status: str
                - reason: str (reason why skipped)
                - best_back: float
                - best_lay: float
                - spread_ticks: float or int
                - current_odds: float (best lay price)
                - timestamp: datetime or str
        """
        try:
            # Try to read existing file
            if self.excel_path.exists():
                df = pd.read_excel(self.excel_path)
            else:
                # Create new DataFrame with columns
                df = pd.DataFrame(columns=[
                    "Match_Name", "Competition", "Minute", "Status",
                    "Reason", "BestBack", "BestLay", "Spread_Ticks",
                    "Current_Odds", "Timestamp"
                ])
            
            # Prepare new row
            new_row = {
                "Match_Name": skipped_data.get("match_name", ""),
                "Competition": skipped_data.get("competition", ""),
                "Minute": skipped_data.get("minute", ""),
                "Status": skipped_data.get("status", ""),
                "Reason": skipped_data.get("reason", ""),
                "BestBack": skipped_data.get("best_back", 0.0),
                "BestLay": skipped_data.get("best_lay", 0.0),
                "Spread_Ticks": skipped_data.get("spread_ticks", 0.0),
                "Current_Odds": skipped_data.get("current_odds", 0.0),
                "Timestamp": skipped_data.get("timestamp", datetime.now())
            }
            
            # Append new record
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
            
            # Save to Excel
            df.to_excel(self.excel_path, index=False)
            
            logger.info(f"Skipped match recorded: {skipped_data.get('match_name', 'N/A')} - {skipped_data.get('reason', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error writing skipped match to Excel: {str(e)}")
            raise

