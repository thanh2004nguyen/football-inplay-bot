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
        # Logging moved to main.py setup checklist
    
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
                # Create new DataFrame with columns (per client requirements)
                df = pd.DataFrame(columns=[
                    "Date", "Match_Name", "Competition", "Minute_75_Score",
                    "Targets_List", "Reason", "BestBack", "BestLay", "Spread_Ticks",
                    "Current_Odds", "Timestamp"
                ])
            
            # Prepare new row
            timestamp = skipped_data.get("timestamp", datetime.now())
            # Ensure timestamp is a datetime object, not string
            if isinstance(timestamp, str):
                try:
                    timestamp = pd.to_datetime(timestamp)
                except:
                    timestamp = datetime.now()
            elif not isinstance(timestamp, datetime):
                timestamp = datetime.now()
            
            # Format date (extract date from timestamp)
            date_str = timestamp.strftime("%Y-%m-%d") if isinstance(timestamp, datetime) else datetime.now().strftime("%Y-%m-%d")
            
            # Get targets list if available
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
                "Timestamp": timestamp  # Always datetime object
            }
            
            # Append new record
            new_df = pd.DataFrame([new_row])
            df = pd.concat([df, new_df], ignore_index=True)
            
            # Ensure Timestamp column is datetime
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            
            # Save to Excel with datetime format
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                # Get the worksheet to set column width for Timestamp
                worksheet = writer.sheets['Sheet1']
                if 'Timestamp' in df.columns:
                    # Set column width for Timestamp (column J)
                    worksheet.column_dimensions['J'].width = 20
            
            logger.info(f"Skipped match recorded: {skipped_data.get('match_name', 'N/A')} - {skipped_data.get('reason', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error writing skipped match to Excel: {str(e)}")
            raise

