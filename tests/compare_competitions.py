"""
Script to compare competitions from Live Score API and Betfair API
Finds competitions with similar names that might be the same
"""
import sys
from pathlib import Path
import json
import re
from difflib import SequenceMatcher

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config.competition_mapper import normalize_text


def normalize_competition_name(name: str) -> str:
    """
    Normalize competition name for comparison
    - Remove extra spaces
    - Convert to lowercase
    - Remove special characters
    """
    if not name:
        return ""
    
    # Normalize using the same function as competition_mapper
    normalized = normalize_text(name)
    
    # Additional normalization for comparison
    normalized = normalized.lower().strip()
    
    # Remove common prefixes/suffixes that might differ
    normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces to single
    
    return normalized


def similarity_score(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two names (0.0 to 1.0)
    """
    return SequenceMatcher(None, name1, name2).ratio()


def load_live_score_competitions(file_path: Path) -> list:
    """Load competitions from Live Score API JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    competitions = []
    
    # Handle different response structures
    if "data" in data and "competition" in data["data"]:
        comps = data["data"]["competition"]
    elif "competition" in data:
        comps = data["competition"]
    elif isinstance(data, list):
        comps = data
    else:
        print(f"⚠ Unexpected Live Score API structure")
        return []
    
    for comp in comps:
        comp_id = comp.get("id", "N/A")
        comp_name = comp.get("name", "N/A")
        
        # Get country
        countries = comp.get("countries", [])
        if countries and isinstance(countries, list) and len(countries) > 0:
            country = countries[0].get("name", "N/A") if isinstance(countries[0], dict) else str(countries[0])
        else:
            country = comp.get("country", "N/A")
        
        competitions.append({
            "id": str(comp_id),
            "name": comp_name,
            "country": country,
            "normalized_name": normalize_competition_name(comp_name),
            "source": "Live Score API"
        })
    
    return competitions


def load_betfair_competitions(file_path: Path) -> list:
    """Load competitions from Betfair API JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    competitions = []
    
    # Betfair returns a list of competition objects
    if isinstance(data, list):
        comps = data
    else:
        print(f"⚠ Unexpected Betfair API structure")
        return []
    
    for comp in comps:
        comp_info = comp.get("competition", {})
        if isinstance(comp_info, dict):
            comp_id = comp_info.get("id", "N/A")
            comp_name = comp_info.get("name", "N/A")
            region = comp_info.get("region", "N/A")
        else:
            comp_id = comp.get("id", "N/A")
            comp_name = comp.get("name", "N/A")
            region = comp.get("region", "N/A")
        
        competitions.append({
            "id": str(comp_id),
            "name": comp_name,
            "country": region,
            "normalized_name": normalize_competition_name(comp_name),
            "source": "Betfair API"
        })
    
    return competitions


def find_matching_competitions(live_score_comps: list, betfair_comps: list, 
                                min_similarity: float = 0.8) -> list:
    """
    Find competitions with similar names between two lists
    
    Args:
        live_score_comps: List of Live Score competitions
        betfair_comps: List of Betfair competitions
        min_similarity: Minimum similarity score (0.0 to 1.0) to consider a match
    
    Returns:
        List of matches with similarity scores
    """
    matches = []
    
    for ls_comp in live_score_comps:
        ls_name = ls_comp["normalized_name"]
        ls_original = ls_comp["name"]
        
        for bf_comp in betfair_comps:
            bf_name = bf_comp["normalized_name"]
            bf_original = bf_comp["name"]
            
            # Calculate similarity
            similarity = similarity_score(ls_name, bf_name)
            
            # Also check exact match after normalization
            exact_match = (ls_name == bf_name)
            
            if exact_match or similarity >= min_similarity:
                matches.append({
                    "live_score": {
                        "id": ls_comp["id"],
                        "name": ls_original,
                        "country": ls_comp["country"]
                    },
                    "betfair": {
                        "id": bf_comp["id"],
                        "name": bf_original,
                        "country": bf_comp["country"]
                    },
                    "similarity": 1.0 if exact_match else similarity,
                    "exact_match": exact_match
                })
    
    # Sort by similarity (highest first)
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    
    return matches


def main():
    """Main function to compare competitions"""
    print("=" * 80)
    print("Comparing Competitions: Live Score API vs Betfair API")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent
    
    # Load competitions
    print("\n[1/3] Loading Live Score API competitions...")
    live_score_file = project_root / "competitions" / "live_score_competitions.json"
    if not live_score_file.exists():
        print(f"❌ File not found: {live_score_file}")
        return 1
    
    live_score_comps = load_live_score_competitions(live_score_file)
    print(f"✓ Loaded {len(live_score_comps)} competitions from Live Score API")
    
    print("\n[2/3] Loading Betfair API competitions...")
    betfair_file = project_root / "competitions" / "betfair_competitions.json"
    if not betfair_file.exists():
        print(f"❌ File not found: {betfair_file}")
        return 1
    
    betfair_comps = load_betfair_competitions(betfair_file)
    print(f"✓ Loaded {len(betfair_comps)} competitions from Betfair API")
    
    # Find matches
    print("\n[3/3] Finding matching competitions...")
    matches = find_matching_competitions(live_score_comps, betfair_comps, min_similarity=0.7)
    
    # Display results
    print("\n" + "=" * 80)
    print("MATCHING COMPETITIONS")
    print("=" * 80)
    
    if not matches:
        print("\n⚠ No matching competitions found (similarity >= 0.7)")
        return 0
    
    # Separate exact matches and similar matches
    exact_matches = [m for m in matches if m["exact_match"]]
    similar_matches = [m for m in matches if not m["exact_match"]]
    
    print(f"\n✅ Exact Matches: {len(exact_matches)}")
    print(f"🔍 Similar Matches (similarity >= 0.7): {len(similar_matches)}")
    print(f"📊 Total Matches: {len(matches)}")
    
    # Display exact matches
    if exact_matches:
        print("\n" + "-" * 80)
        print("EXACT MATCHES (100% similarity)")
        print("-" * 80)
        for idx, match in enumerate(exact_matches, 1):
            ls = match["live_score"]
            bf = match["betfair"]
            print(f"\n{idx}. {ls['name']}")
            print(f"   Live Score: ID={ls['id']}, Country={ls['country']}")
            print(f"   Betfair:    ID={bf['id']}, Country={bf['country']}")
    
    # Display similar matches (top 20)
    if similar_matches:
        print("\n" + "-" * 80)
        print(f"SIMILAR MATCHES (Top 20, similarity >= 0.7)")
        print("-" * 80)
        for idx, match in enumerate(similar_matches[:20], 1):
            ls = match["live_score"]
            bf = match["betfair"]
            similarity = match["similarity"]
            print(f"\n{idx}. Similarity: {similarity:.1%}")
            print(f"   Live Score: {ls['name']} (ID={ls['id']}, Country={ls['country']})")
            print(f"   Betfair:    {bf['name']} (ID={bf['id']}, Country={bf['country']})")
    
    # Save results to file
    output_file = project_root / "competitions" / "competition_matches.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "exact_matches": exact_matches,
            "similar_matches": similar_matches,
            "total_matches": len(matches),
            "live_score_total": len(live_score_comps),
            "betfair_total": len(betfair_comps)
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Summary by country
    print("\n" + "-" * 80)
    print("SUMMARY BY COUNTRY (Exact Matches Only)")
    print("-" * 80)
    country_matches = {}
    for match in exact_matches:
        country = match["live_score"]["country"]
        country_matches[country] = country_matches.get(country, 0) + 1
    
    for country, count in sorted(country_matches.items(), key=lambda x: x[1], reverse=True):
        print(f"  {country}: {count} matches")
    
    print("\n" + "=" * 80)
    print("✅ Comparison completed!")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nComparison interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Comparison failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

