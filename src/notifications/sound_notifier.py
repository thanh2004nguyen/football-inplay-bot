"""
Sound Notifier Module
Handles playing sound notifications for bet events
"""
import logging
import os
from pathlib import Path
from typing import Optional

try:
    from playsound3 import playsound
except ImportError:
    playsound = None
    logging.getLogger("BetfairBot").warning("playsound3 not available, sound notifications disabled")

logger = logging.getLogger("BetfairBot")


class SoundNotifier:
    """Handles sound notifications for bet events"""
    
    def __init__(self, config: dict):
        """
        Initialize sound notifier
        
        Args:
            config: Configuration dictionary with sound settings
        """
        self.enabled = config.get("sound_enabled", False)
        self.sounds_config = config.get("sounds", {})
        
        # Get sound file paths
        project_root = Path(__file__).parent.parent.parent
        self.bet_placed_sound = self._get_sound_path(
            project_root, 
            self.sounds_config.get("bet_placed", "sounds/success.mp3")
        )
        self.bet_matched_sound = self._get_sound_path(
            project_root,
            self.sounds_config.get("bet_matched", "sounds/ping.mp3")
        )
        
        if not playsound:
            self.enabled = False
            logger.warning("playsound3 not available, sound notifications disabled")
    
    def _get_sound_path(self, project_root: Path, sound_file: str) -> Optional[str]:
        """
        Get full path to sound file
        
        Args:
            project_root: Project root directory
            sound_file: Sound file path (relative to project root)
        
        Returns:
            Full path to sound file, or None if not found
        """
        sound_path = project_root / sound_file
        
        if sound_path.exists():
            return str(sound_path)
        else:
            logger.warning(f"Sound file not found: {sound_path}")
            return None
    
    def _play_sound(self, sound_path: Optional[str], event_name: str):
        """
        Play a sound file
        
        Args:
            sound_path: Path to sound file
            event_name: Name of event (for logging)
        """
        if not self.enabled:
            return
        
        if not sound_path:
            logger.debug(f"No sound file for {event_name}")
            return
        
        if not playsound:
            logger.debug(f"playsound3 not available, cannot play {event_name} sound")
            return
        
        try:
            playsound(sound_path, block=False)  # block=False để không block thread
            logger.info(f"Played {event_name} sound: {sound_path}")
        except Exception as e:
            logger.error(f"Error playing {event_name} sound: {str(e)}")
    
    def play_bet_placed_sound(self):
        """Play sound when bet is placed"""
        self._play_sound(self.bet_placed_sound, "bet_placed")
    
    def play_bet_matched_sound(self):
        """Play sound when bet is matched"""
        self._play_sound(self.bet_matched_sound, "bet_matched")

