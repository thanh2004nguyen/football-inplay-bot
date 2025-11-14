"""
Script to create test Excel file for testing
This creates a minimal Excel file with test data matching the scenarios
"""
import pandas as pd
from pathlib import Path

def create_test_excel():
    """Create test Excel file with data for test scenarios"""
    project_root = Path(__file__).parent.parent
    
    # Test data matching scenarios
    # Note: This matches the test scenarios in test_scenarios.json
    test_data = [
        {
            "Competition-Live": "4_Serie A",
            "Competition-Betfair": "81_Italian Serie A",
            "Result": "1-1",
            "Stake": 5.0,
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        },
        {
            "Competition-Live": "4_Serie A",
            "Competition-Betfair": "81_Italian Serie A",
            "Result": "0-0",
            "Stake": 3.0,
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        },
        {
            "Competition-Live": "4_Serie A",
            "Competition-Betfair": "81_Italian Serie A",
            "Result": "0-3",
            "Stake": 0.0,  # Out of target
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        },
        {
            "Competition-Live": "4_Serie A",
            "Competition-Betfair": "81_Italian Serie A",
            "Result": "1-0",
            "Stake": 4.0,
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        },
        {
            "Competition-Live": "24_Serie A",
            "Competition-Betfair": "13_Brazilian Serie A",
            "Result": "1-1",
            "Stake": 5.0,
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        },
        {
            "Competition-Live": "2_Premier League",
            "Competition-Betfair": "10932509_English Premier League",
            "Result": "1-1",
            "Stake": 5.0,
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        },
        {
            "Competition-Live": "3_LaLiga Santander",
            "Competition-Betfair": "117_Spanish La Liga",
            "Result": "1-1",
            "Stake": 5.0,
            "Min Odds": 1.5,
            "Max Odds": 10.0,
            "Max Spread Ticks": 4
        }
    ]
    
    # Create DataFrame
    df = pd.DataFrame(test_data)
    
    # Save to test Excel file
    test_excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake_TEST.xlsx"
    df.to_excel(test_excel_path, index=False)
    
    print(f"✅ Test Excel file created: {test_excel_path}")
    print(f"\nTest data:")
    print(df.to_string(index=False))
    print(f"\n⚠️  IMPORTANT:")
    print(f"   This is a TEST file. To use it for testing:")
    print(f"   1. Backup your original file: Competitions_Results_Odds_Stake.xlsx")
    print(f"   2. Copy test file: {test_excel_path.name} -> Competitions_Results_Odds_Stake.xlsx")
    print(f"   3. Or manually add these rows to your existing Excel file")
    print(f"\n   Required for scenario_1_happy_path:")
    print(f"   - Competition-Live: '4_Serie A'")
    print(f"   - Result: '1-1'")
    print(f"   - Stake: 5.0 (or any value)")

if __name__ == "__main__":
    create_test_excel()

