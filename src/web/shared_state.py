"""
Shared State Module
Allows communication between BotService and main() for stop signals
"""
import threading

# Global stop event that can be set by BotService and checked by main()
_stop_event = None


def set_stop_event(event: threading.Event):
    """Set the stop event (called by BotService)"""
    global _stop_event
    _stop_event = event


def get_stop_event() -> threading.Event:
    """Get the stop event (called by main())"""
    return _stop_event


def should_stop() -> bool:
    """Check if bot should stop"""
    if _stop_event is None:
        return False
    return _stop_event.is_set()

