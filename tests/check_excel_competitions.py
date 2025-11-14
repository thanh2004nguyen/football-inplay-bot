"""
Script to check competitions in Excel file
Lists all unique competitions and their details
"""
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def check_excel_competitions():
    """Check competitions in Excel file"""
    print("=" * 80)
    print("Checking Competitions in Excel File")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    
    if not excel_path.exists():
        print(f"❌ Excel file not found: {excel_path}")
        return
    
    try:
        # Read Excel file
        df = pd.read_excel(excel_path)
        
        print(f"\n📋 Excel File: {excel_path}")
        print(f"📊 Total rows: {len(df)}")
        print(f"📋 Columns: {', '.join(df.columns.tolist())}")
        
        # Check for new columns
        has_competition_live = 'Competition-Live' in df.columns
        has_competition_betfair = 'Competition-Betfair' in df.columns
        has_competition_old = 'Competition' in df.columns
        
        print(f"\n📋 Column Status:")
        print(f"  - Competition (old): {'✅' if has_competition_old else '❌'}")
        print(f"  - Competition-Live (new): {'✅' if has_competition_live else '❌'}")
        print(f"  - Competition-Betfair (new): {'✅' if has_competition_betfair else '❌'}")
        
        # Get unique competitions
        if has_competition_old:
            competitions_old = df['Competition'].dropna().unique().tolist()
            print(f"\n📊 Competitions (old column): {len(competitions_old)} unique")
            for idx, comp in enumerate(sorted(competitions_old), 1):
                count = len(df[df['Competition'] == comp])
                print(f"  {idx:3d}. {comp:40s} ({count} rows)")
        
        if has_competition_live and has_competition_betfair:
            # Show mapping
            print(f"\n📊 Competition Mapping (Live -> Betfair):")
            mapping_df = df[['Competition-Live', 'Competition-Betfair']].drop_duplicates()
            mapping_df = mapping_df.sort_values('Competition-Live')
            
            for idx, row in mapping_df.iterrows():
                live = str(row['Competition-Live']) if pd.notna(row['Competition-Live']) else 'N/A'
                betfair = str(row['Competition-Betfair']) if pd.notna(row['Competition-Betfair']) else 'N/A'
                print(f"  {live:40s} -> {betfair}")
            
            # Check for missing mappings with row details
            missing_live_rows = df[df['Competition-Live'].isna()]
            missing_betfair_rows = df[df['Competition-Betfair'].isna()]
            
            if not missing_live_rows.empty or not missing_betfair_rows.empty:
                print(f"\n⚠ Missing mappings:")
                if not missing_live_rows.empty:
                    print(f"  - Rows with missing Competition-Live: {len(missing_live_rows)}")
                    print(f"    Details:")
                    for idx, row in missing_live_rows.iterrows():
                        comp_old = row.get('Competition', 'N/A')
                        comp_betfair = str(row.get('Competition-Betfair', 'N/A')) if pd.notna(row.get('Competition-Betfair')) else 'N/A'
                        result = row.get('Result', 'N/A')
                        print(f"      Row {idx + 2}: Competition='{comp_old}', Competition-Betfair='{comp_betfair}', Result='{result}'")
                
                if not missing_betfair_rows.empty:
                    print(f"  - Rows with missing Competition-Betfair: {len(missing_betfair_rows)}")
                    print(f"    Details:")
                    for idx, row in missing_betfair_rows.iterrows():
                        comp_old = row.get('Competition', 'N/A')
                        comp_live = str(row.get('Competition-Live', 'N/A')) if pd.notna(row.get('Competition-Live')) else 'N/A'
                        result = row.get('Result', 'N/A')
                        print(f"      Row {idx + 2}: Competition='{comp_old}', Competition-Live='{comp_live}', Result='{result}'")
        
        # Show sample rows
        print(f"\n📋 Sample Rows (first 5):")
        print(df.head().to_string())
        
        print("\n" + "=" * 80)
        print("✅ Check completed!")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        check_excel_competitions()
    except KeyboardInterrupt:
        print("\n\nCheck interrupted by user")
    except Exception as e:
        print(f"\n❌ Check failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

