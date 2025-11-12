"""
Test script to debug competition matching between Excel and Betfair API
"""
import sys
import os
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config.loader import load_config
from auth.cert_login import BetfairAuthenticator
from betfair.market_service import MarketService
from config.competition_mapper import read_competitions_from_excel
import pandas as pd
from pathlib import Path

def main():
    print("=" * 60)
    print("Competition Matching Debug Test")
    print("=" * 60)
    
    # Load config
    print("\n[1] Loading configuration...")
    config = load_config()
    betfair_config = config["betfair"]
    
    # Read Excel competitions
    print("\n[2] Reading Excel file...")
    project_root = Path(__file__).parent
    excel_path = project_root / "competitions" / "Competitions_Results_Odds_Stake.xlsx"
    
    if not excel_path.exists():
        print(f"ERROR: Excel file not found at {excel_path}")
        return
    
    excel_competitions = read_competitions_from_excel(str(excel_path))
    print(f"Found {len(excel_competitions)} unique competitions in Excel")
    print("\nSample Excel competitions (first 10):")
    for i, comp in enumerate(sorted(excel_competitions)[:10], 1):
        print(f"  {i}. {comp}")
    
    # Login to Betfair
    print("\n[3] Logging in to Betfair...")
    authenticator = BetfairAuthenticator(
        app_key=betfair_config["app_key"],
        username=betfair_config["username"],
        password=os.getenv("BETFAIR_PASSWORD"),
        cert_path=betfair_config["certificate_path"],
        key_path=betfair_config["key_path"],
        login_endpoint=betfair_config["login_endpoint"]
    )
    
    success, error = authenticator.login()
    if not success:
        print(f"ERROR: Login failed: {error}")
        return
    
    session_token = authenticator.get_session_token()
    print("✓ Login successful")
    
    # Get Betfair competitions
    print("\n[4] Fetching competitions from Betfair API...")
    market_service = MarketService(
        app_key=betfair_config["app_key"],
        session_token=session_token,
        api_endpoint=betfair_config["api_endpoint"]
    )
    
    betfair_competitions = market_service.list_competitions([1])
    print(f"Found {len(betfair_competitions)} competitions from Betfair")
    
    # Extract competition names
    betfair_names = []
    for comp in betfair_competitions:
        comp_info = comp.get("competition", {})
        comp_name = comp_info.get("name", "")
        comp_id = comp_info.get("id")
        if comp_name and comp_id:
            betfair_names.append((comp_id, comp_name))
    
    print("\nSample Betfair competitions (first 20):")
    for i, (comp_id, comp_name) in enumerate(betfair_names[:20], 1):
        print(f"  {i}. [{comp_id}] {comp_name}")
    
    # Country name mapping (Excel format -> Betfair format)
    country_mapping = {
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
    league_normalization = {
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
    
    def normalize_text(text):
        """Normalize text: lowercase, remove special chars, remove extra spaces, normalize numbers"""
        if not text:
            return ""
        # Lowercase
        text = text.lower().strip()
        # Remove special characters (keep only letters, numbers, spaces)
        # Loại bỏ: - * . , ( ) [ ] { } / \ | _ = + ~ ` ! @ # $ % ^ & * ( ) [ ] { } | \ : ; " ' < > ? ,
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
    
    def normalize_excel_competition(excel_name):
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
            country_normalized = country_mapping.get(country, country)
        else:
            country_normalized = None
        
        # Normalize league name
        league_normalized = league_normalization.get(league, league)
        
        # Create normalized full name for comparison
        if country_normalized and league_normalized:
            normalized_full = normalize_text(f"{country_normalized} {league_normalized}")
        elif league_normalized:
            normalized_full = normalize_text(league_normalized)
        else:
            normalized_full = normalize_text(excel_lower)
        
        return country_normalized, league_normalized, excel_lower, normalized_full
    
    def normalize_betfair_competition(betfair_name):
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
    
    # Try to match - DÙNG SIMILARITY ĐỂ MATCH CHÍNH XÁC HƠN
    print("\n[5] Attempting matches with similarity-based logic (>=80% similarity)...")
    print("-" * 60)
    
    matches_found = 0
    correct_matches = []
    
    def calculate_similarity(str1, str2):
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
    
    for excel_name in sorted(excel_competitions):
        excel_country, excel_league, excel_lower, excel_normalized = normalize_excel_competition(excel_name)
        matched = False
        best_match = None
        best_similarity = 0.0
        
        for comp_id, betfair_name in betfair_names:
            betfair_country, betfair_league, betfair_lower, betfair_normalized = normalize_betfair_competition(betfair_name)
            
            # Calculate similarity between normalized names
            similarity = calculate_similarity(excel_normalized, betfair_normalized)
            
            # Only match if similarity is high (>= 0.8 means 80% of words match)
            if similarity >= 0.8:
                if similarity > best_similarity:
                    best_similarity = similarity
                    match_type = "EXACT" if similarity >= 0.95 else "HIGH_SIMILARITY"
                    best_match = (comp_id, betfair_name, match_type, similarity)
                    matched = True
        
        if matched and best_match:
            comp_id, betfair_name, match_type, similarity = best_match
            similarity_pct = int(similarity * 100)
            print(f"✓ MATCH ({match_type}, {similarity_pct}%): '{excel_name}' -> '{betfair_name}' (ID: {comp_id})")
            matches_found += 1
            correct_matches.append((excel_name, betfair_name, comp_id, match_type))
        else:
            print(f"✗ NO MATCH: '{excel_name}'")
    
    print("-" * 60)
    print(f"\nTotal matches found: {matches_found} / {len(excel_competitions)}")
    exact_count = sum(1 for m in correct_matches if m[3] == "EXACT")
    high_sim_count = sum(1 for m in correct_matches if m[3] == "HIGH_SIMILARITY")
    print(f"  - Exact matches (>=95%): {exact_count}")
    print(f"  - High similarity matches (>=80%): {high_sim_count}")
    
    if correct_matches:
        print("\n✓ Correct matches:")
        for match in correct_matches:
            excel_name, betfair_name, comp_id = match[0], match[1], match[2]
            print(f"  - {excel_name} -> {betfair_name} (ID: {comp_id})")
    
    # Show some examples of format differences
    print("\n[6] Format Analysis:")
    print("\nExcel format examples:")
    for comp in sorted(excel_competitions)[:5]:
        print(f"  - {comp}")
    
    print("\nBetfair format examples:")
    for comp_id, comp_name in betfair_names[:5]:
        print(f"  - {comp_name}")

if __name__ == "__main__":
    main()

