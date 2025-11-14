"""
Script to run all test scenarios automatically
Usage: python tests/run_all_tests.py
"""
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Dict

def get_all_scenarios() -> List[str]:
    """Get all available test scenarios"""
    project_root = Path(__file__).parent.parent
    scenarios_path = project_root / "tests" / "mock_data" / "test_scenarios.json"
    
    if not scenarios_path.exists():
        print(f"❌ Test scenarios file not found: {scenarios_path}")
        return []
    
    with open(scenarios_path, 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    # Filter out metadata keys
    scenario_names = [k for k in scenarios.keys() if not k.startswith('_')]
    return sorted(scenario_names)

def run_scenario(scenario_name: str) -> bool:
    """Run a single test scenario"""
    print(f"\n{'='*60}")
    print(f"Testing: {scenario_name}")
    print(f"{'='*60}")
    
    # Load scenario
    project_root = Path(__file__).parent.parent
    load_script = project_root / "tests" / "load_test_scenario.py"
    
    result = subprocess.run(
        [sys.executable, str(load_script), scenario_name],
        cwd=str(project_root),
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ Failed to load scenario: {scenario_name}")
        print(result.stderr)
        return False
    
    print(result.stdout)
    
    # Note: Actual bot execution would be done manually or with timeout
    # For now, we just load the scenario
    print(f"✅ Scenario loaded: {scenario_name}")
    print(f"   → Run 'python src/main.py' to test this scenario")
    
    return True

def main():
    """Run all test scenarios"""
    print("="*60)
    print("AUTOMATED TEST RUNNER - All Scenarios")
    print("="*60)
    
    scenarios = get_all_scenarios()
    
    if not scenarios:
        print("❌ No scenarios found")
        return
    
    print(f"\nFound {len(scenarios)} test scenarios:")
    for i, scenario in enumerate(scenarios, 1):
        print(f"  {i}. {scenario}")
    
    print("\n" + "="*60)
    print("NOTE: This script will load each scenario into config.json")
    print("You need to run 'python src/main.py' manually for each scenario")
    print("="*60)
    
    response = input("\nDo you want to load all scenarios? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    results = {}
    for scenario in scenarios:
        success = run_scenario(scenario)
        results[scenario] = success
        
        # Ask if continue
        if scenario != scenarios[-1]:  # Not last scenario
            response = input(f"\nContinue to next scenario? (y/n): ")
            if response.lower() != 'y':
                print("Stopped by user")
                break
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for scenario, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {scenario}")
    
    print("\n" + "="*60)
    print("To test each scenario:")
    print("1. Load scenario: python tests/load_test_scenario.py <scenario_name>")
    print("2. Run bot: python src/main.py")
    print("3. Check logs: logs/betfair_bot.log")
    print("="*60)

if __name__ == "__main__":
    main()

