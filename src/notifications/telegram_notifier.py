"""
Telegram Notifier Module
Handles sending Telegram notifications for bet events
"""
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class TelegramNotifier:
    """Handles Telegram notifications for bot events"""
    
    def __init__(self, config: dict):
        """
        Initialize Telegram notifier
        
        Args:
            config: Configuration dictionary with Telegram settings
        """
        self.enabled = config.get("telegram_enabled", False)
        telegram_config = config.get("telegram", {})
        
        if not self.enabled:
            logger.debug("Telegram notifications disabled")
            return
        
        self.bot_token = telegram_config.get("bot_token", "")
        self.chat_id = telegram_config.get("chat_id", "")
        
        # Validate configuration
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram configuration incomplete, Telegram notifications disabled")
            self.enabled = False
            return
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
    
    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message via Telegram Bot API
        
        Args:
            text: Message text
            parse_mode: Parse mode for formatting (HTML or Markdown)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled, skipping message send")
            return False
        
        try:
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            response = requests.post(self.api_url, json=data, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                logger.debug(f"Telegram message sent successfully")
                return True
            else:
                error_code = result.get("error_code", "Unknown")
                error_desc = result.get("description", "Unknown error")
                logger.error(f"Telegram API error ({error_code}): {error_desc}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Telegram API request timeout")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram API request error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    def send_bet_matched_notification(self, bet_result: Dict[str, Any]):
        """
        Send notification when bet is matched
        
        Args:
            bet_result: Dictionary containing bet information
                - betId: Bet ID
                - eventName: Match name
                - marketName: Market name
                - runnerName: Selection name
                - layPrice: Lay odds
                - stake: Stake amount
                - sizeMatched: Matched amount
        """
        try:
            event_name = bet_result.get("eventName", "N/A")
            market_name = bet_result.get("marketName", "N/A")
            runner_name = bet_result.get("runnerName", "N/A")
            lay_price = bet_result.get("layPrice", 0.0)
            stake = bet_result.get("stake", 0.0)
            size_matched = bet_result.get("sizeMatched", 0.0)
            bet_id = bet_result.get("betId", "N/A")
            
            message = f"""🎯 <b>Bet Matched!</b>

📊 <b>Match:</b> {event_name}
📈 <b>Market:</b> {market_name}
🎲 <b>Selection:</b> {runner_name}
💰 <b>Odds:</b> {lay_price}
💵 <b>Stake:</b> {stake:.2f} EUR
✅ <b>Matched:</b> {size_matched:.2f} EUR
🆔 <b>Bet ID:</b> {bet_id}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            self._send_message(message)
            
        except Exception as e:
            logger.error(f"Error formatting bet matched notification: {str(e)}")
    
    def send_bet_settled_notification(self, bet_record: Any, outcome: str, profit_loss: float, final_score: Optional[str] = None, event_name: Optional[str] = None):
        """
        Send notification when bet is settled (Won or Lost)
        
        Args:
            bet_record: BetRecord object or dictionary with bet information
            outcome: "Won" or "Lost"
            profit_loss: Profit or loss amount (positive for win, negative for loss)
            final_score: Final match score (optional)
            event_name: Event/match name (optional, will try to extract from bet_record if not provided)
        """
        try:
            # Extract bet information
            if hasattr(bet_record, 'bet_id'):
                # BetRecord object
                if not event_name:
                    event_name = getattr(bet_record, 'event_name', None) or getattr(bet_record, 'match_id', 'N/A')
                market_name = getattr(bet_record, 'market_name', 'N/A')
                selection = getattr(bet_record, 'selection', 'N/A')
                odds = getattr(bet_record, 'odds', 0.0)
                stake = getattr(bet_record, 'stake', 0.0)
                bet_id = getattr(bet_record, 'bet_id', 'N/A')
            else:
                # Dictionary
                if not event_name:
                    event_name = bet_record.get("event_name", bet_record.get("match_id", "N/A"))
                market_name = bet_record.get("market_name", "N/A")
                selection = bet_record.get("selection", "N/A")
                odds = bet_record.get("odds", 0.0)
                stake = bet_record.get("stake", 0.0)
                bet_id = bet_record.get("bet_id", "N/A")
            
            # Format message based on outcome
            if outcome == "Won":
                emoji = "✅"
                title = "Bet Won!"
                result_text = f"💚 <b>Profit:</b> +{profit_loss:.2f} EUR"
            elif outcome == "Lost":
                emoji = "❌"
                title = "Bet Lost"
                result_text = f"💔 <b>Loss:</b> {profit_loss:.2f} EUR"
            else:
                # Should not happen, but handle gracefully
                emoji = "⚠️"
                title = f"Bet {outcome}"
                result_text = f"💰 <b>P/L:</b> {profit_loss:.2f} EUR"
            
            # Build message
            message = f"""{emoji} <b>{title}</b>

📊 <b>Match:</b> {event_name}"""
            
            if final_score:
                message += f"\n🏆 <b>Final Score:</b> {final_score}"
            
            message += f"""
📈 <b>Market:</b> {market_name}
🎲 <b>Selection:</b> {selection}
💰 <b>Odds:</b> {odds}
💵 <b>Stake:</b> {stake:.2f} EUR
{result_text}
🆔 <b>Bet ID:</b> {bet_id}
🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            self._send_message(message)
            
        except Exception as e:
            logger.error(f"Error formatting bet settled notification: {str(e)}")

