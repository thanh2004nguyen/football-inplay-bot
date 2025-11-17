"""
Session management utilities
"""
import logging

logger = logging.getLogger("BetfairBot")


def create_session_expired_handler(use_password_login: bool, authenticator, market_service, 
                                   keep_alive_manager, betting_service=None):
    """
    Create a callback function for handling session expiry
    
    Args:
        use_password_login: Whether to use password-based login
        authenticator: BetfairAuthenticator instance
        market_service: MarketService instance
        keep_alive_manager: KeepAliveManager instance
        betting_service: Optional BettingService instance
    
    Returns:
        Callback function for session expiry
    """
    def handle_session_expired():
        """Callback when keep-alive detects session expiry"""
        # Note: We do NOT send email notifications here to avoid spam.
        # Email notifications are only sent during initial login (first attempt).
        # Re-login failures are logged but do not trigger email alerts.
        logger.warning("Session expiry detected by keep-alive, attempting re-login...")
        try:
            # Use password login or certificate login based on config
            if use_password_login:
                success, error = authenticator.login_with_password()
            else:
                success, error = authenticator.login()
            if success:
                new_token = authenticator.get_session_token()
                market_service.update_session_token(new_token)
                keep_alive_manager.update_session_token(new_token)
                # Update betting service if it exists (Milestone 3)
                if betting_service:
                    betting_service.update_session_token(new_token)
                logger.info("Re-login successful after keep-alive detected expiry")
            else:
                logger.warning(f"Re-login failed after keep-alive expiry: {error}")
        except Exception as e:
            logger.error(f"Error during re-login from keep-alive callback: {str(e)}")
    
    return handle_session_expired

