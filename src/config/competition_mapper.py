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
    Supports both old format (Competition column) and new format (Competition-Live column)
    
    Args:
        excel_path: Path to Excel file
    
    Returns:
        Set of unique competition names (from Competition-Live if available, else Competition)
    """
    try:
        df = pd.read_excel(excel_path)
        
        # Priority 1: Use new columns (Competition-Live) if available
        if 'Competition-Live' in df.columns:
            competitions = df['Competition-Live'].dropna().unique().tolist()
            logger.info(f"Read {len(competitions)} unique competitions from 'Competition-Live' column")
            return set(competitions)
        
        # Priority 2: Fallback to old column (Competition)
        elif 'Competition' in df.columns:
            competitions = df['Competition'].dropna().unique().tolist()
            logger.info(f"Read {len(competitions)} unique competitions from 'Competition' column (legacy)")
            return set(competitions)
        else:
            logger.warning(f"Neither 'Competition-Live' nor 'Competition' column found in Excel file. Available columns: {df.columns.tolist()}")
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

# Country keywords for matching (Excel country -> Betfair keywords)
COUNTRY_KEYWORDS = {
    "italy": ["italian", "italy"],
    "england": ["english", "england"],
    "spain": ["spanish", "spain"],
    "france": ["french", "france"],
    "germany": ["german", "germany"],
    "brazil": ["brazilian", "brazil"],
    "netherlands": ["dutch", "netherlands"],
    "portugal": ["portuguese", "portugal"],
    "poland": ["polish", "poland"],
    "czech": ["czech"],
    "romania": ["romanian", "romania"],
    "serbia": ["serbian", "serbia"],
    "slovakia": ["slovakian", "slovakia"],
    "slovenia": ["slovenian", "slovenia"],
    "turkey": ["turkish", "turkey"],
    "greece": ["greek", "greece"],
    "sweden": ["swedish", "sweden"],
    "norway": ["norwegian", "norway"],
    "denmark": ["danish", "denmark"],
    "croatia": ["croatian", "croatia"],
    "bulgaria": ["bulgarian", "bulgaria"],
    "switzerland": ["swiss", "switzerland"],
    "japan": ["japanese", "japan"],
    "china": ["chinese", "china"],
    "usa": ["us", "usa", "american"],
    "scotland": ["scottish", "scotland"],
    "argentina": ["argentinian", "argentina"],
    "wales": ["welsh", "wales"],
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


def check_country_match(excel_country: Optional[str], betfair_normalized: str) -> bool:
    """
    Check if Excel country matches Betfair competition name
    
    Args:
        excel_country: Country from Excel (e.g., "italy", "england")
        betfair_normalized: Normalized Betfair competition name
    
    Returns:
        True if country matches
    """
    if not excel_country:
        return False
    
    keywords = COUNTRY_KEYWORDS.get(excel_country, [excel_country])
    return any(keyword in betfair_normalized for keyword in keywords)


def check_league_match(excel_league: Optional[str], betfair_league: Optional[str]) -> bool:
    """
    Check if Excel league matches Betfair league
    
    Args:
        excel_league: League from Excel
        betfair_league: League from Betfair
    
    Returns:
        True if leagues match (exact or substring)
    """
    if not excel_league or not betfair_league:
        return False
    
    excel_league_norm = LEAGUE_NORMALIZATION.get(excel_league, excel_league)
    betfair_league_norm = LEAGUE_NORMALIZATION.get(betfair_league, betfair_league)
    
    # Exact match or substring match
    return (
        excel_league_norm == betfair_league_norm or
        excel_league_norm in betfair_league_norm or
        betfair_league_norm in excel_league_norm
    )


def validate_country_and_league(excel_country: Optional[str],
                                 excel_league: Optional[str],
                                 betfair_normalized: str,
                                 betfair_league: Optional[str]) -> bool:
    """
    Validate that both country and league match between Excel and Betfair
    
    Args:
        excel_country: Country from Excel
        excel_league: League from Excel
        betfair_normalized: Normalized Betfair competition name
        betfair_league: League from Betfair
    
    Returns:
        True if both country and league match, or country matches if no league info
    """
    if not excel_country:
        return True  # No country to validate
    
    country_match = check_country_match(excel_country, betfair_normalized)
    
    if excel_league:
        # Both country and league must match
        league_match = check_league_match(excel_league, betfair_league)
        return country_match and league_match
    else:
        # Only country needs to match
        return country_match


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
    
    # Create a list of Betfair competitions with normalized names and league names
    betfair_list = []
    for comp in betfair_competitions:
        comp_info = comp.get("competition", {})
        comp_id = comp_info.get("id")
        comp_name = comp_info.get("name", "")
        
        if comp_id and comp_name:
            _, _, _, normalized = normalize_betfair_competition(comp_name)
            # Extract league name from Betfair competition
            _, betfair_league, _, _ = normalize_betfair_competition(comp_name)
            betfair_list.append((comp_id, comp_name, normalized, betfair_league))
    
    # Match Excel competition names with Betfair competitions
    unmatched_competitions = []
    
    for excel_name in competition_names:
        excel_country, excel_league, excel_lower, excel_normalized = normalize_excel_competition(excel_name)
        
        best_match = None
        best_similarity = 0.0
        match_method = ""
        
        # Strategy 1: Full name similarity matching (strict)
        for comp_id, betfair_name, betfair_normalized, betfair_league in betfair_list:
            similarity = calculate_similarity(excel_normalized, betfair_normalized)
            
            # Require high similarity (>= 0.75) to avoid false matches
            if similarity >= 0.75:
                # Additional validation: check if country and league match
                is_valid = validate_country_and_league(
                    excel_country, excel_league, betfair_normalized, betfair_league
                )
                
                if is_valid and similarity > best_similarity:
                    best_similarity = similarity
                    best_match = (comp_id, betfair_name, similarity)
                    match_method = "full_name"
        
        # Strategy 2: League name matching (if we have league names) - STRICT
        if excel_league and excel_country:  # Require both country and league
            for comp_id, betfair_name, betfair_normalized, betfair_league in betfair_list:
                if betfair_league:
                    # Validate country match first
                    if not check_country_match(excel_country, betfair_normalized):
                        continue
                    
                    # Normalize league names using LEAGUE_NORMALIZATION
                    excel_league_norm = LEAGUE_NORMALIZATION.get(excel_league, excel_league)
                    betfair_league_norm = LEAGUE_NORMALIZATION.get(betfair_league, betfair_league)
                    
                    # Exact league match
                    if excel_league_norm == betfair_league_norm:
                        similarity = 0.95
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = (comp_id, betfair_name, similarity)
                            match_method = "league_exact"
                    
                    # Substring league match (strict: must be substantial)
                    elif (excel_league_norm in betfair_league_norm or betfair_league_norm in excel_league_norm) and len(excel_league_norm) >= 4:
                        similarity = 0.90
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = (comp_id, betfair_name, similarity)
                            match_method = "league_substring"
                    
                    # League similarity (strict threshold)
                    else:
                        league_similarity = calculate_similarity(excel_league_norm, betfair_league_norm)
                        if league_similarity >= 0.85:  # Increased from 0.7 to 0.85 for strictness
                            similarity = 0.85
                            if similarity > best_similarity:
                                best_similarity = similarity
                                best_match = (comp_id, betfair_name, similarity)
                                match_method = "league_similarity"
        
        # Strategy 3: Substring matching (fallback) - STRICT
        if not best_match or best_similarity < 0.85:
            for comp_id, betfair_name, betfair_normalized, betfair_league in betfair_list:
                # Check if one contains the other (substantial match)
                if excel_normalized in betfair_normalized or betfair_normalized in excel_normalized:
                    if len(excel_normalized) >= 6 and len(betfair_normalized) >= 6:  # Increased from 4 to 6
                        # Additional validation: check country match if available
                        is_valid = True
                        if excel_country:
                            is_valid = check_country_match(excel_country, betfair_normalized)
                        
                        if is_valid:
                            similarity = 0.80
                            if similarity > best_similarity:
                                best_similarity = similarity
                                best_match = (comp_id, betfair_name, similarity)
                                match_method = "substring"
        
        # Only accept if similarity >= 0.75 (strict threshold to avoid false matches)
        if best_match and best_similarity >= 0.75:
            comp_id, betfair_name, similarity = best_match
            similarity_pct = int(similarity * 100)
            matched_ids.append(comp_id)
            match_type = "EXACT" if similarity >= 0.95 else "HIGH_SIMILARITY" if similarity >= 0.85 else "MEDIUM_SIMILARITY"
            logger.info(f"Matched ({match_type}, {similarity_pct}%, {match_method}): '{excel_name}' -> '{betfair_name}' (ID: {comp_id})")
        else:
            unmatched_competitions.append(excel_name)
    
    # Log summary
    if unmatched_competitions:
        logger.warning(f"No match found for {len(unmatched_competitions)} competition(s): {', '.join(unmatched_competitions[:10])}{'...' if len(unmatched_competitions) > 10 else ''}")
    
    match_rate = len(matched_ids) / len(competition_names) * 100 if competition_names else 0
    logger.info(f"Matched {len(matched_ids)} competition(s) from {len(competition_names)} Excel entries ({match_rate:.1f}%)")
    return list(set(matched_ids))  # Remove duplicates


def map_competitions_direct_from_excel(excel_path: str,
                                       betfair_competitions: List[Dict[str, Any]]) -> List[int]:
    """
    Map competitions directly from Competition-Betfair column (new format)
    This provides 100% accurate mapping without similarity matching
    
    Args:
        excel_path: Path to Excel file
        betfair_competitions: List of competitions from Betfair API
    
    Returns:
        List of competition IDs that match
    """
    try:
        df = pd.read_excel(excel_path)
        
        # Check if new columns exist
        if 'Competition-Betfair' not in df.columns:
            logger.debug("'Competition-Betfair' column not found, cannot use direct mapping")
            return []
        
        # Get unique Betfair competition names from Excel
        betfair_names_from_excel = df['Competition-Betfair'].dropna().unique().tolist()
        
        if not betfair_names_from_excel:
            logger.debug("No 'Competition-Betfair' values found in Excel")
            return []
        
        # Create a mapping: Betfair name -> Betfair ID, and "ID_Name" -> Betfair ID
        betfair_name_to_id = {}
        betfair_id_name_to_id = {}
        for comp in betfair_competitions:
            comp_info = comp.get("competition", {})
            comp_id = comp_info.get("id")
            comp_name = comp_info.get("name", "")
            if comp_id and comp_name:
                # Map name -> ID
                betfair_name_to_id[comp_name] = comp_id
                # Map "ID_Name" -> ID
                betfair_id_name_to_id[f"{comp_id}_{comp_name}"] = comp_id
        
        # Match Excel Betfair names with actual Betfair competitions
        matched_ids = []
        unmatched_names = []
        
        for excel_betfair_name in betfair_names_from_excel:
            excel_betfair_name = str(excel_betfair_name).strip()
            
            # Try exact match first (supports both "Name" and "ID_Name" format)
            if excel_betfair_name in betfair_name_to_id:
                comp_id = betfair_name_to_id[excel_betfair_name]
                matched_ids.append(comp_id)
                logger.info(f"Direct match: '{excel_betfair_name}' -> ID: {comp_id}")
            elif excel_betfair_name in betfair_id_name_to_id:
                comp_id = betfair_id_name_to_id[excel_betfair_name]
                matched_ids.append(comp_id)
                # Logging moved to main.py setup checklist
            else:
                # Try case-insensitive match
                found = False
                for betfair_name, comp_id in betfair_name_to_id.items():
                    if excel_betfair_name.lower() == betfair_name.lower():
                        matched_ids.append(comp_id)
                        logger.info(f"Direct match (case-insensitive): '{excel_betfair_name}' -> '{betfair_name}' (ID: {comp_id})")
                        found = True
                        break
                
                # Try matching with "ID_Name" format (extract ID from Excel and match)
                if not found and "_" in excel_betfair_name:
                    try:
                        excel_parts = excel_betfair_name.split("_", 1)
                        excel_id = excel_parts[0].strip()
                        excel_name = excel_parts[1].strip()
                        # Try matching with name part
                        for betfair_name, comp_id in betfair_name_to_id.items():
                            if excel_name.lower() == betfair_name.lower():
                                matched_ids.append(comp_id)
                                logger.info(f"Direct match (ID_Name format, name part): '{excel_betfair_name}' -> '{betfair_name}' (ID: {comp_id})")
                                found = True
                                break
                    except:
                        pass
                
                if not found:
                    unmatched_names.append(excel_betfair_name)
        
        # Removed warning log for unmatched names to reduce noise
        # if unmatched_names:
        #     logger.warning(f"Direct mapping: {len(unmatched_names)} Betfair competition name(s) not found: {', '.join(unmatched_names[:10])}{'...' if len(unmatched_names) > 10 else ''}")
        
        # Logging moved to main.py setup checklist
        return list(set(matched_ids))  # Remove duplicates
        
    except Exception as e:
        logger.error(f"Error in direct mapping from Excel: {str(e)}")
        return []


def get_competition_ids_from_excel(excel_path: str, 
                                   betfair_competitions: List[Dict[str, Any]]) -> List[int]:
    """
    Main function to get competition IDs from Excel file
    Uses direct mapping (Competition-Betfair) if available, otherwise falls back to similarity matching
    
    Args:
        excel_path: Path to Excel file
        betfair_competitions: List of competitions from Betfair API
    
    Returns:
        List of competition IDs
    """
    try:
        df = pd.read_excel(excel_path)
        
        # Strategy 1: Direct mapping (new format with Competition-Betfair column)
        if 'Competition-Betfair' in df.columns:
            # Logging moved to main.py setup checklist
            competition_ids = map_competitions_direct_from_excel(excel_path, betfair_competitions)
            if competition_ids:
                return competition_ids
            else:
                logger.warning("Direct mapping returned no results, falling back to similarity matching")
        
        # Strategy 2: Similarity matching (old format with Competition column)
        logger.info("Using similarity matching from 'Competition' column")
        competition_names = read_competitions_from_excel(excel_path)
        
        if not competition_names:
            logger.warning("No competitions found in Excel file")
            return []
        
        # Map to Betfair IDs using similarity matching
        competition_ids = map_competitions_to_ids(competition_names, betfair_competitions)
        
        return competition_ids
        
    except Exception as e:
        logger.error(f"Error getting competition IDs from Excel: {str(e)}")
        return []


def get_live_api_competition_ids_from_excel(excel_path: str) -> List[str]:
    """
    Get Live API competition IDs from Excel file (from Competition-Live column)
    
    Extracts competition IDs from format "ID_Name" (e.g., "4_Serie A") or just uses name
    if format is just "Name"
    
    Args:
        excel_path: Path to Excel file
    
    Returns:
        List of Live API competition IDs (as strings)
    """
    try:
        df = pd.read_excel(excel_path)
        
        competition_ids = []
        
        # Priority: Use Competition-Live column if available
        if 'Competition-Live' in df.columns:
            competitions = df['Competition-Live'].dropna().unique().tolist()
            
            for comp in competitions:
                comp_str = str(comp).strip()
                if not comp_str:
                    continue
                
                # Extract ID from format "ID_Name" (e.g., "4_Serie A")
                if "_" in comp_str:
                    try:
                        parts = comp_str.split("_", 1)
                        comp_id = parts[0].strip()
                        # Validate that first part is a number (ID)
                        if comp_id.isdigit():
                            competition_ids.append(comp_id)
                        else:
                            # Not a valid ID format, skip
                            logger.debug(f"Skipping competition '{comp_str}' - ID part '{comp_id}' is not numeric")
                    except Exception as e:
                        logger.debug(f"Error parsing competition '{comp_str}': {str(e)}")
                else:
                    # Format is just "Name" without ID - cannot filter by ID
                    # We'll need to filter by name after getting matches
                    logger.debug(f"Competition '{comp_str}' has no ID, will filter by name")
        
        # Remove duplicates and return
        unique_ids = list(set(competition_ids))
        # Log removed per user request
        if not unique_ids:
            logger.info("No Live API competition IDs found in Excel (Competition-Live column may not have ID format)")
        
        return unique_ids
        
    except Exception as e:
        logger.error(f"Error getting Live API competition IDs from Excel: {str(e)}")
        return []


def get_competitions_with_zero_zero_exception(excel_path: str) -> Set[str]:
    """
    Read Excel to identify competitions with 0-0 exception
    Supports both old format (Competition column) and new format (Competition-Live column)
    
    Args:
        excel_path: Path to Excel file
    
    Returns:
        Set of competition names that have 0-0 exception (Result = "0-0")
    """
    try:
        df = pd.read_excel(excel_path)
        
        # Check if 'Result' column exists
        if 'Result' not in df.columns:
            logger.warning("Column 'Result' not found in Excel file, no 0-0 exception competitions")
            return set()
        
        # Filter rows where Result = "0-0" (case-insensitive, handle whitespace)
        zero_zero_rows = df[
            df['Result'].astype(str).str.strip().str.lower() == '0-0'
        ]
        
        # Get unique competition names (prefer Competition-Live, fallback to Competition)
        if 'Competition-Live' in df.columns:
            competitions = zero_zero_rows['Competition-Live'].dropna().unique().tolist()
        elif 'Competition' in df.columns:
            competitions = zero_zero_rows['Competition'].dropna().unique().tolist()
        else:
            logger.warning("Neither 'Competition-Live' nor 'Competition' column found")
            return set()
        
        # Logging moved to main.py setup checklist
        if competitions:
            logger.debug(f"0-0 exception competitions: {', '.join(competitions[:10])}{'...' if len(competitions) > 10 else ''}")
        
        return set(competitions)
        
    except Exception as e:
        logger.error(f"Error reading 0-0 exception from Excel: {str(e)}")
        return set()

