"""
Test script to check Betfair account balance
This script authenticates and retrieves account funds information
"""
import sys
from pathlib import Path

# Add src to path (go up one level from tests/ to project root, then into src/)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService


def test_account_balance():
    """Test function to check account balance"""
    print("=" * 60)
    print("Betfair Account Balance Test")
    print("=" * 60)
    
    try:
        # Load configuration
        print("\n[1/3] Loading configuration...")
        config = load_config()
        betfair_config = config["betfair"]
        print("✓ Configuration loaded")
        
        # Initialize authenticator
        print("\n[2/3] Authenticating with Betfair...")
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config.get("password") or input("Enter Betfair password: "),
            cert_path=betfair_config["certificate_path"],
            key_path=betfair_config["key_path"],
            login_endpoint=betfair_config["login_endpoint"]
        )
        
        success, error = authenticator.login()
        if not success:
            print(f"✗ Login failed: {error}")
            return 1
        
        session_token = authenticator.get_session_token()
        print("✓ Login successful")
        
        # Get account funds
        print("\n[3/3] Retrieving account balance...")
        market_service = MarketService(
            app_key=betfair_config["app_key"],
            session_token=session_token,
            api_endpoint=betfair_config["api_endpoint"]
        )
        
        account_funds = market_service.get_account_funds()
        
        if account_funds:
            print("\n" + "=" * 60)
            print("ACCOUNT BALANCE INFORMATION")
            print("=" * 60)
            
            # Extract key information
            available_to_bet = account_funds.get("availableToBetBalance", "N/A")
            total_balance = account_funds.get("balance", "N/A")
            exposure = account_funds.get("exposure", "N/A")
            retained_commission = account_funds.get("retainedCommission", "N/A")
            exposure_limit = account_funds.get("exposureLimit", "N/A")
            discount_rate = account_funds.get("discountRate", "N/A")
            points_balance = account_funds.get("pointsBalance", "N/A")
            
            print(f"\n💰 Available to Bet: {available_to_bet} EUR")
            print(f"💵 Total Balance: {total_balance} EUR")
            print(f"📊 Exposure: {exposure} EUR")
            print(f"💼 Retained Commission: {retained_commission} EUR")
            print(f"📈 Exposure Limit: {exposure_limit} EUR")
            print(f"🎯 Discount Rate: {discount_rate}%")
            print(f"⭐ Points Balance: {points_balance}")
            
            # Check if balance is sufficient for betting
            try:
                available_float = float(available_to_bet) if isinstance(available_to_bet, (int, float, str)) else 0.0
                if available_float > 0:
                    print(f"\n✅ Account has sufficient balance for betting")
                    print(f"   Minimum bet stake: 2 EUR (typical)")
                    if available_float >= 2:
                        print(f"   ✅ Balance is sufficient for minimum bet")
                    else:
                        print(f"   ⚠️  Balance is below minimum bet requirement (2 EUR)")
                else:
                    print(f"\n⚠️  Account balance is 0 or negative")
                    print(f"   Please add funds to your Betfair account")
            except (ValueError, TypeError):
                print(f"\n⚠️  Could not parse balance value")
            
            print("\n" + "=" * 60)
            print("Full Account Funds Response:")
            print("=" * 60)
            import json
            print(json.dumps(account_funds, indent=2))
            
            return 0
        else:
            print("✗ Could not retrieve account balance")
            print("  Please check your API key and account permissions")
            return 1
            
    except FileNotFoundError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease ensure:")
        print("  1. config/config.json exists and is properly configured")
        print("  2. Certificate files exist at specified paths")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = test_account_balance()
    sys.exit(exit_code)

