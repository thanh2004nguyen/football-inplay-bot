"""
Configuration loader module
Loads and validates configuration from JSON file and environment variables
"""
import json
import os
from pathlib import Path
from typing import Dict, Any

# Optional: python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    # Define a dummy function if dotenv is not available
    def load_dotenv(path):
        pass


def load_config(config_path: str = "config/config.json") -> Dict[str, Any]:
    """
    Load configuration from JSON file and environment variables
    
    Args:
        config_path: Path to configuration JSON file
    
    Returns:
        Dictionary containing merged configuration
    
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    # Load environment variables from .env file if it exists
    if HAS_DOTENV:
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path)
    
    # Load JSON config
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create {config_path} and fill in your credentials"
        )
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Override with environment variables if they exist
    if "betfair" in config:
        betfair_config = config["betfair"]
        
        # Override from environment variables
        if os.getenv("BETFAIR_APP_KEY"):
            betfair_config["app_key"] = os.getenv("BETFAIR_APP_KEY")
        if os.getenv("BETFAIR_USERNAME"):
            betfair_config["username"] = os.getenv("BETFAIR_USERNAME")
        if os.getenv("BETFAIR_CERT_PATH"):
            betfair_config["certificate_path"] = os.getenv("BETFAIR_CERT_PATH")
        if os.getenv("BETFAIR_KEY_PATH"):
            betfair_config["key_path"] = os.getenv("BETFAIR_KEY_PATH")
    
    # Get password from environment (never store in JSON)
    if os.getenv("BETFAIR_PASSWORD"):
        config["betfair"]["password"] = os.getenv("BETFAIR_PASSWORD")
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration structure and required fields
    
    Args:
        config: Configuration dictionary
    
    Returns:
        True if valid, raises ValueError if invalid
    """
    required_sections = ["betfair", "monitoring", "logging"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Validate Betfair section
    betfair = config["betfair"]
    required_betfair_fields = ["app_key", "username"]
    for field in required_betfair_fields:
        if field not in betfair or not betfair[field] or betfair[field].startswith("YOUR_"):
            raise ValueError(
                f"Missing or invalid Betfair configuration: {field}\n"
                f"Please update config/config.json with your actual credentials"
            )
    
    # Check certificate files exist
    cert_path = betfair.get("certificate_path")
    key_path = betfair.get("key_path")
    
    if cert_path and not Path(cert_path).exists():
        raise FileNotFoundError(f"Certificate file not found: {cert_path}")
    if key_path and not Path(key_path).exists():
        raise FileNotFoundError(f"Key file not found: {key_path}")
    
    # Check password is provided (from env or config)
    if "password" not in betfair or not betfair["password"]:
        raise ValueError(
            "Betfair password not found. Please set BETFAIR_PASSWORD environment variable"
        )
    
    return True

