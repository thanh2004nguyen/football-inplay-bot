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
                 cert_path: str = None, key_path: str = None, login_endpoint: str = None):
        """
        Initialize authenticator
        
        Args:
            app_key: Betfair Application Key
            username: Betfair username
            password: Betfair password
            cert_path: Path to certificate file (.crt) - optional for password login
            key_path: Path to private key file (.key) - optional for password login
            login_endpoint: Betfair login endpoint URL - optional (defaults to cert endpoint)
        """
        self.app_key = app_key
        self.username = username
        self.password = password
        self.cert_path = Path(cert_path) if cert_path else None
        self.key_path = Path(key_path) if key_path else None
        self.login_endpoint = login_endpoint or "https://identitysso-cert.betfair.it/api/certlogin"
        self.session_token: Optional[str] = None
        
        # Validate certificate files exist (only if provided - optional for password login)
        if self.cert_path and not self.cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")
        if self.key_path and not self.key_path.exists():
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
            
            # Prepare form data (URL encode username and password as per Betfair documentation)
            # According to Betfair docs: "You should ensure that your username and password 
            # values are encoded before being sent to the API; if your password contains 
            # special characters and isn't encoded, the login request will fail with 
            # CERT_AUTH_REQUIRED/INVALID_PASSWORD"
            # 
            # Note: We encode manually using urlencode to ensure proper encoding,
            # then pass as string to avoid double encoding by requests library
            form_data = urllib.parse.urlencode({
                'username': self.username,
                'password': self.password
            })
            
            # Make POST request with certificate
            # Pass encoded data as string to avoid double encoding
            if not self.cert_path or not self.key_path:
                raise ValueError("Certificate files required for certificate-based login")
            
            response = requests.post(
                self.login_endpoint,
                headers=headers,
                data=form_data,
                cert=(str(self.cert_path), str(self.key_path)),
                timeout=30
            )
            
            # Parse response
            if response.status_code == 200:
                try:
                    result = response.json()
                except ValueError:
                    # Response is not valid JSON
                    error_msg = f"Invalid JSON response: {response.text[:200]}"
                    logger.error(error_msg)
                    return False, error_msg
                
                if result.get('loginStatus') == 'SUCCESS':
                    self.session_token = result.get('sessionToken')
                    # Mask token in logs for security
                    masked_token = self._mask_token(self.session_token) if self.session_token else None
                    logger.info(f"Certificate login successful! Session token: {masked_token}")
                    print(f"✓ Certificate login successful! Session token: {masked_token}")
                    return True, None
                else:
                    error_status = result.get('loginStatus', 'UNKNOWN_ERROR')
                    # Log full response for debugging (but don't log password/credentials)
                    logger.error(f"Login failed with status: {error_status}")
                    logger.debug(f"Full login response: {result}")
                    
                    # Include additional error details if available
                    error_message = result.get('error', '')
                    if error_message:
                        error_status = f"{error_status}: {error_message}"
                    
                    return False, error_status
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
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
    
    def login_with_password(self, login_endpoint: str = None) -> Tuple[bool, Optional[str]]:
        """
        Perform username/password login to Betfair (without certificates)
        
        Args:
            login_endpoint: Betfair login endpoint URL (default: Italy endpoint)
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            On success, self.session_token will be set
        """
        # Use Italy endpoint by default
        if not login_endpoint:
            login_endpoint = "https://identitysso.betfair.it/api/login"
        
        try:
            # Prepare headers
            headers = {
                'X-Application': self.app_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            # Prepare form data (URL encode username and password)
            form_data = urllib.parse.urlencode({
                'username': self.username,
                'password': self.password
            })
            
            # Make POST request (no certificate needed)
            response = requests.post(
                login_endpoint,
                headers=headers,
                data=form_data,
                timeout=30,
                allow_redirects=False
            )
            
            # Parse response
            # According to Betfair Interactive Login API documentation:
            # Response structure: {"token":"SESSION_TOKEN", "product":"APP_KEY", "status":"SUCCESS", "error":""}
            if response.status_code == 200:
                try:
                    result = response.json()
                except ValueError:
                    error_msg = f"Invalid JSON response: {response.text[:200]}"
                    logger.error(error_msg)
                    return False, error_msg
                
                # Use 'status' field (not 'loginStatus') as per official documentation
                status = result.get('status', 'UNKNOWN')
                
                if status == 'SUCCESS':
                    # Use 'token' field (not 'sessionToken') as per official documentation
                    self.session_token = result.get('token')
                    masked_token = self._mask_token(self.session_token) if self.session_token else None
                    # Logging moved to main.py setup checklist
                    return True, None
                elif status == 'LIMITED_ACCESS':
                    # Access is limited but session token is provided
                    self.session_token = result.get('token')
                    error_message = result.get('error', '')
                    logger.warning(f"Login successful but with LIMITED_ACCESS: {error_message}")
                    masked_token = self._mask_token(self.session_token) if self.session_token else None
                    logger.info(f"Session token obtained: {masked_token}")
                    return True, None
                else:
                    # Handle various login error statuses
                    error_status = status
                    error_message = result.get('error', '')
                    
                    # Log specific error types based on official documentation
                    if status == 'LOGIN_RESTRICTED':
                        logger.error("Login restricted - account may be suspended or restricted")
                    elif error_message == 'ACCOUNT_PENDING_PASSWORD_CHANGE':
                        logger.error("Account pending password change - please change password on website")
                    elif error_message == 'INVALID_USERNAME_OR_PASSWORD':
                        logger.error("Invalid username or password")
                    elif error_message == 'CERT_AUTH_REQUIRED':
                        logger.error("Certificate authentication required (unexpected for password login)")
                    elif error_message == 'ITALIAN_CONTRACT_ACCEPTANCE_REQUIRED':
                        logger.error("Italian contract acceptance required - please login to website to accept")
                    elif error_message == 'CHANGE_PASSWORD_REQUIRED':
                        logger.error("Password change required - please change password on website")
                    else:
                        logger.error(f"Login failed with status: {error_status}, error: {error_message}")
                    
                    logger.debug(f"Full login response: {result}")
                    
                    if error_message:
                        error_status = f"{error_status}: {error_message}"
                    
                    return False, error_status
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:500]}"
                logger.error(f"Login request failed: {error_msg}")
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

