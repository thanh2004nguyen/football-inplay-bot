"""
Live Score API Client
Handles authentication, rate limiting, and API requests to live-score-api.com
"""
import requests
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("BetfairBot")


class RateLimiter:
    """Rate limiter to enforce API request limits"""
    
    def __init__(self, requests_per_day: int):
        """
        Initialize rate limiter
        
        Args:
            requests_per_day: Maximum requests allowed per day
        """
        self.requests_per_day = requests_per_day
        self.requests_per_hour = requests_per_day / 24
        self.requests_today = 0
        self.requests_this_hour = 0
        self.last_reset_date = datetime.now().date()
        self.last_reset_hour = datetime.now().hour
        self.request_times = []  # Track request timestamps for hourly limit
        
    def _reset_if_needed(self):
        """Reset counters if day or hour has changed"""
        now = datetime.now()
        current_date = now.date()
        current_hour = now.hour
        
        # Reset daily counter if new day
        if current_date != self.last_reset_date:
            self.requests_today = 0
            self.last_reset_date = current_date
            logger.info(f"Rate limiter: Daily counter reset (limit: {self.requests_per_day}/day)")
        
        # Reset hourly counter if new hour
        if current_hour != self.last_reset_hour:
            self.requests_this_hour = 0
            self.last_reset_hour = current_hour
            # Remove old timestamps (older than 1 hour)
            cutoff = now - timedelta(hours=1)
            self.request_times = [t for t in self.request_times if t > cutoff]
            logger.debug(f"Rate limiter: Hourly counter reset (limit: {self.requests_per_hour:.1f}/hour)")
    
    def can_make_request(self) -> bool:
        """
        Check if a request can be made without exceeding limits
        
        Returns:
            True if request can be made, False otherwise
        """
        self._reset_if_needed()
        
        # Check daily limit
        if self.requests_today >= self.requests_per_day:
            logger.warning(f"Rate limit exceeded: {self.requests_today}/{self.requests_per_day} requests today")
            return False
        
        # Check hourly limit (approximate)
        if self.requests_this_hour >= self.requests_per_hour:
            logger.warning(f"Rate limit exceeded: {self.requests_this_hour:.1f}/{self.requests_per_hour:.1f} requests this hour")
            return False
        
        return True
    
    def record_request(self):
        """Record that a request was made"""
        self._reset_if_needed()
        self.requests_today += 1
        self.requests_this_hour += 1
        self.request_times.append(datetime.now())
        logger.debug(f"Rate limiter: {self.requests_today}/{self.requests_per_day} requests today, {self.requests_this_hour:.1f}/{self.requests_per_hour:.1f} this hour")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status"""
        self._reset_if_needed()
        return {
            "requests_today": self.requests_today,
            "requests_per_day": self.requests_per_day,
            "remaining_today": self.requests_per_day - self.requests_today,
            "requests_this_hour": self.requests_this_hour,
            "requests_per_hour": self.requests_per_hour,
            "remaining_this_hour": max(0, self.requests_per_hour - self.requests_this_hour)
        }


class LiveScoreClient:
    """Client for live-score-api.com"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://livescore-api.com/api-client", 
                 rate_limit_per_day: int = 1500):
        """
        Initialize Live Score API client
        
        Args:
            api_key: API key for authentication
            api_secret: API secret for authentication
            base_url: Base URL for API (default: https://livescore-api.com/api-client)
            rate_limit_per_day: Maximum requests per day (default: 1500 for trial)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')
        self.rate_limiter = RateLimiter(rate_limit_per_day)
        
        # Setup session for connection pooling
        # Note: This API uses query parameters for authentication, not headers
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
        
        logger.info(f"Live Score API client initialized (rate limit: {rate_limit_per_day}/day)")
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make API request with rate limiting and error handling
        
        Args:
            endpoint: API endpoint (e.g., "/livescores")
            params: Optional query parameters
        
        Returns:
            Response JSON as dictionary, or None if error
        """
        # Check rate limit
        if not self.rate_limiter.can_make_request():
            logger.error("Rate limit exceeded, cannot make request")
            return None
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            logger.debug(f"Making request to: {url}")
            response = self.session.get(url, params=params, timeout=30)
            
            # Log response status and headers for debugging
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            # Check if response is empty
            if not response.text or not response.text.strip():
                logger.error(f"Empty response from Live Score API: {url}")
                return None
            
            # Log first 200 chars of response for debugging
            logger.debug(f"Response preview: {response.text[:200]}")
            
            response.raise_for_status()
            
            # Try to parse JSON
            try:
                result = response.json()
                # Record successful request
                self.rate_limiter.record_request()
                return result
            except ValueError as json_error:
                # Response is not valid JSON
                logger.error(f"Invalid JSON response from Live Score API: {str(json_error)}")
                logger.error(f"Response text (first 500 chars): {response.text[:500]}")
                return None
            
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text[:500] if e.response.text else "No response text"
            logger.error(f"HTTP error in Live Score API request: {e.response.status_code}")
            logger.error(f"Error response: {error_text}")
            logger.error(f"Request URL: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error in Live Score API request: {str(e)}")
            logger.error(f"Request URL: {url}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Live Score API request: {str(e)}", exc_info=True)
            return None
    
    def get_live_matches(self) -> List[Dict[str, Any]]:
        """
        Get list of currently live matches (filtered to only include actually live matches)
        
        Returns:
            List of match dictionaries (only matches that are actually live)
        """
        logger.debug("Fetching live matches from Live Score API")
        
        # According to documentation: https://livescore-api.com/api-client/matches/live.json?key=...&secret=...
        params = {
            "key": self.api_key,
            "secret": self.api_secret
        }
        result = self._make_request("/matches/live.json", params=params)
        
        if result and isinstance(result, dict):
            # API response structure from documentation:
            # {"success": true, "data": {"match": [...]}}
            if result.get("success") and "data" in result:
                matches = result["data"].get("match", [])
                
                if not isinstance(matches, list):
                    return []
                
                # Filter out matches that are not actually live
                from football_api.parser import parse_match_minute
                live_matches = []
                
                for match in matches:
                    # Check status
                    status = str(match.get("status", "")).upper()
                    
                    # Skip matches that are not started, scheduled, or postponed
                    if "NOT STARTED" in status or "SCHEDULED" in status or "POSTPONED" in status:
                        logger.debug(f"Skipping match (not started): {match.get('home', {}).get('name', 'N/A')} v {match.get('away', {}).get('name', 'N/A')} - Status: {status}")
                        continue
                    
                    # Check minute - if -1, match is not live
                    minute = parse_match_minute(match)
                    if minute < 0:
                        logger.debug(f"Skipping match (not live): {match.get('home', {}).get('name', 'N/A')} v {match.get('away', {}).get('name', 'N/A')} - Minute: {minute}")
                        continue
                    
                    # Match is live
                    live_matches.append(match)
                
                logger.debug(f"Retrieved {len(matches)} match(es) from API, filtered to {len(live_matches)} live match(es)")
                return live_matches
            else:
                logger.warning(f"API response indicates failure or unexpected structure: {result}")
                return []
        
        return []
    
    def get_match_details(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific match
        
        Args:
            match_id: Match ID from Live Score API
        
        Returns:
            Match details dictionary, or None if error
        """
        logger.debug(f"Fetching match details for match ID: {match_id}")
        
        # According to documentation, use events endpoint or match stats endpoint
        # For now, we'll get events which contains goals timeline
        params = {
            "key": self.api_key,
            "secret": self.api_secret,
            "id": match_id
        }
        result = self._make_request("/scores/events.json", params=params)
        
        if result and isinstance(result, dict):
            # API response structure: {"success": true, "data": {...}}
            if result.get("success") and "data" in result:
                match_data = result["data"]
                logger.debug(f"Retrieved match details for match ID: {match_id}")
                return match_data
        
        return None
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        return self.rate_limiter.get_status()

