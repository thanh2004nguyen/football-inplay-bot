"""Check Bet Records Excel file"""
import pandas as pd
from pathlib import Path

excel_path = Path('competitions/Bet_Records.xlsx')

if not excel_path.exists():
    print('❌ Excel file not found')
    exit(1)

df = pd.read_excel(excel_path)

print('✅ Bet Records Excel file:')
print(f'Total rows: {len(df)}')
print('\n📊 Latest bet record:')
print(df.tail(1).to_string())

if len(df) > 0:
    last_row = df.iloc[-1]
    print('\n🔍 Key fields check:')
    print(f'  Bet_ID: {last_row["Bet_ID"]}')
    print(f'  Bankroll_Before: {last_row["Bankroll_Before"]}')
    print(f'  Bankroll_After: {last_row["Bankroll_After"]}')
    print(f'  Stake: {last_row["Stake"]}')
    
    expected_after = last_row["Bankroll_Before"] - last_row["Stake"]
    print(f'  Expected Bankroll_After: {expected_after}')
    
    is_match = abs(last_row["Bankroll_After"] - expected_after) < 0.01
    print(f'  ✅ Match: {is_match}')
    
    if not is_match:
        print(f'  ❌ ERROR: Bankroll_After should be {expected_after}, but got {last_row["Bankroll_After"]}')
    else:
        print(f'  ✅ SUCCESS: Bankroll_After is correct!')

