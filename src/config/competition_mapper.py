"""
Competition Mapper Module
Reads competition names from Excel file and maps them to Betfair competition IDs
"""
import pandas as pd
import logging
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Any, Tuple

logger = logging.getLogger("BetfairBot")


def read_competitions_from_excel(excel_path: str) -> Set[str]:
    """
    Read unique competition names from Excel file
    
    Args:
        excel_path: Path to Excel file
    
    Returns:
        Set of unique competition names
    """
    try:
        df = pd.read_excel(excel_path)
        
        # Get unique competition names from 'Competition' column
        if 'Competition' in df.columns:
            competitions = df['Competition'].dropna().unique().tolist()
            logger.info(f"Read {len(competitions)} unique competitions from Excel file")
            return set(competitions)
        else:
            logger.warning(f"Column 'Competition' not found in Excel file. Available columns: {df.columns.tolist()}")
            return set()
            
    except Exception as e:
        logger.error(f"Error reading Excel file: {str(e)}")
        return set()


# Country name mapping (Excel format -> Betfair format)
COUNTRY_MAPPING = {
    "argentina": "argentinian",
    "brazil": "brazilian",
    "bulgaria": "bulgarian",
    "china": "chinese",
    "croatia": "croatian",
    "czech": "czech",
    "denmark": "danish",
    "england": "english",
    "france": "french",
    "germany": "german",
    "greece": "greek",
    "hungary": "hungarian",
    "italy": "italian",
    "japan": "japanese",
    "netherlands": "dutch",
    "norway": "norwegian",
    "poland": "polish",
    "portugal": "portuguese",
    "romania": "romanian",
    "scotland": "scottish",
    "serbia": "serbian",
    "slovakia": "slovakian",
    "slovenia": "slovenian",
    "spain": "spanish",
    "sweden": "swedish",
    "switzerland": "swiss",
    "turkey": "turkish",
    "usa": "us",
    "wales": "welsh",
}

# League name normalization
LEAGUE_NORMALIZATION = {
    "serie a": "serie a",
    "serie b": "serie b",
    "premier league": "premier league",
    "championship": "championship",
    "league one": "league 1",
    "league two": "league 2",
    "ligue 2": "ligue 2",
    "national": "national",
    "bundesliga 1": "bundesliga",
    "3rd liga": "3. liga",
    "eredivisie": "eredivisie",
    "ekstraklasa": "ekstraklasa",
    "segunda liga": "segunda liga",
    "liga 1": "liga 1",
    "liga 2": "liga 2",
    "prva liga": "prva liga",
    "prvaliga": "prva liga",
    "2. snl": "2. snl",
    "2. liga": "2. liga",
    "super league": "super league",
    "superliga": "superliga",
    "allsvenskan": "allsvenskan",
    "challenge league": "challenge league",
    "1. lig": "1. lig",
    "mls": "mls",
    "vtora liga": "vtora liga",
    "division 1": "division 1",
    "division 2": "division 2",
    "primera division": "primera division",
    "segunda division": "segunda division",
    "brasilero serie a": "serie a",
    "brasilero serie b": "serie b",
    "chinese league": "chinese super league",
    "j. league 2": "j. league 2",
    "merchantil bank": "merchantil bank",
    "rl northeast": "regionalliga northeast",
}


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove special chars, remove extra spaces, normalize numbers"""
    if not text:
        return ""
    # Lowercase
    text = text.lower().strip()
    # Remove special characters (keep only letters, numbers, spaces)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Remove extra spaces
    text = ' '.join(text.split())
    
    # Normalize number words to digits (one->1, two->2, three->3, etc.)
    number_map = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
        '1st': '1', '2nd': '2', '3rd': '3', '4th': '4', '5th': '5'
    }
    words = text.split()
    words = [number_map.get(w, w) for w in words]
    text = ' '.join(words)
    
    return text


def normalize_excel_competition(excel_name: str) -> Tuple[Optional[str], Optional[str], str, str]:
    """Parse and normalize Excel competition name"""
    excel_lower = excel_name.lower().strip()
    
    # Split by "-" to get country and league
    if "-" in excel_lower:
        parts = excel_lower.split("-", 1)
        country = parts[0].strip()
        league = parts[1].strip()
    else:
        # No country prefix
        country = None
        league = excel_lower
    
    # Map country name
    if country:
        country_normalized = COUNTRY_MAPPING.get(country, country)
    else:
        country_normalized = None
    
    # Normalize league name
    league_normalized = LEAGUE_NORMALIZATION.get(league, league)
    
    # Create normalized full name for comparison
    if country_normalized and league_normalized:
        normalized_full = normalize_text(f"{country_normalized} {league_normalized}")
    elif league_normalized:
        normalized_full = normalize_text(league_normalized)
    else:
        normalized_full = normalize_text(excel_lower)
    
    return country_normalized, league_normalized, excel_lower, normalized_full


def normalize_betfair_competition(betfair_name: str) -> Tuple[Optional[str], Optional[str], str, str]:
    """Parse and normalize Betfair competition name"""
    betfair_lower = betfair_name.lower().strip()
    parts = betfair_lower.split()
    
    # Try to extract country (first word) and league (rest)
    if len(parts) > 1:
        possible_country = parts[0]
        league = " ".join(parts[1:])
    else:
        possible_country = None
        league = betfair_lower
    
    # Create normalized full name for comparison
    normalized_full = normalize_text(betfair_name)
    
    return possible_country, league, betfair_lower, normalized_full


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings (0-1)
    Handles cases where one string has extra words (like sponsor names)
    Example: "english league two" vs "english sky bet league 2" should match
    """
    if not str1 or not str2:
        return 0.0
    
    # Exact match
    if str1 == str2:
        return 1.0
    
    # Word-based similarity
    words1 = set(str1.split())
    words2 = set(str2.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate intersection (common words)
    intersection = words1 & words2
    
    # If one set is subset of another (e.g., "english league two" is subset of "english sky bet league 2")
    # This handles sponsor names in Betfair
    if words1.issubset(words2) or words2.issubset(words1):
        # Use the smaller set as denominator for higher similarity score
        smaller_set = min(len(words1), len(words2))
        if smaller_set > 0:
            return len(intersection) / smaller_set
    
    # Normal Jaccard similarity (intersection / union)
    union = words1 | words2
    if len(union) == 0:
        return 0.0
    
    return len(intersection) / len(union)


def map_competitions_to_ids(competition_names: Set[str], 
                            betfair_competitions: List[Dict[str, Any]]) -> List[int]:
    """
    Map competition names from Excel to Betfair competition IDs using similarity-based matching
    
    Args:
        competition_names: Set of competition names from Excel
        betfair_competitions: List of competition dictionaries from Betfair API
    
    Returns:
        List of competition IDs that match
    """
    matched_ids = []
    
    # Create a list of Betfair competitions with normalized names
    betfair_list = []
    for comp in betfair_competitions:
        comp_info = comp.get("competition", {})
        comp_id = comp_info.get("id")
        comp_name = comp_info.get("name", "")
        
        if comp_id and comp_name:
            _, _, _, normalized = normalize_betfair_competition(comp_name)
            betfair_list.append((comp_id, comp_name, normalized))
    
    # Match Excel competition names with Betfair competitions
    unmatched_competitions = []
    
    for excel_name in competition_names:
        excel_country, excel_league, excel_lower, excel_normalized = normalize_excel_competition(excel_name)
        
        best_match = None
        best_similarity = 0.0
        
        for comp_id, betfair_name, betfair_normalized in betfair_list:
            # Calculate similarity between normalized names
            similarity = calculate_similarity(excel_normalized, betfair_normalized)
            
            # Only match if similarity is high (>= 0.8 means 80% of words match)
            if similarity >= 0.8:
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = (comp_id, betfair_name, similarity)
        
        if best_match:
            comp_id, betfair_name, similarity = best_match
            similarity_pct = int(similarity * 100)
            matched_ids.append(comp_id)
            match_type = "EXACT" if similarity >= 0.95 else "HIGH_SIMILARITY"
            logger.info(f"Matched ({match_type}, {similarity_pct}%): '{excel_name}' -> '{betfair_name}' (ID: {comp_id})")
        else:
            unmatched_competitions.append(excel_name)
    
    # Log summary (only at DEBUG level to keep logs clean)
    if unmatched_competitions:
        logger.debug(f"No match found for {len(unmatched_competitions)} competition(s) - likely no active markets or name mismatch")
        logger.debug(f"Unmatched competitions: {', '.join(unmatched_competitions[:10])}{'...' if len(unmatched_competitions) > 10 else ''}")
    
    # Only log summary of matched competitions (important info)
    logger.info(f"Matched {len(matched_ids)} competition(s) from {len(competition_names)} Excel entries")
    return list(set(matched_ids))  # Remove duplicates


def get_competition_ids_from_excel(excel_path: str, 
                                   betfair_competitions: List[Dict[str, Any]]) -> List[int]:
    """
    Main function to get competition IDs from Excel file
    
    Args:
        excel_path: Path to Excel file
        betfair_competitions: List of competitions from Betfair API
    
    Returns:
        List of competition IDs
    """
    # Read competition names from Excel
    competition_names = read_competitions_from_excel(excel_path)
    
    if not competition_names:
        logger.warning("No competitions found in Excel file")
        return []
    
    # Map to Betfair IDs
    competition_ids = map_competitions_to_ids(competition_names, betfair_competitions)
    
    return competition_ids

