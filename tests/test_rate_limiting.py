"""
Test Rate Limiting for Betfair and Live API
This script tests rate limiting behavior for both Betfair Stream API and Live Score API.

Test 1: Betfair 1s interval for 2 minutes 10 seconds (130 seconds)
Test 2: Betfair and Live API 10s interval
"""
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from services.util import perform_login_with_retry
from services.betfair import get_live_markets_from_stream_api
from services.live import LiveScoreClient
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RateLimitTest")


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(name: str, status: bool, details: str = ""):
    """Print a test result"""
    status_symbol = "✓" if status else "✗"
    status_text = "PASS" if status else "FAIL"
    print(f"{status_symbol} [{status_text}] {name}")
    if details:
        print(f"    → {details}")


def test_betfair_rate_limit_1s():
    """
    Test Betfair API rate limiting: 1 second interval for 2 minutes 10 seconds (130 seconds)
    This will make approximately 130 requests to Betfair Stream API
    """
    print_section("Test 1: Betfair Rate Limit Test (1s interval for 2m10s)")
    
    try:
        # Load configuration
        config = load_config()
        betfair_config = config["betfair"]
        
        # Initialize authenticator
        use_password_login = betfair_config.get("use_password_login", False)
        cert_path = betfair_config.get("certificate_path") if not use_password_login else None
        key_path = betfair_config.get("key_path") if not use_password_login else None
        
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config["password"],
            cert_path=cert_path,
            key_path=key_path,
            login_endpoint=betfair_config.get("login_endpoint")
        )
        
        # Perform login
        print("Logging in to Betfair...")
        session_token, _ = perform_login_with_retry(config, authenticator, None)
        
        if not session_token:
            print_result("Login", False, "Failed to obtain session token")
            return False
        
        print_result("Login", True, "Session token obtained")
        
        # Test parameters
        test_duration = 130  # 2 minutes 10 seconds
        interval = 1  # 1 second between requests
        expected_requests = test_duration // interval  # Approximately 130 requests
        
        print(f"\nTest Parameters:")
        print(f"  Duration: {test_duration} seconds (2 minutes 10 seconds)")
        print(f"  Interval: {interval} second(s)")
        print(f"  Expected requests: ~{expected_requests}")
        print(f"\nStarting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        # Statistics
        successful_requests = 0
        failed_requests = 0
        rate_limit_errors = 0
        other_errors = 0
        error_details = []
        
        start_time = time.time()
        request_count = 0
        
        try:
            while time.time() - start_time < test_duration:
                request_count += 1
                request_start = time.time()
                
                try:
                    # Make request to Betfair Stream API
                    markets = get_live_markets_from_stream_api(
                        app_key=betfair_config["app_key"],
                        session_token=session_token,
                        api_endpoint=betfair_config["api_endpoint"],
                        market_type_codes=["OVER_UNDER_05", "OVER_UNDER_15", "OVER_UNDER_25", "OVER_UNDER_35", "OVER_UNDER_45"],
                        collect_duration=1.0  # Short collection duration for faster requests
                    )
                    
                    if markets is not None:
                        successful_requests += 1
                        elapsed = time.time() - request_start
                        print(f"  Request #{request_count}: SUCCESS ({len(markets)} markets, {elapsed:.2f}s)")
                    else:
                        failed_requests += 1
                        elapsed = time.time() - request_start
                        print(f"  Request #{request_count}: FAILED (None returned, {elapsed:.2f}s)")
                        error_details.append(f"Request #{request_count}: None returned")
                
                except Exception as e:
                    error_str = str(e)
                    failed_requests += 1
                    elapsed = time.time() - request_start
                    
                    # Check if it's a rate limit error
                    if any(keyword in error_str.upper() for keyword in [
                        "RATE LIMIT", "RATE_LIMIT", "429", "TOO MANY REQUESTS",
                        "REQUEST LIMIT", "THROTTLE", "QUOTA"
                    ]):
                        rate_limit_errors += 1
                        print(f"  Request #{request_count}: RATE LIMIT ERROR ({elapsed:.2f}s)")
                        error_details.append(f"Request #{request_count}: Rate limit error - {error_str[:100]}")
                    else:
                        other_errors += 1
                        print(f"  Request #{request_count}: ERROR ({elapsed:.2f}s) - {error_str[:100]}")
                        error_details.append(f"Request #{request_count}: {error_str[:100]}")
                
                # Wait for next interval
                elapsed_total = time.time() - start_time
                if elapsed_total < test_duration:
                    sleep_time = interval - (time.time() - request_start)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        
        # Calculate statistics
        total_time = time.time() - start_time
        total_requests = successful_requests + failed_requests
        
        print(f"\n{'='*70}")
        print("Test Results:")
        print(f"{'='*70}")
        print(f"  Total time: {total_time:.2f} seconds")
        print(f"  Total requests: {total_requests}")
        print(f"  Successful: {successful_requests} ({successful_requests/total_requests*100:.1f}%)" if total_requests > 0 else "  Successful: 0")
        print(f"  Failed: {failed_requests} ({failed_requests/total_requests*100:.1f}%)" if total_requests > 0 else "  Failed: 0")
        print(f"  Rate limit errors: {rate_limit_errors}")
        print(f"  Other errors: {other_errors}")
        
        if error_details:
            print(f"\n  Error Details (first 5):")
            for detail in error_details[:5]:
                print(f"    - {detail}")
        
        # Determine test result
        test_passed = rate_limit_errors == 0 and (successful_requests / total_requests >= 0.9 if total_requests > 0 else False)
        
        if test_passed:
            print_result("Rate Limit Test", True, f"No rate limit errors detected. {successful_requests}/{total_requests} requests successful.")
        else:
            if rate_limit_errors > 0:
                print_result("Rate Limit Test", False, f"Rate limit errors detected: {rate_limit_errors} errors")
            else:
                print_result("Rate Limit Test", False, f"Low success rate: {successful_requests}/{total_requests} requests successful")
        
        return test_passed
    
    except Exception as e:
        print_result("Rate Limit Test", False, f"Test failed with exception: {str(e)}")
        traceback.print_exc()
        return False


def test_betfair_live_api_10s():
    """
    Test both Betfair and Live API with 10 second interval
    This simulates the polling behavior when matches are in 60-74 minute range with QUALIFIED status
    """
    print_section("Test 2: Betfair and Live API 10s Interval Test")
    
    try:
        # Load configuration
        config = load_config()
        betfair_config = config["betfair"]
        live_score_config = config.get("live_score_api", {})
        
        # Initialize Betfair authenticator
        use_password_login = betfair_config.get("use_password_login", False)
        cert_path = betfair_config.get("certificate_path") if not use_password_login else None
        key_path = betfair_config.get("key_path") if not use_password_login else None
        
        authenticator = BetfairAuthenticator(
            app_key=betfair_config["app_key"],
            username=betfair_config["username"],
            password=betfair_config["password"],
            cert_path=cert_path,
            key_path=key_path,
            login_endpoint=betfair_config.get("login_endpoint")
        )
        
        # Perform login
        print("Logging in to Betfair...")
        session_token, _ = perform_login_with_retry(config, authenticator, None)
        
        if not session_token:
            print_result("Betfair Login", False, "Failed to obtain session token")
            return False
        
        print_result("Betfair Login", True, "Session token obtained")
        
        # Initialize Live API client
        live_client = None
        if live_score_config.get("api_key") and live_score_config.get("api_secret"):
            try:
                live_client = LiveScoreClient(
                    api_key=live_score_config["api_key"],
                    api_secret=live_score_config["api_secret"],
                    base_url=live_score_config.get("base_url", "https://livescore-api.com/api-client"),
                    rate_limit_per_day=live_score_config.get("rate_limit_per_day", 1500)
                )
                print_result("Live API Client", True, "Initialized successfully")
            except Exception as e:
                print_result("Live API Client", False, f"Failed to initialize: {str(e)}")
                live_client = None
        else:
            print_result("Live API Client", False, "API key or secret not configured")
        
        # Test parameters
        test_duration = 120  # 2 minutes
        interval = 10  # 10 seconds between requests
        expected_requests = test_duration // interval  # Approximately 12 requests
        
        print(f"\nTest Parameters:")
        print(f"  Duration: {test_duration} seconds (2 minutes)")
        print(f"  Interval: {interval} second(s)")
        print(f"  Expected requests per API: ~{expected_requests}")
        print(f"\nStarting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        # Statistics
        betfair_successful = 0
        betfair_failed = 0
        betfair_rate_limit_errors = 0
        live_successful = 0
        live_failed = 0
        live_rate_limit_errors = 0
        
        start_time = time.time()
        iteration = 0
        
        try:
            while time.time() - start_time < test_duration:
                iteration += 1
                iteration_start = time.time()
                
                print(f"\n--- Iteration #{iteration} ---")
                
                # Test Betfair API
                try:
                    betfair_start = time.time()
                    markets = get_live_markets_from_stream_api(
                        app_key=betfair_config["app_key"],
                        session_token=session_token,
                        api_endpoint=betfair_config["api_endpoint"],
                        market_type_codes=["OVER_UNDER_05", "OVER_UNDER_15", "OVER_UNDER_25", "OVER_UNDER_35", "OVER_UNDER_45"],
                        collect_duration=2.0
                    )
                    betfair_elapsed = time.time() - betfair_start
                    
                    if markets is not None:
                        betfair_successful += 1
                        print(f"  Betfair: SUCCESS ({len(markets)} markets, {betfair_elapsed:.2f}s)")
                    else:
                        betfair_failed += 1
                        print(f"  Betfair: FAILED (None returned, {betfair_elapsed:.2f}s)")
                
                except Exception as e:
                    error_str = str(e)
                    betfair_failed += 1
                    betfair_elapsed = time.time() - betfair_start
                    
                    if any(keyword in error_str.upper() for keyword in [
                        "RATE LIMIT", "RATE_LIMIT", "429", "TOO MANY REQUESTS",
                        "REQUEST LIMIT", "THROTTLE", "QUOTA"
                    ]):
                        betfair_rate_limit_errors += 1
                        print(f"  Betfair: RATE LIMIT ERROR ({betfair_elapsed:.2f}s) - {error_str[:100]}")
                    else:
                        print(f"  Betfair: ERROR ({betfair_elapsed:.2f}s) - {error_str[:100]}")
                
                # Test Live API
                if live_client:
                    try:
                        live_start = time.time()
                        live_matches = live_client.get_live_matches(competition_ids=None)
                        live_elapsed = time.time() - live_start
                        
                        if live_matches is not None:
                            live_successful += 1
                            print(f"  Live API: SUCCESS ({len(live_matches)} matches, {live_elapsed:.2f}s)")
                            
                            # Show rate limit status
                            rate_status = live_client.get_rate_limit_status()
                            if rate_status:
                                remaining = rate_status.get("remaining", "N/A")
                                used = rate_status.get("used", "N/A")
                                print(f"    Rate limit: {used}/{rate_status.get('limit', 'N/A')} used, {remaining} remaining")
                        else:
                            live_failed += 1
                            print(f"  Live API: FAILED (None returned, {live_elapsed:.2f}s)")
                    
                    except Exception as e:
                        error_str = str(e)
                        live_failed += 1
                        live_elapsed = time.time() - live_start
                        
                        if any(keyword in error_str.upper() for keyword in [
                            "RATE LIMIT", "RATE_LIMIT", "429", "TOO MANY REQUESTS",
                            "REQUEST LIMIT", "THROTTLE", "QUOTA"
                        ]):
                            live_rate_limit_errors += 1
                            print(f"  Live API: RATE LIMIT ERROR ({live_elapsed:.2f}s) - {error_str[:100]}")
                        else:
                            print(f"  Live API: ERROR ({live_elapsed:.2f}s) - {error_str[:100]}")
                else:
                    print(f"  Live API: SKIPPED (not configured)")
                
                # Wait for next interval
                elapsed_total = time.time() - start_time
                if elapsed_total < test_duration:
                    sleep_time = interval - (time.time() - iteration_start)
                    if sleep_time > 0:
                        print(f"  Waiting {sleep_time:.2f}s until next iteration...")
                        time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        
        # Calculate statistics
        total_time = time.time() - start_time
        betfair_total = betfair_successful + betfair_failed
        live_total = live_successful + live_failed
        
        print(f"\n{'='*70}")
        print("Test Results:")
        print(f"{'='*70}")
        print(f"  Total time: {total_time:.2f} seconds")
        print(f"  Total iterations: {iteration}")
        print(f"\n  Betfair API:")
        print(f"    Total requests: {betfair_total}")
        print(f"    Successful: {betfair_successful} ({betfair_successful/betfair_total*100:.1f}%)" if betfair_total > 0 else "    Successful: 0")
        print(f"    Failed: {betfair_failed} ({betfair_failed/betfair_total*100:.1f}%)" if betfair_total > 0 else "    Failed: 0")
        print(f"    Rate limit errors: {betfair_rate_limit_errors}")
        
        if live_client:
            print(f"\n  Live API:")
            print(f"    Total requests: {live_total}")
            print(f"    Successful: {live_successful} ({live_successful/live_total*100:.1f}%)" if live_total > 0 else "    Successful: 0")
            print(f"    Failed: {live_failed} ({live_failed/live_total*100:.1f}%)" if live_total > 0 else "    Failed: 0")
            print(f"    Rate limit errors: {live_rate_limit_errors}")
            
            # Show final rate limit status
            rate_status = live_client.get_rate_limit_status()
            if rate_status:
                print(f"    Final rate limit status: {rate_status.get('used', 'N/A')}/{rate_status.get('limit', 'N/A')} used")
        
        # Determine test result
        betfair_passed = betfair_rate_limit_errors == 0 and (betfair_successful / betfair_total >= 0.9 if betfair_total > 0 else False)
        live_passed = live_rate_limit_errors == 0 and (live_successful / live_total >= 0.9 if live_total > 0 else True) if live_client else True
        
        test_passed = betfair_passed and live_passed
        
        print(f"\n  Overall Result:")
        print_result("Betfair API Test", betfair_passed, 
                   f"{betfair_successful}/{betfair_total} successful, {betfair_rate_limit_errors} rate limit errors")
        if live_client:
            print_result("Live API Test", live_passed,
                       f"{live_successful}/{live_total} successful, {live_rate_limit_errors} rate limit errors")
        
        return test_passed
    
    except Exception as e:
        print_result("Combined Test", False, f"Test failed with exception: {str(e)}")
        traceback.print_exc()
        return False


def test_multiple_qualified_matches(num_matches: int = 5):
    """
    Test rate limiting when there are multiple QUALIFIED matches
    This simulates the real scenario where:
    - get_live_matches is called every 10s (when QUALIFIED in 60-74)
    - get_match_details is called for each QUALIFIED match every 15s (perform_matching interval)
    
    Args:
        num_matches: Number of QUALIFIED matches to simulate (default: 5)
    """
    print_section(f"Test 3: Multiple QUALIFIED Matches Test ({num_matches} matches)")
    
    try:
        # Load configuration
        config = load_config()
        live_score_config = config.get("live_score_api", {})
        
        # Initialize Live API client
        live_client = None
        if live_score_config.get("api_key") and live_score_config.get("api_secret"):
            try:
                live_client = LiveScoreClient(
                    api_key=live_score_config["api_key"],
                    api_secret=live_score_config["api_secret"],
                    base_url=live_score_config.get("base_url", "https://livescore-api.com/api-client"),
                    rate_limit_per_day=live_score_config.get("rate_limit_per_day", 1500)
                )
                print_result("Live API Client", True, "Initialized successfully")
            except Exception as e:
                print_result("Live API Client", False, f"Failed to initialize: {str(e)}")
                return False
        else:
            print_result("Live API Client", False, "API key or secret not configured")
            return False
        
        # Get some real match IDs for testing (use first few matches from get_live_matches)
        print("\nGetting sample match IDs from Live API...")
        sample_matches = live_client.get_live_matches(competition_ids=None)
        
        if not sample_matches or len(sample_matches) == 0:
            print_result("Sample Matches", False, "No live matches available for testing")
            return False
        
        # Use first N matches (or all if less than N)
        test_match_ids = [str(m.get("id", "")) for m in sample_matches[:num_matches] if m.get("id")]
        
        if len(test_match_ids) < num_matches:
            print(f"  Warning: Only {len(test_match_ids)} matches available, using {len(test_match_ids)} for test")
            num_matches = len(test_match_ids)
        
        print_result("Sample Matches", True, f"Using {num_matches} match IDs: {', '.join(test_match_ids[:3])}{'...' if len(test_match_ids) > 3 else ''}")
        
        # Test parameters
        test_duration = 120  # 2 minutes
        get_live_matches_interval = 10  # 10 seconds (when QUALIFIED in 60-74)
        perform_matching_interval = 15  # 15 seconds (perform_matching runs every 15s)
        
        expected_get_live_matches = test_duration // get_live_matches_interval  # ~12 requests
        expected_perform_matching = test_duration // perform_matching_interval  # ~8 iterations
        expected_get_match_details = expected_perform_matching * num_matches  # ~40 requests (8 * 5)
        expected_total_live_api = expected_get_live_matches + expected_get_match_details  # ~52 requests
        
        print(f"\nTest Parameters:")
        print(f"  Duration: {test_duration} seconds (2 minutes)")
        print(f"  Number of QUALIFIED matches: {num_matches}")
        print(f"  get_live_matches interval: {get_live_matches_interval}s")
        print(f"  perform_matching interval: {perform_matching_interval}s")
        print(f"  Expected get_live_matches calls: ~{expected_get_live_matches}")
        print(f"  Expected perform_matching iterations: ~{expected_perform_matching}")
        print(f"  Expected get_match_details calls: ~{expected_get_match_details} ({expected_perform_matching} iterations × {num_matches} matches)")
        print(f"  Expected total Live API requests: ~{expected_total_live_api}")
        print(f"\nStarting test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
        
        # Statistics
        get_live_matches_successful = 0
        get_live_matches_failed = 0
        get_match_details_successful = 0
        get_match_details_failed = 0
        rate_limit_errors = 0
        last_get_live_matches_time = 0
        last_perform_matching_time = 0
        
        start_time = time.time()
        iteration = 0
        
        try:
            while time.time() - start_time < test_duration:
                iteration += 1
                current_time = time.time()
                elapsed_total = current_time - start_time
                
                # Call get_live_matches every 10s
                if current_time - last_get_live_matches_time >= get_live_matches_interval:
                    try:
                        get_live_start = time.time()
                        live_matches = live_client.get_live_matches(competition_ids=None)
                        get_live_elapsed = time.time() - get_live_start
                        
                        if live_matches is not None:
                            get_live_matches_successful += 1
                            print(f"\n[{elapsed_total:.1f}s] get_live_matches: SUCCESS ({len(live_matches)} matches, {get_live_elapsed:.2f}s)")
                        else:
                            get_live_matches_failed += 1
                            print(f"\n[{elapsed_total:.1f}s] get_live_matches: FAILED (None returned, {get_live_elapsed:.2f}s)")
                        
                        last_get_live_matches_time = current_time
                    
                    except Exception as e:
                        error_str = str(e)
                        get_live_matches_failed += 1
                        get_live_elapsed = time.time() - get_live_start
                        
                        if any(keyword in error_str.upper() for keyword in [
                            "RATE LIMIT", "RATE_LIMIT", "429", "TOO MANY REQUESTS",
                            "REQUEST LIMIT", "THROTTLE", "QUOTA"
                        ]):
                            rate_limit_errors += 1
                            print(f"\n[{elapsed_total:.1f}s] get_live_matches: RATE LIMIT ERROR ({get_live_elapsed:.2f}s)")
                        else:
                            print(f"\n[{elapsed_total:.1f}s] get_live_matches: ERROR ({get_live_elapsed:.2f}s) - {error_str[:100]}")
                
                # Call get_match_details for each match every 15s (simulate perform_matching)
                if current_time - last_perform_matching_time >= perform_matching_interval:
                    print(f"\n[{elapsed_total:.1f}s] perform_matching: Calling get_match_details for {num_matches} matches...")
                    
                    for i, match_id in enumerate(test_match_ids, 1):
                        try:
                            details_start = time.time()
                            match_details = live_client.get_match_details(match_id)
                            details_elapsed = time.time() - details_start
                            
                            if match_details is not None:
                                get_match_details_successful += 1
                                print(f"  Match {i}/{num_matches} (ID: {match_id}): SUCCESS ({details_elapsed:.2f}s)")
                            else:
                                get_match_details_failed += 1
                                print(f"  Match {i}/{num_matches} (ID: {match_id}): FAILED (None returned, {details_elapsed:.2f}s)")
                        
                        except Exception as e:
                            error_str = str(e)
                            get_match_details_failed += 1
                            details_elapsed = time.time() - details_start
                            
                            if any(keyword in error_str.upper() for keyword in [
                                "RATE LIMIT", "RATE_LIMIT", "429", "TOO MANY REQUESTS",
                                "REQUEST LIMIT", "THROTTLE", "QUOTA"
                            ]):
                                rate_limit_errors += 1
                                print(f"  Match {i}/{num_matches} (ID: {match_id}): RATE LIMIT ERROR ({details_elapsed:.2f}s)")
                            else:
                                print(f"  Match {i}/{num_matches} (ID: {match_id}): ERROR ({details_elapsed:.2f}s) - {error_str[:100]}")
                    
                    last_perform_matching_time = current_time
                
                # Small sleep to avoid busy waiting
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
        
        # Calculate statistics
        total_time = time.time() - start_time
        total_get_live_matches = get_live_matches_successful + get_live_matches_failed
        total_get_match_details = get_match_details_successful + get_match_details_failed
        total_live_api_requests = total_get_live_matches + total_get_match_details
        
        print(f"\n{'='*70}")
        print("Test Results:")
        print(f"{'='*70}")
        print(f"  Total time: {total_time:.2f} seconds")
        print(f"\n  get_live_matches:")
        print(f"    Total requests: {total_get_live_matches}")
        print(f"    Successful: {get_live_matches_successful} ({get_live_matches_successful/total_get_live_matches*100:.1f}%)" if total_get_live_matches > 0 else "    Successful: 0")
        print(f"    Failed: {get_live_matches_failed} ({get_live_matches_failed/total_get_live_matches*100:.1f}%)" if total_get_live_matches > 0 else "    Failed: 0")
        
        print(f"\n  get_match_details ({num_matches} matches per iteration):")
        print(f"    Total requests: {total_get_match_details}")
        print(f"    Successful: {get_match_details_successful} ({get_match_details_successful/total_get_match_details*100:.1f}%)" if total_get_match_details > 0 else "    Successful: 0")
        print(f"    Failed: {get_match_details_failed} ({get_match_details_failed/total_get_match_details*100:.1f}%)" if total_get_match_details > 0 else "    Failed: 0")
        
        print(f"\n  Total Live API requests: {total_live_api_requests}")
        print(f"    Rate limit errors: {rate_limit_errors}")
        
        # Show rate limit status
        rate_status = live_client.get_rate_limit_status()
        if rate_status:
            print(f"    Rate limit status: {rate_status.get('used', 'N/A')}/{rate_status.get('limit', 'N/A')} used")
        
        # Calculate requests per minute
        requests_per_minute = (total_live_api_requests / total_time) * 60 if total_time > 0 else 0
        print(f"    Requests per minute: {requests_per_minute:.1f}")
        
        # Determine test result
        test_passed = rate_limit_errors == 0 and (
            (get_live_matches_successful / total_get_live_matches >= 0.9 if total_get_live_matches > 0 else True) and
            (get_match_details_successful / total_get_match_details >= 0.9 if total_get_match_details > 0 else True)
        )
        
        print(f"\n  Overall Result:")
        if test_passed:
            print_result("Multiple QUALIFIED Matches Test", True, 
                       f"{total_live_api_requests} total requests, {rate_limit_errors} rate limit errors, {requests_per_minute:.1f} req/min")
        else:
            if rate_limit_errors > 0:
                print_result("Multiple QUALIFIED Matches Test", False,
                           f"Rate limit errors detected: {rate_limit_errors} errors")
            else:
                print_result("Multiple QUALIFIED Matches Test", False,
                           f"Low success rate: {get_live_matches_successful}/{total_get_live_matches} get_live_matches, {get_match_details_successful}/{total_get_match_details} get_match_details")
        
        return test_passed
    
    except Exception as e:
        print_result("Multiple QUALIFIED Matches Test", False, f"Test failed with exception: {str(e)}")
        traceback.print_exc()
        return False


def main():
    """Run all rate limiting tests"""
    print_section("Rate Limiting Tests")
    print("This script tests rate limiting behavior for Betfair and Live API")
    print("\nTests:")
    print("  1. Betfair 1s interval for 2 minutes 10 seconds (130 requests)")
    print("  2. Betfair and Live API 10s interval for 2 minutes (12 requests each)")
    print("  3. Multiple QUALIFIED matches (5 matches) - simulates real scenario")
    
    results = []
    
    # Test 1: Betfair 1s interval
    print("\n" + "="*70)
    result1 = test_betfair_rate_limit_1s()
    results.append(("Betfair 1s Interval Test", result1))
    
    # Test 2: Betfair and Live API 10s interval
    print("\n" + "="*70)
    result2 = test_betfair_live_api_10s()
    results.append(("Betfair and Live API 10s Interval Test", result2))
    
    # Test 3: Multiple QUALIFIED matches
    print("\n" + "="*70)
    result3 = test_multiple_qualified_matches(num_matches=5)
    results.append(("Multiple QUALIFIED Matches Test (5 matches)", result3))
    
    # Summary
    print_section("Test Summary")
    for test_name, result in results:
        print_result(test_name, result)
    
    all_passed = all(result for _, result in results)
    print(f"\n{'='*70}")
    if all_passed:
        print("✓ All tests PASSED")
    else:
        print("✗ Some tests FAILED")
    print(f"{'='*70}\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

