"""
Detailed Betfair Login Test Script
This script performs comprehensive checks and detailed error reporting for Betfair login issues.
"""
import sys
import os
from pathlib import Path
import traceback
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_check(name: str, status: bool, details: str = ""):
    """Print a check result"""
    status_symbol = "✓" if status else "✗"
    status_text = "PASS" if status else "FAIL"
    print(f"{status_symbol} [{status_text}] {name}")
    if details:
        print(f"    → {details}")

def check_python_version():
    """Check Python version"""
    print_section("1. Python Environment Check")
    version = sys.version_info
    print_check(
        "Python Version",
        version.major >= 3 and version.minor >= 10,
        f"Python {version.major}.{version.minor}.{version.micro}"
    )
    return version.major >= 3 and version.minor >= 10

def check_dependencies():
    """Check required Python packages"""
    print_section("2. Dependencies Check")
    
    # Critical packages - login will fail without these
    critical_packages = {
        "requests": "HTTP library for API calls",
        "certifi": "SSL/TLS certificate bundle",
        "urllib3": "SSL/TLS support",
    }
    
    # Optional packages - login can work without these
    optional_packages = {
        "python-dotenv": "Environment variables (optional)",
    }
    
    critical_ok = True
    for package, description in critical_packages.items():
        try:
            module = __import__(package)
            # Try to get version
            version = "unknown"
            if hasattr(module, '__version__'):
                version = module.__version__
            elif package == "certifi":
                try:
                    import certifi
                    version = certifi.__version__
                except:
                    pass
            print_check(f"{package}", True, f"{description} (version: {version})")
        except ImportError:
            print_check(f"{package}", False, f"MISSING - {description}")
            critical_ok = False
    
    for package, description in optional_packages.items():
        try:
            module = __import__(package)
            version = getattr(module, '__version__', 'unknown')
            print_check(f"{package}", True, f"{description} (version: {version})")
        except ImportError:
            print_check(f"{package}", False, f"MISSING - {description} (optional, continuing...)")
    
    # Also check Python version and SSL version
    print("\n   Python & SSL Information:")
    print(f"   → Python version: {sys.version.split()[0]}")
    try:
        import ssl
        print(f"   → SSL version: {ssl.OPENSSL_VERSION}")
    except:
        print(f"   → SSL version: unknown")
    
    return critical_ok

def check_certificate_files(cert_path: str, key_path: str):
    """Check certificate files in detail"""
    print_section("3. Certificate Files Check")
    
    cert_file = Path(cert_path)
    key_file = Path(key_path)
    
    # Check if files exist
    cert_exists = cert_file.exists()
    key_exists = key_file.exists()
    
    print_check("Certificate file exists", cert_exists, str(cert_path))
    if cert_exists:
        print(f"    → Absolute path: {cert_file.resolve()}")
        print(f"    → File size: {cert_file.stat().st_size} bytes")
        print(f"    → Readable: {os.access(cert_file, os.R_OK)}")
    else:
        print(f"    → Current working directory: {os.getcwd()}")
        print(f"    → Resolved path: {cert_file.resolve()}")
    
    print_check("Key file exists", key_exists, str(key_path))
    if key_exists:
        print(f"    → Absolute path: {key_file.resolve()}")
        print(f"    → File size: {key_file.stat().st_size} bytes")
        print(f"    → Readable: {os.access(key_file, os.R_OK)}")
    else:
        print(f"    → Current working directory: {os.getcwd()}")
        print(f"    → Resolved path: {key_file.resolve()}")
    
    # Try to read certificate content
    if cert_exists:
        try:
            with open(cert_file, 'rb') as f:
                cert_content = f.read(100)  # Read first 100 bytes
                if cert_content.startswith(b'-----BEGIN CERTIFICATE-----'):
                    print_check("Certificate format", True, "Valid PEM format")
                else:
                    print_check("Certificate format", False, "Invalid format (should be PEM)")
        except Exception as e:
            print_check("Certificate readable", False, f"Error: {str(e)}")
    
    # Try to read key content
    if key_exists:
        try:
            with open(key_file, 'rb') as f:
                key_content = f.read(100)  # Read first 100 bytes
                if key_content.startswith(b'-----BEGIN'):
                    print_check("Key format", True, "Valid PEM format")
                else:
                    print_check("Key format", False, "Invalid format (should be PEM)")
        except Exception as e:
            print_check("Key readable", False, f"Error: {str(e)}")
    
    return cert_exists and key_exists

def check_config():
    """Load and check configuration"""
    print_section("4. Configuration Check")
    
    try:
        from config.loader import load_config
        
        config = load_config()
        betfair_config = config.get("betfair", {})
        
        app_key = betfair_config.get("app_key", "")
        username = betfair_config.get("username", "")
        password = betfair_config.get("password", "")
        cert_path = betfair_config.get("certificate_path", "")
        key_path = betfair_config.get("key_path", "")
        login_endpoint = betfair_config.get("login_endpoint", "")
        
        print_check("Config file loaded", True, "config/config.json")
        print_check("app_key present", bool(app_key), f"Length: {len(app_key)} chars" if app_key else "MISSING")
        print_check("username present", bool(username), username if username else "MISSING")
        print_check("password present", bool(password), "***" if password else "MISSING")
        print_check("certificate_path present", bool(cert_path), cert_path)
        print_check("key_path present", bool(key_path), key_path)
        print_check("login_endpoint present", bool(login_endpoint), login_endpoint)
        
        return {
            "app_key": app_key,
            "username": username,
            "password": password,
            "cert_path": cert_path,
            "key_path": key_path,
            "login_endpoint": login_endpoint
        }
    except Exception as e:
        print_check("Config file loaded", False, f"Error: {str(e)}")
        traceback.print_exc()
        return None

def test_ssl_connection(login_endpoint: str):
    """Test SSL connection to Betfair"""
    print_section("5. SSL Connection Test")
    
    try:
        import requests
        import ssl
        import socket
        
        # Parse URL
        from urllib.parse import urlparse
        parsed = urlparse(login_endpoint)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        
        print(f"Testing connection to: {hostname}:{port}")
        
        # Test basic TCP connection
        try:
            sock = socket.create_connection((hostname, port), timeout=10)
            sock.close()
            print_check("TCP connection", True, f"Connected to {hostname}:{port}")
        except Exception as e:
            print_check("TCP connection", False, f"Error: {str(e)}")
            return False
        
        # Test HTTPS connection
        try:
            response = requests.get(f"https://{hostname}", timeout=10, verify=True)
            print_check("HTTPS connection", True, f"Status: {response.status_code}")
        except requests.exceptions.SSLError as e:
            print_check("HTTPS connection", False, f"SSL Error: {str(e)}")
            return False
        except Exception as e:
            print_check("HTTPS connection", False, f"Error: {str(e)}")
            return False
        
        return True
    except Exception as e:
        print_check("SSL connection test", False, f"Error: {str(e)}")
        traceback.print_exc()
        return False

def test_login_detailed(config_data: dict):
    """Test login with detailed error reporting"""
    print_section("6. Detailed Login Test")
    
    try:
        from auth.cert_login import BetfairAuthenticator
        
        print(f"Initializing authenticator...")
        print(f"  → app_key: {config_data['app_key'][:8]}... (length: {len(config_data['app_key'])})")
        print(f"  → username: {config_data['username']}")
        print(f"  → cert_path: {config_data.get('cert_path', 'N/A')}")
        print(f"  → key_path: {config_data.get('key_path', 'N/A')}")
        print(f"  → login_endpoint: {config_data.get('login_endpoint', 'N/A')}")
        
        # Try password-based login first (no certificate required)
        print("\n" + "=" * 70)
        print("  Testing Password-Based Login (No Certificate)")
        print("=" * 70)
        
        # Create authenticator without certificate (for password login)
        # Certificate paths are optional for password-based login
        cert_path = config_data.get('cert_path')
        key_path = config_data.get('key_path')
        
        authenticator = BetfairAuthenticator(
            app_key=config_data['app_key'],
            username=config_data['username'],
            password=config_data['password'],
            cert_path=cert_path,  # Optional for password login
            key_path=key_path,     # Optional for password login
            login_endpoint=None    # Will use default cert endpoint, but password login uses different endpoint
        )
        print_check("Authenticator initialized", True, "")
        
        print("\nAttempting password-based login...")
        print(f"  → Endpoint: https://identitysso.betfair.it/api/login")
        success, error = authenticator.login_with_password()
        
        # If password login fails, try certificate-based login
        if not success:
            print("\n" + "=" * 70)
            print("  Password login failed, trying Certificate-Based Login")
            print("=" * 70)
            
            # Check if certificate files exist
            cert_path = Path(config_data.get('cert_path', ''))
            key_path = Path(config_data.get('key_path', ''))
            
            if cert_path.exists() and key_path.exists():
                print("\nAttempting certificate-based login...")
                success, error = authenticator.login()
            else:
                print("⚠ Certificate files not found, skipping certificate login test")
                print(f"  → Certificate path: {cert_path}")
                print(f"  → Key path: {key_path}")
        
        if success:
            print_check("Login successful", True, "")
            session_token = authenticator.get_session_token()
            if session_token:
                masked_token = f"{session_token[:8]}...{session_token[-8:]}" if len(session_token) > 16 else "***"
                print(f"  → Session token: {masked_token}")
            return True
        else:
            print_check("Login failed", False, error or "Unknown error")
            
            # Try to get more details
            print("\nDetailed error information:")
            try:
                import requests
                
                # Try manual request to see full response
                headers = {
                    'X-Application': config_data['app_key'],
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                data = {
                    'username': config_data['username'],
                    'password': config_data['password']
                }
                
                cert_tuple = (config_data['cert_path'], config_data['key_path'])
                
                print(f"  → Making test request...")
                response = requests.post(
                    config_data['login_endpoint'],
                    headers=headers,
                    data=data,
                    cert=cert_tuple,
                    timeout=30,
                    verify=True
                )
                
                print(f"  → HTTP Status: {response.status_code}")
                print(f"  → Response headers: {dict(response.headers)}")
                
                try:
                    result = response.json()
                    print(f"  → Response JSON: {json.dumps(result, indent=2)}")
                    
                    if 'loginStatus' in result:
                        login_status = result['loginStatus']
                        print(f"  → Login Status: {login_status}")
                        
                        if login_status == 'CERT_AUTH_REQUIRED':
                            print("\n  ⚠ CERT_AUTH_REQUIRED Error Details:")
                            print("     This usually means:")
                            print("     1. Certificate file not found or path incorrect")
                            print("     2. Certificate format is invalid")
                            print("     3. Certificate doesn't match the account")
                            print("     4. Account needs to accept terms on website")
                            print("     5. Certificate not uploaded to Betfair account")
                            
                except json.JSONDecodeError:
                    print(f"  → Response text: {response.text[:500]}")
                    
            except Exception as e:
                print(f"  → Error getting detailed info: {str(e)}")
                traceback.print_exc()
            
            return False
            
    except FileNotFoundError as e:
        print_check("Authenticator initialization", False, f"File not found: {str(e)}")
        traceback.print_exc()
        return False
    except Exception as e:
        print_check("Login test", False, f"Unexpected error: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("=" * 70)
    print("  BETFAIR LOGIN DETAILED TEST")
    print("=" * 70)
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script location: {Path(__file__).resolve()}")
    
    # Step 1: Check Python version
    if not check_python_version():
        print("\n❌ Python version check failed. Please use Python 3.10+")
        return 1
    
    # Step 2: Check dependencies
    if not check_dependencies():
        print("\n❌ Some dependencies are missing. Please run: pip install -r requirements.txt")
        return 1
    
    # Step 3: Load configuration
    config_data = check_config()
    if not config_data:
        print("\n❌ Configuration check failed")
        return 1
    
    # Step 4: Check certificate files (optional for password login)
    cert_path = config_data.get('cert_path', '')
    key_path = config_data.get('key_path', '')
    if cert_path and key_path:
        cert_ok = check_certificate_files(cert_path, key_path)
        if not cert_ok:
            print("\n⚠ Certificate files check failed (but password login will be tried first)")
    else:
        print("\n⚠ Certificate paths not configured (password login will be used)")
    
    # Step 5: Test SSL connection (test password login endpoint)
    password_login_endpoint = "https://identitysso.betfair.it/api/login"
    ssl_ok = test_ssl_connection(password_login_endpoint)
    if not ssl_ok:
        print("\n⚠ SSL connection test failed, but continuing with login test...")
    
    # Step 6: Test login
    login_ok = test_login_detailed(config_data)
    
    # Summary
    print_section("SUMMARY")
    if login_ok:
        print("✅ All checks passed! Login successful.")
        return 0
    else:
        print("❌ Login failed. Please review the errors above.")
        print("\nCommon solutions:")
        print("  1. Verify certificate files exist and are readable")
        print("  2. Check certificate paths in config.json (use absolute paths)")
        print("  3. Ensure certificate is uploaded to Betfair account")
        print("  4. Log in to https://www.betfair.it and accept terms")
        print("  5. Verify app_key, username, and password are correct")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

