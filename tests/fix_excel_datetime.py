"""Fix datetime columns in existing Excel files"""
import pandas as pd
from pathlib import Path

print("=" * 60)
print("Fixing datetime columns in Excel files")
print("=" * 60)

# Fix Bet_Records.xlsx
excel1 = Path('competitions/Bet_Records.xlsx')
if excel1.exists():
    print(f"\n1. Fixing {excel1.name}...")
    df1 = pd.read_excel(excel1)
    
    print(f"   Current Bet_Time type: {df1['Bet_Time'].dtype}")
    
    # Convert Bet_Time to datetime
    if df1['Bet_Time'].dtype == 'object':
        df1['Bet_Time'] = pd.to_datetime(df1['Bet_Time'], errors='coerce')
        print(f"   ✅ Converted Bet_Time to datetime")
    else:
        print(f"   ✅ Bet_Time already datetime")
    
    # Convert Settled_At to datetime
    if 'Settled_At' in df1.columns:
        if df1['Settled_At'].dtype == 'object':
            df1['Settled_At'] = pd.to_datetime(df1['Settled_At'], errors='coerce')
            print(f"   ✅ Converted Settled_At to datetime")
        elif df1['Settled_At'].dtype == 'float64':
            # NaN values, keep as is
            print(f"   ✅ Settled_At is float (NaN for pending bets)")
    
    # Save back with column width and format Settled_At
    if 'Settled_At' in df1.columns:
        df1['Settled_At'] = pd.to_datetime(df1['Settled_At'], errors='coerce')
        df1['Settled_At'] = df1['Settled_At'].where(pd.notna(df1['Settled_At']), None)
    
    with pd.ExcelWriter(excel1, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='Sheet1')
        worksheet = writer.sheets['Sheet1']
        if 'Bet_Time' in df1.columns:
            worksheet.column_dimensions['H'].width = 20
        if 'Settled_At' in df1.columns:
            worksheet.column_dimensions['N'].width = 20
    
    print(f"   ✅ Saved {excel1.name}")
    
    # Verify
    df1_check = pd.read_excel(excel1)
    print(f"   Verified: Bet_Time is now {df1_check['Bet_Time'].dtype}")
else:
    print(f"\n1. {excel1.name} not found (will be created on next bet)")

# Fix Skipped Matches.xlsx
excel2 = Path('competitions/Skipped Matches.xlsx')
if excel2.exists():
    print(f"\n2. Fixing {excel2.name}...")
    df2 = pd.read_excel(excel2)
    
    if 'Timestamp' in df2.columns:
        print(f"   Current Timestamp type: {df2['Timestamp'].dtype}")
        
        if df2['Timestamp'].dtype == 'object':
            df2['Timestamp'] = pd.to_datetime(df2['Timestamp'], errors='coerce')
            print(f"   ✅ Converted Timestamp to datetime")
        else:
            print(f"   ✅ Timestamp already datetime")
        
        # Save back with column width
        with pd.ExcelWriter(excel2, engine='openpyxl') as writer:
            df2.to_excel(writer, index=False, sheet_name='Sheet1')
            worksheet = writer.sheets['Sheet1']
            if 'Timestamp' in df2.columns:
                worksheet.column_dimensions['J'].width = 20
                print(f"   ✅ Set Timestamp column width to 20")
        
        print(f"   ✅ Saved {excel2.name}")
        
        # Verify
        df2_check = pd.read_excel(excel2)
        print(f"   Verified: Timestamp is now {df2_check['Timestamp'].dtype}")
else:
    print(f"\n2. {excel2.name} not found (will be created on next skip)")

print("\n" + "=" * 60)
print("✅ Done! Please close and reopen Excel to see the changes.")
print("=" * 60)

