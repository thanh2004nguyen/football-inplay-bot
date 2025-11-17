"""
Betfair Session Keep-Alive Module
Maintains active session by sending keep-alive requests
"""
import requests
import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger("BetfairBot")


class KeepAliveManager:
    """Manages Betfair session keep-alive"""
    
    def __init__(self, app_key: str, session_token: str, 
                 keep_alive_interval: int = 300,
                 on_session_expired: Optional[Callable[[], None]] = None):
        """
        Initialize keep-alive manager
        
        Args:
            app_key: Betfair Application Key
            session_token: Current session token
            keep_alive_interval: Interval in seconds between keep-alive calls
            on_session_expired: Optional callback function when session expires (will be called with no args)
        """
        self.app_key = app_key
        self.session_token = session_token
        self.keep_alive_interval = keep_alive_interval
        # Use Italy endpoint for keep-alive
        self.keep_alive_endpoint = "https://identitysso.betfair.it/api/keepAlive"
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_keep_alive_time: Optional[float] = None
        self.on_session_expired = on_session_expired
        self._session_expired_detected = False
    
    def start(self):
        """Start keep-alive thread"""
        if self.running:
            logger.warning("Keep-alive already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self.thread.start()
        # Logging moved to main.py setup checklist
    
    def stop(self):
        """Stop keep-alive thread"""
        self.running = False
        if self.thread:
            try:
                self.thread.join(timeout=5)
            except KeyboardInterrupt:
                # Ignore KeyboardInterrupt during thread join
                pass
        logger.info("Keep-alive stopped")
    
    def update_session_token(self, new_token: str):
        """Update session token (e.g., after re-login)"""
        self.session_token = new_token
        logger.debug("Session token updated in keep-alive manager")
    
    def _keep_alive_loop(self):
        """Main keep-alive loop"""
        while self.running:
            try:
                success = self._send_keep_alive()
                if success:
                    self.last_keep_alive_time = time.time()
                else:
                    logger.warning("Keep-alive request failed")
                
                # Sleep until next interval
                time.sleep(self.keep_alive_interval)
                
            except Exception as e:
                logger.error(f"Error in keep-alive loop: {str(e)}")
                time.sleep(self.keep_alive_interval)
    
    def _send_keep_alive(self) -> bool:
        """
        Send keep-alive request to Betfair
        
        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {
                'X-Application': self.app_key,
                'X-Authentication': self.session_token,
                'Accept': 'application/json'
            }
            
            response = requests.post(
                self.keep_alive_endpoint,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'SUCCESS':
                    logger.debug("Keep-alive successful")
                    self._session_expired_detected = False  # Reset flag on success
                    return True
                else:
                    logger.warning(f"Keep-alive returned status: {result.get('status')}")
                    return False
            elif response.status_code == 401:
                # Session expired detected by keep-alive
                logger.warning("Session expired detected by keep-alive (401)")
                self._session_expired_detected = True
                if self.on_session_expired:
                    try:
                        self.on_session_expired()
                    except Exception as callback_error:
                        logger.error(f"Error in session expired callback: {str(callback_error)}")
                return False
            else:
                logger.warning(f"Keep-alive HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Keep-alive request error: {str(e)}")
            return False
    
    def get_last_keep_alive_time(self) -> Optional[float]:
        """Get timestamp of last successful keep-alive"""
        return self.last_keep_alive_time
    
    def is_session_expired(self) -> bool:
        """Check if session expired was detected by keep-alive"""
        return self._session_expired_detected

