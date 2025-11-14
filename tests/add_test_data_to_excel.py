"""
Script to add test data to existing Excel file
Adds row for "4_Serie A" with Result "1-1" if not exists
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import pandas as pd

excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"

if not excel_path.exists():
    print(f"❌ Excel file not found: {excel_path}")
    sys.exit(1)

print(f"✅ Reading Excel file: {excel_path}")
df = pd.read_excel(excel_path)

# Check if row already exists
existing = df[
    (df['Competition-Live'] == "4_Serie A") & 
    (df['Result'].astype(str).str.strip() == "1-1")
]

if not existing.empty:
    print(f"✅ Row already exists: Competition-Live='4_Serie A', Result='1-1'")
    print(f"   Stake: {existing.iloc[0]['Stake']}")
    sys.exit(0)

# Find a row with "4_Serie A" to use as template
template = df[df['Competition-Live'] == "4_Serie A"]
if template.empty:
    print(f"❌ No template row found for '4_Serie A'")
    sys.exit(1)

# Create new row based on template
new_row = template.iloc[0].copy()
new_row['Result'] = "1-1"
new_row['Stake'] = 5.0  # Set stake to 5.0 for test

# Add new row
df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Save back to Excel
df.to_excel(excel_path, index=False)
print(f"✅ Added row: Competition-Live='4_Serie A', Result='1-1', Stake=5.0")
print(f"✅ Excel file updated: {excel_path}")

