"""
Authentication utilities for login and session management
"""
import time
import logging
from typing import Tuple, Optional, Any

logger = logging.getLogger("BetfairBot")


def perform_login_with_retry(config: dict, authenticator: Any, email_notifier: Optional[Any] = None) -> Tuple[Optional[str], dict]:
    """
    Perform login with retry logic and error handling
    
    Args:
        config: Bot configuration
        authenticator: BetfairAuthenticator instance
        email_notifier: Optional EmailNotifier for sending alerts
    
    Returns:
        Tuple of (session_token, email_flags)
        email_flags: dict with keys 'email_sent_for_maintenance', 'email_sent_for_terms'
    """
    betfair_config = config["betfair"]
    use_password_login = betfair_config.get("use_password_login", False)
    retry_delay = config.get("session", {}).get("retry_delay_seconds", 10)
    max_login_attempts = 999999  # Infinite retry
    login_attempt = 0
    session_token = None
    
    # Email flags: Track if email already sent to avoid sending multiple times
    # These flags persist for the entire bot session (even if re-login happens later)
    email_flags = {
        'email_sent_for_maintenance': False,
        'email_sent_for_terms': False
    }
    
    while login_attempt < max_login_attempts:
        try:
            login_attempt += 1
            
            # Use password login or certificate login based on config
            if use_password_login:
                success, error = authenticator.login_with_password()
            else:
                success, error = authenticator.login()
            
            if success:
                session_token = authenticator.get_session_token()
                break
            else:
                # Check if it's a maintenance/regulator error
                is_maintenance_error = "UNAVAILABLE_CONNECTIVITY_TO_REGULATOR_IT" in str(error)
                
                # Check if it's a connectivity/regulator error (should retry)
                is_retryable_error = is_maintenance_error or any(keyword in str(error) for keyword in [
                    "UNAVAILABLE_CONNECTIVITY",
                    "CONNECTION",
                    "TIMEOUT",
                    "NETWORK"
                ])
                
                # Only show retry message on first attempt and every 10 attempts (1, 11, 21, 31...)
                should_show_retry = (login_attempt == 1) or (login_attempt % 10 == 1)
                
                if is_maintenance_error:
                    # Maintenance error - show maintenance message only once
                    if login_attempt == 1:
                        print(f"⚠ Betfair Italy Exchange is under maintenance. Check status: https://www.betfair.it")
                        logger.warning(f"Betfair maintenance detected: {error}")
                        logger.info("Check service status at: https://www.betfair.it")
                        
                        # Send email notification for maintenance (only once per bot session)
                        # Check both conditions: first attempt AND email not sent yet
                        if login_attempt == 1 and email_notifier and not email_flags['email_sent_for_maintenance']:
                            try:
                                email_notifier.send_betfair_maintenance_alert(str(error))
                                email_flags['email_sent_for_maintenance'] = True  # Set flag to prevent sending again
                                logger.info("Email alert sent for Betfair maintenance (will not send again this session)")
                            except Exception as e:
                                logger.error(f"Failed to send maintenance email: {str(e)}")
                    
                    # Only show retry message on first attempt and every 10 attempts
                    if should_show_retry:
                        print(f"   Retrying in {retry_delay} seconds... (attempt {login_attempt})")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during login retry")
                        print("\n\nStopping...")
                        return None, email_flags
                elif is_retryable_error:
                    # Other retryable errors - only show on first attempt
                    if login_attempt == 1:
                        print(f"⚠ Login failed: {error}")
                    
                    # Only show retry message on first attempt and every 10 attempts
                    if should_show_retry:
                        print(f"   Retrying in {retry_delay} seconds... (attempt {login_attempt})")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during login retry")
                        print("\n\nStopping...")
                        return None, email_flags
                else:
                    # Non-retryable error (e.g., invalid credentials, contract acceptance)
                    # Check if it's a terms/conditions error
                    error_str = str(error).upper()
                    is_terms_error = any(keyword in error_str for keyword in [
                        "TERMS", "CONDITIONS", "ACCEPT", "CONFIRMATION", "CONTRACT",
                        "AGREEMENT", "ACCEPTANCE", "REQUIRED"
                    ])
                    
                    # Only log to file for retry attempts, print to console only on first attempt
                    if login_attempt == 1:
                        logger.error(f"Login failed: {error}")
                        print(f"✗ Login failed: {error}")
                        print(f"\nPlease check: https://www.betfair.it/ app_key, Username, password.")
                        
                        # Send email notification for terms/conditions (only once per bot session)
                        # Check both conditions: first attempt AND email not sent yet AND is terms error
                        if login_attempt == 1 and is_terms_error and email_notifier and not email_flags['email_sent_for_terms']:
                            try:
                                email_notifier.send_betfair_terms_confirmation_alert(str(error))
                                email_flags['email_sent_for_terms'] = True  # Set flag to prevent sending again
                                logger.info("Email alert sent for Betfair terms confirmation (will not send again this session)")
                            except Exception as e:
                                logger.error(f"Failed to send terms confirmation email: {str(e)}")
                    # For subsequent attempts, already logged above with logger.debug()
                    
                    # Only show retry message on first attempt and every 10 attempts
                    if should_show_retry:
                        print(f"\nRetrying in {retry_delay} seconds... (attempt {login_attempt}) (Press Ctrl+C to stop)")
                    
                    try:
                        time.sleep(retry_delay)
                    except KeyboardInterrupt:
                        logger.info("Interrupted by user during login retry")
                        print("\n\nStopping...")
                        return None, email_flags
        except KeyboardInterrupt:
            # Handle Ctrl+C even when it happens during HTTP request
            logger.info("Interrupted by user during login attempt")
            print("\n\nStopping...")
            return None, email_flags
    
    return session_token, email_flags

