"""
Flask Web Application
Provides web interface for controlling the bot
"""
from flask import Flask, render_template, jsonify, request
import logging
from pathlib import Path
import socket
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.bot_service import BotService

logger = logging.getLogger("BetfairBot")

app = Flask(__name__, 
            template_folder=str(Path(__file__).parent.parent.parent / "templates"),
            static_folder=str(Path(__file__).parent.parent.parent / "static"))

# Initialize bot service
bot_service = BotService()

# Disable Flask request logging for /api/status to reduce console spam
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)  # Only show warnings and errors, not INFO requests


def get_local_ip():
    """Get local IP address for network access"""
    try:
        # Connect to a remote address to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


@app.route('/')
def dashboard():
    """Main dashboard page"""
    local_ip = get_local_ip()
    return render_template('dashboard.html', local_ip=local_ip)


@app.route('/api/status')
def api_status():
    """Get bot status"""
    status = bot_service.get_status()
    return jsonify(status)


@app.route('/api/start', methods=['POST'])
def api_start():
    """Start the bot"""
    result = bot_service.start()
    return jsonify(result)


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop the bot"""
    result = bot_service.stop()
    return jsonify(result)


@app.route('/api/matches')
def api_matches():
    """Get active matches"""
    matches = bot_service.get_matches()
    return jsonify({"matches": matches, "count": len(matches)})


@app.route('/api/bets')
def api_bets():
    """Get bet history"""
    bets = bot_service.get_bets()
    return jsonify({"bets": bets, "count": len(bets)})


@app.route('/api/account-balance')
def api_account_balance():
    """Get account balance"""
    try:
        balance = bot_service.get_account_balance()
        if balance is not None:
            return jsonify({
                "success": True, 
                "balance": balance,
                "formatted": f"{balance:.2f} EUR"
            })
        else:
            return jsonify({
                "success": False, 
                "balance": None, 
                "error": "Could not retrieve account balance. Please check authentication."
            })
    except Exception as e:
        logger.error(f"Error getting account balance: {str(e)}")
        return jsonify({"success": False, "balance": None, "error": str(e)})


@app.route('/api/refresh-balance', methods=['POST'])
def api_refresh_balance():
    """Refresh account balance"""
    try:
        success = bot_service.refresh_account_balance()
        balance = bot_service.get_account_balance()
        if success and balance is not None:
            return jsonify({
                "success": True, 
                "balance": balance,
                "formatted": f"{balance:.2f} EUR"
            })
        else:
            return jsonify({
                "success": False, 
                "balance": None, 
                "error": "Could not refresh account balance"
            })
    except Exception as e:
        logger.error(f"Error refreshing account balance: {str(e)}")
        return jsonify({"success": False, "balance": None, "error": str(e)})


# Track log file position for streaming
_log_file_position = {}

@app.route('/api/logs')
def api_logs():
    """Get new log entries from log file (streaming)"""
    try:
        from pathlib import Path
        from config.loader import load_config
        
        # Get log file path from config
        config = load_config()
        log_path = config.get("logging", {}).get("file_path", "logs/betfair_bot.log")
        log_file = Path(log_path)
        
        if not log_file.exists():
            return jsonify({
                "success": False,
                "logs": [],
                "error": "Log file not found"
            })
        
        # Get client ID from request (use session or IP)
        client_id = request.remote_addr or "default"
        
        # Get last position for this client
        last_position = _log_file_position.get(client_id, 0)
        
        try:
            # Open file and seek to last position
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # If file was truncated or position is beyond file size, reset
                f.seek(0, 2)  # Seek to end
                current_size = f.tell()
                
                if last_position > current_size:
                    # File was truncated, reset position
                    last_position = 0
                
                # Seek to last position
                f.seek(last_position)
                
                # Read new lines
                new_lines = f.readlines()
                
                # Update position
                _log_file_position[client_id] = f.tell()
                
                # Process lines: remove trailing newlines and filter empty
                raw_logs = [line.rstrip('\n\r') for line in new_lines if line.strip()]
                
                # Parse logs to extract only the message content
                # Format: "YYYY-MM-DD HH:MM:SS - LoggerName - LEVEL - module - message"
                # We want to extract only the message part
                parsed_logs = []
                for log_line in raw_logs:
                    # Try to parse log format: "timestamp - logger - level - module - message"
                    # Split by " - " and take the last part (message)
                    parts = log_line.split(' - ')
                    if len(parts) >= 5:
                        # Standard format: timestamp - logger - level - module - message
                        message = ' - '.join(parts[4:])  # Join in case message contains " - "
                    elif len(parts) >= 4:
                        # Alternative format: timestamp - logger - level - message
                        message = ' - '.join(parts[3:])
                    elif len(parts) >= 3:
                        # Alternative format: timestamp - logger - message
                        message = ' - '.join(parts[2:])
                    else:
                        # No standard format, use as is
                        message = log_line
                    
                    parsed_logs.append(message)
                
            return jsonify({
                "success": True,
                "logs": parsed_logs,
                "count": len(parsed_logs),
                "new": len(parsed_logs) > 0
            })
        except Exception as e:
            logger.error(f"Error reading log file: {str(e)}")
            return jsonify({
                "success": False,
                "logs": [],
                "error": str(e)
            })
            
    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")
        return jsonify({
            "success": False,
            "logs": [],
            "error": str(e)
        })


@app.route('/api/logs/reset', methods=['POST'])
def api_logs_reset():
    """Reset log position to end of file (don't load old logs, only new ones)"""
    try:
        from pathlib import Path
        from config.loader import load_config
        
        client_id = request.remote_addr or "default"
        
        # Get log file path from config
        config = load_config()
        log_path = config.get("logging", {}).get("file_path", "logs/betfair_bot.log")
        log_file = Path(log_path)
        
        if log_file.exists():
            # Set position to end of file (don't load old logs)
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, 2)  # Seek to end
                _log_file_position[client_id] = f.tell()
        else:
            _log_file_position[client_id] = 0
            
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error resetting log position: {str(e)}")
        client_id = request.remote_addr or "default"
        _log_file_position[client_id] = 0
        return jsonify({"success": True})


# get_local_ip function is now in run_web.py

