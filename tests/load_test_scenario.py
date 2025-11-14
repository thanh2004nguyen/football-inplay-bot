"""
Script to load test scenario into config.json
Usage: python tests/load_test_scenario.py scenario_1_happy_path
"""
import sys
import json
from pathlib import Path

def load_scenario(scenario_name: str):
    """Load a test scenario and update config.json"""
    project_root = Path(__file__).parent.parent
    
    # Load test scenarios
    scenarios_path = project_root / "tests" / "mock_data" / "test_scenarios.json"
    if not scenarios_path.exists():
        print(f"❌ Test scenarios file not found: {scenarios_path}")
        return False
    
    with open(scenarios_path, 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    if scenario_name not in scenarios:
        print(f"❌ Scenario '{scenario_name}' not found")
        print(f"Available scenarios: {[k for k in scenarios.keys() if not k.startswith('_')]}")
        return False
    
    scenario_data = scenarios[scenario_name]
    
    # Load config.json
    config_path = project_root / "config" / "config.json"
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Update test_mode config
    if "test_mode" not in config:
        config["test_mode"] = {}
    
    config["test_mode"]["enabled"] = True
    config["test_mode"]["simulate_bet_matched"] = scenario_data.get("simulate_bet_matched", False)
    config["test_mode"]["mock_data"] = {
        "live_matches": scenario_data.get("live_matches", []),
        "markets": scenario_data.get("markets", []),
        "market_books": scenario_data.get("market_books", {}),
        "match_details": scenario_data.get("match_details", {}),
        "account_balance": scenario_data.get("account_balance", 1000.0)
    }
    
    # Save config
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Scenario '{scenario_name}' loaded into config.json")
    print(f"   Description: {scenario_data.get('_description', 'N/A')}")
    print(f"   Test mode enabled: {config['test_mode']['enabled']}")
    print(f"   Simulate bet matched: {config['test_mode'].get('simulate_bet_matched', False)}")
    print(f"   Live matches: {len(config['test_mode']['mock_data']['live_matches'])}")
    print(f"   Markets: {len(config['test_mode']['mock_data']['markets'])}")
    if scenario_data.get('_test_notifications'):
        print(f"   Notifications: {scenario_data.get('_test_notifications')}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/load_test_scenario.py <scenario_name>")
        print("\nAvailable scenarios:")
        print("  scenario_1_happy_path - Happy Path (Bet placed, NOT matched)")
        print("  scenario_1b_happy_path_matched - Happy Path (Bet placed AND matched - TEST NOTIFICATIONS)")
        print("  scenario_combined_bet_and_skip - Combined Test (1 bet placed + 1 skipped)")
        print("  scenario_2_early_discard - Early Discard (Out of target)")
        print("  scenario_3_var_cancelled_goal - VAR Cancelled Goal")
        print("  scenario_4_zero_zero_exception - 0-0 Exception")
        print("  scenario_5_odds_too_low - Odds Too Low")
        print("  scenario_6_spread_too_wide - Spread Too Wide")
        print("  scenario_7_no_liquidity - No Liquidity")
        print("  scenario_8_insufficient_funds - Insufficient Funds")
        print("  scenario_9_no_goal_in_window - No Goal in Window")
        print("  scenario_10_market_unavailable - Market Unavailable")
        sys.exit(1)
    
    scenario_name = sys.argv[1]
    success = load_scenario(scenario_name)
    sys.exit(0 if success else 1)

