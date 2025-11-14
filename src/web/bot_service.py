"""
Bot Service Module
Wraps the main bot logic to run as a service that can be controlled via web interface
"""
import threading
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("BetfairBot")


class BotService:
    """Manages bot lifecycle and exposes status for web interface"""
    
    def __init__(self):
        self.is_running = False
        self.bot_thread: Optional[threading.Thread] = None
        self.status = {
            "state": "stopped",  # stopped, starting, running, stopping, error
            "started_at": None,
            "stopped_at": None,
            "uptime_seconds": 0,
            "error_message": None,
            "matches_tracked": 0,
            "bets_placed": 0,
            "last_update": None
        }
        self._status_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # These will be set when bot starts
        self.match_tracker_manager = None
        self.bet_tracker = None
        
        # Account balance - will be loaded on init
        self.account_balance: Optional[float] = None
        self._load_account_balance()
    
    def start(self) -> Dict[str, Any]:
        """Start the bot in a separate thread"""
        with self._status_lock:
            if self.is_running:
                return {"success": False, "message": "Bot is already running"}
            
            if self.bot_thread and self.bot_thread.is_alive():
                return {"success": False, "message": "Bot thread is still running"}
            
            self.is_running = True
            self.status["state"] = "starting"
            self.status["started_at"] = datetime.now().isoformat()
            self.status["stopped_at"] = None
            self.status["error_message"] = None
            self._stop_event.clear()
        
        # Set stop event in shared state so main() can check it
        from web.shared_state import set_stop_event
        set_stop_event(self._stop_event)
        
        # Start bot in separate thread
        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()
        
        logger.info("Bot service started")
        return {"success": True, "message": "Bot is starting..."}
    
    def stop(self) -> Dict[str, Any]:
        """Stop the bot gracefully"""
        with self._status_lock:
            if not self.is_running:
                return {"success": False, "message": "Bot is not running"}
            
            # Don't allow multiple stop calls
            if self.status["state"] == "stopping":
                return {"success": False, "message": "Bot is already stopping"}
            
            self.status["state"] = "stopping"
            self._stop_event.set()
        
        logger.info("Stop signal sent, waiting for bot thread to finish...")
        
        # Wait for thread to finish (with timeout)
        if self.bot_thread and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=10)
            
            # If thread is still alive after timeout, force stop
            if self.bot_thread.is_alive():
                logger.warning("Bot thread did not stop within timeout, forcing stop")
        
        with self._status_lock:
            self.is_running = False
            self.status["state"] = "stopped"
            self.status["stopped_at"] = datetime.now().isoformat()
            if self.status["started_at"]:
                try:
                    started = datetime.fromisoformat(self.status["started_at"])
                    stopped = datetime.now()
                    self.status["uptime_seconds"] = int((stopped - started).total_seconds())
                except:
                    pass
        
        logger.info("Bot service stopped")
        return {"success": True, "message": "Bot stopped"}
    
    def _run_bot(self):
        """Run the bot main function in this thread"""
        try:
            with self._status_lock:
                self.status["state"] = "running"
            
            # Import and run main function
            try:
                from main import main as bot_main
            except ImportError as e:
                error_msg = f"Failed to import main module: {str(e)}"
                logger.error(error_msg)
                with self._status_lock:
                    self.status["state"] = "error"
                    self.status["error_message"] = error_msg
                    self.is_running = False
                    self.status["stopped_at"] = datetime.now().isoformat()
                return
            
            # Run bot (this will block until bot stops)
            try:
                exit_code = bot_main()
            except KeyboardInterrupt:
                # Bot was stopped gracefully
                logger.info("Bot stopped by user")
                with self._status_lock:
                    self.status["state"] = "stopped"
                    self.is_running = False
                    self.status["stopped_at"] = datetime.now().isoformat()
                return
            except Exception as e:
                error_msg = f"Error in bot main: {str(e)}"
                logger.error(error_msg, exc_info=True)
                with self._status_lock:
                    self.status["state"] = "error"
                    self.status["error_message"] = error_msg
                    self.is_running = False
                    self.status["stopped_at"] = datetime.now().isoformat()
                return
            
            # Bot exited normally
            with self._status_lock:
                if exit_code == 0:
                    self.status["state"] = "stopped"
                else:
                    self.status["state"] = "error"
                    self.status["error_message"] = f"Bot exited with code {exit_code}"
                self.is_running = False
                self.status["stopped_at"] = datetime.now().isoformat()
                
        except Exception as e:
            error_msg = f"Unexpected error in bot thread: {str(e)}"
            logger.error(error_msg, exc_info=True)
            with self._status_lock:
                self.status["state"] = "error"
                self.status["error_message"] = error_msg
                self.is_running = False
                self.status["stopped_at"] = datetime.now().isoformat()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        with self._status_lock:
            status = self.status.copy()
            
            # Calculate uptime if running
            if self.is_running and status["started_at"]:
                try:
                    started = datetime.fromisoformat(status["started_at"])
                    now = datetime.now()
                    status["uptime_seconds"] = int((now - started).total_seconds())
                except:
                    pass
            
            status["is_running"] = self.is_running
            status["last_update"] = datetime.now().isoformat()
            
            return status
    
    def should_stop(self) -> bool:
        """Check if bot should stop (called from bot main loop)"""
        return self._stop_event.is_set()
    
    def update_match_tracker(self, match_tracker_manager):
        """Update match tracker reference (called from bot)"""
        self.match_tracker_manager = match_tracker_manager
    
    def update_bet_tracker(self, bet_tracker):
        """Update bet tracker reference (called from bot)"""
        self.bet_tracker = bet_tracker
    
    def get_matches(self) -> list:
        """Get active matches from match tracker"""
        if self.match_tracker_manager:
            try:
                matches = []
                for tracker in self.match_tracker_manager.trackers.values():
                    matches.append(tracker.get_status())
                return matches
            except:
                pass
        return []
    
    def get_bets(self) -> list:
        """Get bet history from bet tracker"""
        if self.bet_tracker:
            try:
                bets = []
                for bet in self.bet_tracker.bets.values():
                    bets.append(bet.to_dict())
                return bets
            except:
                pass
        return []
    
    def _load_account_balance(self):
        """Load account balance on initialization"""
        try:
            from config.loader import load_config
            from auth.cert_login import BetfairAuthenticator
            from betfair.market_service import MarketService
            
            # Load configuration
            config = load_config()
            betfair_config = config["betfair"]
            
            # Initialize authenticator
            authenticator = BetfairAuthenticator(
                app_key=betfair_config["app_key"],
                username=betfair_config["username"],
                password=betfair_config.get("password") or "",
                cert_path=betfair_config["certificate_path"],
                key_path=betfair_config["key_path"],
                login_endpoint=betfair_config["login_endpoint"]
            )
            
            # Try to login and get balance
            success, error = authenticator.login()
            if not success:
                logger.warning(f"Could not authenticate to get account balance: {error}")
                self.account_balance = None
                return
            
            session_token = authenticator.get_session_token()
            
            # Get account funds
            market_service = MarketService(
                app_key=betfair_config["app_key"],
                session_token=session_token,
                api_endpoint=betfair_config["api_endpoint"]
            )
            
            account_funds = market_service.get_account_funds()
            
            if account_funds:
                available_to_bet = account_funds.get("availableToBetBalance", 0)
                try:
                    self.account_balance = float(available_to_bet) if isinstance(available_to_bet, (int, float, str)) else 0.0
                    logger.info(f"Account balance loaded: {self.account_balance} EUR")
                except (ValueError, TypeError):
                    self.account_balance = None
                    logger.warning("Could not parse account balance")
            else:
                self.account_balance = None
                logger.warning("Could not retrieve account balance")
                
        except Exception as e:
            logger.warning(f"Error loading account balance: {str(e)}")
            self.account_balance = None
    
    def get_account_balance(self) -> Optional[float]:
        """Get account balance"""
        return self.account_balance
    
    def refresh_account_balance(self) -> bool:
        """Refresh account balance by re-authenticating"""
        try:
            self._load_account_balance()
            return self.account_balance is not None
        except Exception as e:
            logger.error(f"Error refreshing account balance: {str(e)}")
            return False

