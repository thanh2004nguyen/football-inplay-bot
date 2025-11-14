"""
Script to check Excel file content
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    import pandas as pd
    
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    
    if not excel_path.exists():
        print(f"❌ Excel file not found: {excel_path}")
        sys.exit(1)
    
    print(f"✅ Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    print(f"\nColumns: {df.columns.tolist()}")
    print(f"\nTotal rows: {len(df)}")
    
    # Check Competition-Live column
    if 'Competition-Live' in df.columns:
        print(f"\nCompetition-Live values:")
        comps = df['Competition-Live'].dropna().unique()
        for comp in comps:
            print(f"  - {comp}")
        
        # Check for "4_Serie A"
        if "4_Serie A" in comps:
            print(f"\n✅ Found '4_Serie A' in Competition-Live")
            matches = df[df['Competition-Live'] == "4_Serie A"]
            print(f"   Rows with '4_Serie A': {len(matches)}")
            
            if 'Result' in df.columns:
                results = matches['Result'].dropna().unique()
                print(f"   Available Results for '4_Serie A': {results.tolist()}")
                
                if "1-1" in [str(r).strip() for r in results]:
                    print(f"   ✅ Found '1-1' in Results")
                    stake_row = matches[matches['Result'].astype(str).str.strip() == "1-1"]
                    if not stake_row.empty:
                        stake = stake_row.iloc[0]['Stake'] if 'Stake' in df.columns else 'N/A'
                        print(f"   ✅ Stake value: {stake}")
                else:
                    print(f"   ❌ '1-1' NOT found in Results")
                    print(f"   Available Results: {[str(r).strip() for r in results]}")
        else:
            print(f"\n❌ '4_Serie A' NOT found in Competition-Live")
    else:
        print(f"\n❌ 'Competition-Live' column not found")
    
    # Show first few rows
    print(f"\nFirst 5 rows:")
    print(df.head().to_string())
    
except ImportError as e:
    print(f"❌ Error: {e}")
    print("Please install: pip install openpyxl")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error reading Excel: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

