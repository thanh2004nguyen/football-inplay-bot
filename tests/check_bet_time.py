"""Check Bet_Time column in Bet_Records.xlsx"""
import pandas as pd
from pathlib import Path

excel = Path('competitions/Bet_Records.xlsx')

if not excel.exists():
    print('❌ File not found')
    exit(1)

df = pd.read_excel(excel)

print('Bet_Time column check:')
print(f'Total rows: {len(df)}')

if len(df) > 0:
    print(f'\nBet_Time column:')
    print(f'  Type: {df["Bet_Time"].dtype}')
    print(f'  Is datetime: {pd.api.types.is_datetime64_any_dtype(df["Bet_Time"])}')
    
    print(f'\nLast row Bet_Time:')
    last_value = df["Bet_Time"].iloc[-1]
    print(f'  Value: {last_value}')
    print(f'  Type of value: {type(last_value).__name__}')
    
    if isinstance(last_value, str):
        print(f'  ⚠️  WARNING: Bet_Time is still a string!')
        print(f'  This will cause ### in Excel')
    elif pd.api.types.is_datetime64_any_dtype(df["Bet_Time"]):
        print(f'  ✅ Bet_Time is datetime - OK!')
    else:
        print(f'  ⚠️  Bet_Time is not datetime type')

