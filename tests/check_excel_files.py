"""Check Excel files for Time column issues and data validation"""
import pandas as pd
from pathlib import Path
from datetime import datetime

print("=" * 60)
print("1. BET_RECORDS.XLSX")
print("=" * 60)

excel1 = Path('competitions/Bet_Records.xlsx')
if excel1.exists():
    df1 = pd.read_excel(excel1)
    print(f"✅ File exists")
    print(f"Total rows: {len(df1)}")
    print(f"\nColumns: {list(df1.columns)}")
    
    if len(df1) > 0:
        print(f"\n📊 Last row data:")
        last_row = df1.iloc[-1]
        for col in df1.columns:
            value = last_row[col]
            dtype = df1[col].dtype
            print(f"  {col}: {value} (type: {dtype})")
        
        # Check Bet_Time column
        if 'Bet_Time' in df1.columns:
            print(f"\n🔍 Bet_Time column analysis:")
            print(f"  Type: {df1['Bet_Time'].dtype}")
            print(f"  Sample value: {df1['Bet_Time'].iloc[-1]}")
            print(f"  Is datetime: {pd.api.types.is_datetime64_any_dtype(df1['Bet_Time'])}")
            
            # Check if it's a string
            if df1['Bet_Time'].dtype == 'object':
                try:
                    # Try to parse as datetime
                    parsed = pd.to_datetime(df1['Bet_Time'].iloc[-1])
                    print(f"  ✅ Can be parsed as datetime: {parsed}")
                except:
                    print(f"  ❌ Cannot be parsed as datetime")
        
        # Check Settled_At column
        if 'Settled_At' in df1.columns:
            print(f"\n🔍 Settled_At column analysis:")
            print(f"  Type: {df1['Settled_At'].dtype}")
            print(f"  Sample value: {df1['Settled_At'].iloc[-1]}")
            print(f"  Is datetime: {pd.api.types.is_datetime64_any_dtype(df1['Settled_At'])}")
            
            # Check if it's a string
            if df1['Settled_At'].dtype == 'object':
                sample = df1['Settled_At'].iloc[-1]
                if pd.isna(sample) or sample == '':
                    print(f"  ✅ Empty/NaN (expected for pending bets)")
                else:
                    try:
                        parsed = pd.to_datetime(sample)
                        print(f"  ✅ Can be parsed as datetime: {parsed}")
                    except:
                        print(f"  ❌ Cannot be parsed as datetime")
    else:
        print("No data in file")
else:
    print("❌ File not found")

print("\n" + "=" * 60)
print("2. SKIPPED MATCHES.XLSX")
print("=" * 60)

excel2 = Path('competitions/Skipped Matches.xlsx')
if excel2.exists():
    df2 = pd.read_excel(excel2)
    print(f"✅ File exists")
    print(f"Total rows: {len(df2)}")
    print(f"\nColumns: {list(df2.columns)}")
    
    if len(df2) > 0:
        print(f"\n📊 Last 3 rows:")
        print(df2.tail(3).to_string())
        
        # Check Time column if exists
        if 'Time' in df2.columns:
            print(f"\n🔍 Time column analysis:")
            print(f"  Type: {df2['Time'].dtype}")
            print(f"  Sample values:")
            for idx, val in df2['Time'].tail(3).items():
                print(f"    Row {idx}: {val} (type: {type(val).__name__})")
            
            # Check if it's a string
            if df2['Time'].dtype == 'object':
                print(f"  ⚠️  Time column is object type (string), not datetime")
                print(f"  This may cause ### display in Excel if format is wrong")
    else:
        print("No data in file")
else:
    print("❌ File not found")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("Issue with ### in Excel Time column usually means:")
print("1. Column width too narrow (Excel display issue)")
print("2. Value is string instead of datetime object")
print("3. Date format not recognized by Excel")
print("\nSolution: Use datetime objects when writing to Excel")

