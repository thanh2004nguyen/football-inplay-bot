"""
Logging setup module for Betfair Italy Bot
Configures file and console logging with rotation
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_config: dict) -> logging.Logger:
    """
    Setup logging configuration
    
    Args:
        log_config: Dictionary containing logging configuration
            - level: Log level (DEBUG, INFO, WARNING, ERROR)
            - file_path: Path to log file
            - max_bytes: Maximum log file size before rotation
            - backup_count: Number of backup log files to keep
            - console_output: Whether to output to console
            - clear_on_start: Whether to clear log file on each start (default: False)
    
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_file_path = log_config.get("file_path", "logs/betfair_bot.log")
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear log file on start if configured
    clear_on_start = log_config.get("clear_on_start", False)
    if clear_on_start and Path(log_file_path).exists():
        Path(log_file_path).unlink()
    
    # Get log level
    log_level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger("BetfairBot")
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # File formatter - keep timestamp for debugging
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console formatter - only show message (clean output)
    console_formatter = logging.Formatter('%(message)s')
    
    # File handler with rotation (UTF-8 encoding for Unicode support)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=log_config.get("max_bytes", 10485760),  # 10MB default
        backupCount=log_config.get("backup_count", 5),
        encoding='utf-8'  # Support Unicode characters
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler (with error handling for Windows console encoding issues)
    if log_config.get("console_output", True):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        # Wrap stream to handle encoding errors gracefully
        import sys
        if sys.stdout.encoding and sys.stdout.encoding.lower() in ['cp1252', 'windows-1252']:
            # On Windows with cp1252, replace problematic characters
            original_emit = console_handler.emit
            def safe_emit(record):
                try:
                    original_emit(record)
                except UnicodeEncodeError:
                    # Replace problematic Unicode characters with ASCII equivalents
                    record.msg = str(record.msg).encode('ascii', 'replace').decode('ascii')
                    original_emit(record)
            console_handler.emit = safe_emit
        logger.addHandler(console_handler)
    
    logger.info("Logging initialized successfully")
    return logger

