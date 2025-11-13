"""
Price Ladder Module
Handles Betfair price ladder calculations for CLASSIC and FINEST ladders
"""
import logging
from typing import Optional

logger = logging.getLogger("BetfairBot")


# CLASSIC Price Ladder increments (from Betfair API documentation)
CLASSIC_LADDER = [
    (1.01, 2.0, 0.01),      # 1.01 → 2: increment 0.01
    (2.0, 3.0, 0.02),      # 2 → 3: increment 0.02
    (3.0, 4.0, 0.05),      # 3 → 4: increment 0.05
    (4.0, 6.0, 0.1),       # 4 → 6: increment 0.1
    (6.0, 10.0, 0.2),      # 6 → 10: increment 0.2
    (10.0, 20.0, 0.5),     # 10 → 20: increment 0.5
    (20.0, 30.0, 1.0),     # 20 → 30: increment 1.0
    (30.0, 50.0, 2.0),     # 30 → 50: increment 2.0
    (50.0, 100.0, 5.0),    # 50 → 100: increment 5.0
    (100.0, 1000.0, 10.0), # 100 → 1000: increment 10.0
]

# FINEST Price Ladder: always 0.01 increment
FINEST_INCREMENT = 0.01


def get_increment_for_price(price: float, ladder_type: str = "CLASSIC") -> float:
    """
    Get the price increment for a given price based on ladder type
    
    Args:
        price: The price value
        ladder_type: "CLASSIC" or "FINEST"
    
    Returns:
        The increment value for the price range
    """
    if ladder_type == "FINEST":
        return FINEST_INCREMENT
    
    # CLASSIC ladder
    for min_price, max_price, increment in CLASSIC_LADDER:
        if min_price <= price < max_price:
            return increment
    
    # If price >= 1000, use last increment
    if price >= 1000.0:
        return CLASSIC_LADDER[-1][2]
    
    # If price < 1.01, use first increment
    if price < 1.01:
        return CLASSIC_LADDER[0][2]
    
    logger.warning(f"Could not determine increment for price {price}, using 0.01")
    return 0.01


def add_ticks_to_price(price: float, ticks: int, ladder_type: str = "CLASSIC") -> float:
    """
    Add ticks to a price
    
    Args:
        price: The base price
        ticks: Number of ticks to add (can be negative to subtract)
        ladder_type: "CLASSIC" or "FINEST"
    
    Returns:
        The new price after adding ticks
    """
    increment = get_increment_for_price(price, ladder_type)
    new_price = price + (ticks * increment)
    
    # Round to appropriate decimal places
    if increment >= 1.0:
        new_price = round(new_price, 0)
    elif increment >= 0.1:
        new_price = round(new_price, 1)
    elif increment >= 0.01:
        new_price = round(new_price, 2)
    else:
        new_price = round(new_price, 3)
    
    return new_price


def calculate_ticks_between(price1: float, price2: float, ladder_type: str = "CLASSIC") -> int:
    """
    Calculate the number of ticks between two prices
    
    Args:
        price1: First price (lower price)
        price2: Second price (higher price)
        ladder_type: "CLASSIC" or "FINEST"
    
    Returns:
        Number of ticks between the two prices
    """
    if price1 >= price2:
        return 0
    
    # For FINEST, simple calculation
    if ladder_type == "FINEST":
        ticks = int((price2 - price1) / FINEST_INCREMENT)
        return ticks
    
    # For CLASSIC, need to handle different increments across ranges
    current_price = price1
    total_ticks = 0
    
    while current_price < price2:
        increment = get_increment_for_price(current_price, ladder_type)
        
        # Find the next boundary
        next_boundary = None
        for min_price, max_price, _ in CLASSIC_LADDER:
            if min_price <= current_price < max_price:
                next_boundary = max_price
                break
        
        if next_boundary is None or next_boundary > price2:
            # Remaining distance is within same increment range
            remaining = price2 - current_price
            ticks_in_range = int(remaining / increment)
            total_ticks += ticks_in_range
            break
        else:
            # Calculate ticks to next boundary
            distance_to_boundary = next_boundary - current_price
            ticks_to_boundary = int(distance_to_boundary / increment)
            total_ticks += ticks_to_boundary
            current_price = next_boundary
    
    return total_ticks


def is_valid_price(price: float, ladder_type: str = "CLASSIC") -> bool:
    """
    Check if a price is valid according to the price ladder
    
    Args:
        price: The price to validate
        ladder_type: "CLASSIC" or "FINEST"
    
    Returns:
        True if price is valid, False otherwise
    """
    if price < 1.01:
        return False
    
    if ladder_type == "FINEST":
        # FINEST: any price with 2 decimal places is valid
        return abs(price - round(price, 2)) < 0.001
    
    # CLASSIC: check if price matches valid increments
    for min_price, max_price, increment in CLASSIC_LADDER:
        if min_price <= price < max_price:
            # Check if price is a multiple of increment from min_price
            diff = price - min_price
            if abs(diff % increment) < 0.001 or abs(diff % increment - increment) < 0.001:
                return True
    
    # Check if price >= 1000 (use last increment)
    if price >= 1000.0:
        increment = CLASSIC_LADDER[-1][2]
        base = 1000.0
        diff = price - base
        return abs(diff % increment) < 0.001 or abs(diff % increment - increment) < 0.001
    
    return False


def round_to_valid_price(price: float, ladder_type: str = "CLASSIC") -> float:
    """
    Round a price to the nearest valid price according to the ladder
    
    Args:
        price: The price to round
        ladder_type: "CLASSIC" or "FINEST"
    
    Returns:
        The nearest valid price
    """
    if price < 1.01:
        return 1.01
    
    increment = get_increment_for_price(price, ladder_type)
    
    if ladder_type == "FINEST":
        return round(price, 2)
    
    # CLASSIC: round to nearest multiple of increment
    for min_price, max_price, inc in CLASSIC_LADDER:
        if min_price <= price < max_price:
            diff = price - min_price
            ticks = round(diff / inc)
            return min_price + (ticks * inc)
    
    # If price >= 1000
    if price >= 1000.0:
        increment = CLASSIC_LADDER[-1][2]
        base = 1000.0
        diff = price - base
        ticks = round(diff / increment)
        return base + (ticks * increment)
    
    return round(price, 2)

