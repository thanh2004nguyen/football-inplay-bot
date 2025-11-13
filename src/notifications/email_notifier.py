"""
Email Notifier Module
Handles sending email notifications for important bot events
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime

logger = logging.getLogger("BetfairBot")


class EmailNotifier:
    """Handles email notifications for bot events"""
    
    def __init__(self, config: dict):
        """
        Initialize email notifier
        
        Args:
            config: Configuration dictionary with email settings
        """
        self.enabled = config.get("email_enabled", False)
        email_config = config.get("email", {})
        
        if not self.enabled:
            logger.debug("Email notifications disabled")
            return
        
        self.smtp_server = email_config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = email_config.get("smtp_port", 587)
        self.sender_email = email_config.get("sender_email", "")
        self.sender_password = email_config.get("sender_password", "")
        self.recipient_email = email_config.get("recipient_email", "")
        self.subject_prefix = email_config.get("subject_prefix", "[Betfair Bot]")
        
        # Validate configuration
        if not self.sender_email or not self.sender_password or not self.recipient_email:
            logger.warning("Email configuration incomplete, email notifications disabled")
            self.enabled = False
            return
        
        logger.info(f"Email notifier initialized")
        logger.info(f"  - SMTP Server: {self.smtp_server}:{self.smtp_port}")
        logger.info(f"  - Sender: {self.sender_email}")
        logger.info(f"  - Recipient: {self.recipient_email}")
    
    def _send_email(self, subject: str, body: str, is_html: bool = False) -> bool:
        """
        Send an email
        
        Args:
            subject: Email subject
            body: Email body
            is_html: Whether body is HTML format
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Email notifications disabled, skipping email send")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"{self.subject_prefix} {subject}"
            
            # Add body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Enable encryption
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            logger.error("Please check your email and password (use App Password for Gmail)")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_betfair_maintenance_alert(self, error_message: str):
        """
        Send alert when Betfair requires manual confirmation after maintenance
        
        Args:
            error_message: The error message from Betfair API
        """
        subject = "Betfair Requires Manual Confirmation"
        body = f"""
Betfair Bot Alert

The bot detected that Betfair requires manual confirmation.

Error: {error_message}

Action Required:
Please log in to the Betfair website (https://www.betfair.it) to:
1. Check for any maintenance notices
2. Accept updated terms and conditions if prompted
3. Confirm your account settings

After completing these steps, the bot will be able to log in automatically.

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_email(subject, body)
    
    def send_betfair_terms_confirmation_alert(self, error_message: str):
        """
        Send alert when Betfair requires terms/conditions acceptance
        
        Args:
            error_message: The error message from Betfair API
        """
        subject = "Betfair Terms Confirmation Required"
        body = f"""
Betfair Bot Alert

The bot detected that Betfair requires you to accept new terms and conditions.

Error: {error_message}

Action Required:
Please log in to the Betfair website (https://www.betfair.it) and:
1. Accept the updated terms and conditions
2. Confirm any required settings
3. The bot will automatically retry login after you complete this step

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self._send_email(subject, body)

