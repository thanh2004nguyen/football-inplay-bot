"""
Test script to check Betfair Italy connectivity
"""
import requests
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.loader import load_config

def test_betfair_connectivity():
    """Test connectivity to Betfair Italy endpoints"""
    print("=" * 60)
    print("Betfair Italy Connectivity Test")
    print("=" * 60)
    
    try:
        config = load_config()
        betfair_config = config["betfair"]
        
        # Test 1: Check if main website is accessible and check for maintenance
        print("\n[Test 1] Checking Betfair Italy website...")
        maintenance_detected = False
        try:
            # Use headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get("https://www.betfair.it", timeout=10, headers=headers)
            
            if response.status_code == 200:
                print("✓ Betfair Italy website is accessible")
                # Check if maintenance message is present
                text_lower = response.text.lower()
                if "manutenzione" in text_lower or "maintenance" in text_lower:
                    maintenance_detected = True
                    print("  ⚠ WARNING: Website shows MAINTENANCE message!")
                    print("  This explains why login is failing with UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT")
                    
                    # Try to extract service status
                    if "exchange" in text_lower and "unavailable" in text_lower:
                        print("  → Exchange service: UNAVAILABLE")
                    if "login" in text_lower and "unavailable" in text_lower:
                        print("  → Login service: UNAVAILABLE")
                    if "sportsbook" in text_lower and "unavailable" in text_lower:
                        print("  → Sportsbook service: UNAVAILABLE")
                    
                    print("  → Solution: Wait for maintenance to complete")
            elif response.status_code == 403:
                print(f"⚠ Betfair Italy website returned status {response.status_code}")
                print("  This may indicate IP geolocation restrictions")
                print("  However, if you can access it in browser, this is normal")
                print("  → Please check manually: https://www.betfair.it")
                print("  → Look for 'Manutenzione in Corso' or 'Maintenance' message")
            else:
                print(f"⚠ Betfair Italy website returned status {response.status_code}")
                print("  → Please check manually: https://www.betfair.it")
        except requests.exceptions.RequestException as e:
            print(f"✗ Cannot access Betfair Italy website: {str(e)}")
            print("  This may indicate network connectivity issues or IP restrictions")
            print("  → Please check manually in browser: https://www.betfair.it")
        
        if not maintenance_detected:
            print("\n  ℹ Note: Could not detect maintenance status automatically")
            print("  → Please check https://www.betfair.it manually in your browser")
            print("  → Look for 'Manutenzione in Corso' (Maintenance) message")
            print("  → Check 'Stato prodotto' (Product Status) section")
        
        # Test 2: Check login endpoint (try actual login to get real error)
        print("\n[Test 2] Checking Betfair Italy login endpoint...")
        login_endpoint = betfair_config["login_endpoint"]
        print(f"   Endpoint: {login_endpoint}")
        
        # First, check if endpoint is reachable
        try:
            response = requests.get(login_endpoint, timeout=10, allow_redirects=False)
            print(f"   GET request status: {response.status_code}")
            if response.status_code in [200, 405, 400]:  # 405 = Method Not Allowed (expected for GET)
                print("✓ Login endpoint is reachable")
            else:
                print(f"⚠ Login endpoint returned unexpected status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"✗ Cannot reach login endpoint: {str(e)}")
        
        # Try actual login to see the real error
        print("\n[Test 2b] Attempting actual login to see error details...")
        print("  (This will help determine if the issue is temporary or permanent)")
        try:
            from auth.cert_login import BetfairAuthenticator
            authenticator = BetfairAuthenticator(
                app_key=betfair_config["app_key"],
                username=betfair_config["username"],
                password=betfair_config["password"],
                cert_path=betfair_config["certificate_path"],
                key_path=betfair_config["key_path"],
                login_endpoint=login_endpoint
            )
            success, error = authenticator.login()
            if success:
                print("✓ Login successful! (This means maintenance is complete)")
                print("  → Bot should work normally now")
            else:
                print(f"✗ Login failed: {error}")
                if "UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT" in str(error):
                    print("\n  → Analysis:")
                    print("     This error typically means:")
                    print("     1. Betfair Italy Exchange is under maintenance (MOST LIKELY)")
                    print("     2. Regulator Italy service is temporarily unavailable")
                    print("     3. Temporary network/connectivity issue")
                    print("\n  → Since it worked yesterday with same IP:")
                    print("     - This is likely a TEMPORARY issue on Betfair's side")
                    print("     - Not an IP location problem (proven by yesterday's success)")
                    print("     - Bot will automatically retry until service is restored")
                    print("\n  → What to do:")
                    print("     1. Check https://www.betfair.it for maintenance status")
                    print("     2. Let the bot run - it will auto-retry every 10 seconds")
                    print("     3. Once Betfair service is restored, login will succeed")
                else:
                    print(f"  → Error type: {error}")
                    print("  → Check configuration and certificate")
        except Exception as e:
            print(f"✗ Error during login test: {str(e)}")
        
        # Test 3: Check API endpoint
        print("\n[Test 3] Checking Betfair API endpoint...")
        api_endpoint = betfair_config["api_endpoint"]
        print(f"   Endpoint: {api_endpoint}")
        try:
            response = requests.get(api_endpoint, timeout=10)
            print(f"   Status: {response.status_code}")
            if response.status_code in [200, 405, 400]:
                print("✓ API endpoint is reachable")
            else:
                print(f"⚠ API endpoint returned status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"✗ Cannot access API endpoint: {str(e)}")
        
        # Test 4: Check certificate files
        print("\n[Test 4] Checking certificate files...")
        cert_path = Path(betfair_config["certificate_path"])
        key_path = Path(betfair_config["key_path"])
        
        if cert_path.exists():
            print(f"✓ Certificate file exists: {cert_path}")
            print(f"   Size: {cert_path.stat().st_size} bytes")
        else:
            print(f"✗ Certificate file not found: {cert_path}")
        
        if key_path.exists():
            print(f"✓ Key file exists: {key_path}")
            print(f"   Size: {key_path.stat().st_size} bytes")
        else:
            print(f"✗ Key file not found: {key_path}")
        
        # Summary
        print("\n" + "=" * 60)
        print("Summary & Recommendations")
        print("=" * 60)
        print("\nIf you're getting UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT:")
        print("\n1. CHECK MAINTENANCE STATUS:")
        print("   - Visit https://www.betfair.it in your browser")
        print("   - Check if 'Manutenzione in Corso' (Maintenance) message appears")
        print("   - Check if Exchange and Login services show as 'Unavailable'")
        print("   - If yes: Wait for maintenance to complete")
        print("\n2. VERIFY CONFIGURATION:")
        print("   - Certificate files exist and are correct")
        print("   - Certificate is uploaded to your Betfair account")
        print("   - Account is registered for Italy Exchange")
        print("\n3. IP LOCATION:")
        print("   - Betfair Italy may require Italy IP address")
        print("   - If outside Italy, you may need VPN")
        print("\n4. BOT BEHAVIOR:")
        print("   - Bot will automatically retry login every 10 seconds")
        print("   - Once maintenance is complete, login should succeed")
        print("   - You can stop the bot with Ctrl+C and restart later")
        print("\nFor more information, visit:")
        print("  - Betfair Italy: https://www.betfair.it")
        print("  - Developer Portal: https://developer.betfair.com/")
        print("  - Check Product Status page for service availability")
        
    except Exception as e:
        print(f"\n✗ Error during test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_betfair_connectivity()

