"""
Betfair Certificate-based Authentication Module
Implements Non-Interactive (bot) login for Italian Exchange
"""
import requests
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger("BetfairBot")


class BetfairAuthenticator:
    """Handles Betfair certificate-based authentication"""
    
    def __init__(self, app_key: str, username: str, password: str, 
                 cert_path: str, key_path: str, login_endpoint: str):
        """
        Initialize authenticator
        
        Args:
            app_key: Betfair Application Key
            username: Betfair username
            password: Betfair password
            cert_path: Path to certificate file (.crt)
            key_path: Path to private key file (.key)
            login_endpoint: Betfair login endpoint URL
        """
        self.app_key = app_key
        self.username = username
        self.password = password
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.login_endpoint = login_endpoint
        self.session_token: Optional[str] = None
        
        # Validate certificate files exist
        if not self.cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")
        if not self.key_path.exists():
            raise FileNotFoundError(f"Key file not found: {key_path}")
    
    def login(self) -> Tuple[bool, Optional[str]]:
        """
        Perform certificate-based login to Betfair
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            On success, self.session_token will be set
        """
        # Login details are logged only when needed (errors, success)
        
        try:
            # Prepare headers
            headers = {
                'X-Application': self.app_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Prepare form data (URL encoded)
            data = {
                'username': self.username,
                'password': self.password
            }
            
            # Make POST request with certificate
            response = requests.post(
                self.login_endpoint,
                headers=headers,
                data=data,
                cert=(str(self.cert_path), str(self.key_path)),
                timeout=30
            )
            
            # Parse response
            if response.status_code == 200:
                result = response.json()
                
                if result.get('loginStatus') == 'SUCCESS':
                    self.session_token = result.get('sessionToken')
                    # Mask token in logs for security
                    masked_token = self._mask_token(self.session_token) if self.session_token else None
                    logger.info(f"Login successful! Session token: {masked_token}")
                    return True, None
                else:
                    error_status = result.get('loginStatus', 'UNKNOWN_ERROR')
                    # Don't log "Login failed" here - let main.py handle the logging
                    # Only log the error status for debugging
                    logger.debug(f"Login response status: {error_status}")
                    return False, error_status
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Login request failed: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.SSLError as e:
            error_msg = f"SSL error during login: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error during login: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during login: {str(e)}"
            logger.exception(error_msg)
            return False, error_msg
    
    def get_session_token(self) -> Optional[str]:
        """Get current session token"""
        return self.session_token
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated"""
        return self.session_token is not None
    
    @staticmethod
    def _mask_token(token: str, visible_chars: int = 8) -> str:
        """Mask session token for logging (show first and last few chars)"""
        if not token or len(token) <= visible_chars * 2:
            return "***"
        return f"{token[:visible_chars]}...{token[-visible_chars:]}"

