# Competition Matching Logic

This document explains how the bot matches competitions between the Live Score API, Excel file, and Betfair API.

## Overview

The bot needs to match competitions from three different sources:
1. **Live Score API**: Provides live match data with competition information
2. **Excel File** (`Competitions_Results_Odds_Stake.xlsx`): Contains stake percentages and target results
3. **Betfair API**: Provides market data for betting

To ensure accurate matching, especially when competitions have similar names across different countries (e.g., "Serie A" in Italy vs Brazil), the bot uses a combination of **Competition ID** and **Competition Name** in the format `"ID_Name"`.

---

## Competition Format

### Live Score API Format

The bot parses competition data from Live Score API and creates a unique identifier:

- **If both ID and name are available**: `"ID_Name"` (e.g., `"4_Serie A"`, `"24_Serie A"`)
- **If only name is available**: Just the name (e.g., `"Serie A"`, `"Premier League"`)

**Example:**
```json
{
  "competition": {
    "id": 4,
    "name": "Serie A",
    "country": "Italy"
  }
}
```
→ Parsed as: `"4_Serie A"`

### Excel File Format

The Excel file supports two formats:

1. **New Format** (Recommended):
   - `Competition-Live`: Competition identifier from Live Score API (e.g., `"4_Serie A"` or `"Serie A"`)
   - `Competition-Betfair`: Competition identifier for Betfair API (e.g., `"81_Italian Serie A"`)

2. **Legacy Format**:
   - `Competition`: Competition name (e.g., `"Serie A"`)

---

## Matching Logic

### 1. Matching Live Score API → Excel (for Stake Calculation)

When a live match is detected, the bot needs to find the corresponding row in Excel to get the stake percentage.

**Input:** Competition name from Live Score API (e.g., `"24_Serie A"` or `"Argentina-Primera Division"`)

**Process:**

1. **Extract ID and Name** (if in `"ID_Name"` format):
   - `competition_id = "24"`
   - `competition_name_only = "Serie A"`

2. **Try matching with `Competition-Live` column** (if available):
   - **Exact match**: `"24_Serie A" == "24_Serie A"` ✅
   - **Normalized match**: Normalize both strings and compare ✅
   - **ID_Name format match**: If Excel has `"ID_Name"`, extract name part and compare ✅
   - **Name-only match**: If competition has ID but Excel has only name, compare name parts ✅

3. **Fallback to `Competition` column** (legacy format):
   - Exact match or normalized match

**Examples:**

| Live Score API | Excel Competition-Live | Match Result |
|----------------|----------------------|--------------|
| `"24_Serie A"` | `"24_Serie A"` | ✅ **Match** (exact) |
| `"24_Serie A"` | `"Serie A"` | ✅ **Match** (name part) |
| `"24_Serie A"` | `"4_Serie A"` | ✅ **Match** (name part, different ID) |
| `"Argentina-Primera Division"` | `"Argentina-Primera Division"` | ✅ **Match** (exact) |
| `"Argentina-Primera Division"` | `"123_Argentina-Primera Division"` | ✅ **Match** (extract name from Excel) |
| `"Argentina-Primera Division"` | `"24_Serie A"` | ❌ **No Match** (different names) |

**Code Location:** `src/logic/bet_executor.py` → `get_stake_from_excel()`

---

### 2. Matching Excel → Betfair API (for Market Discovery)

At startup, the bot reads competitions from Excel and maps them to Betfair competition IDs to know which markets to monitor.

**Process:**

1. **Direct Mapping** (if `Competition-Betfair` column exists):
   - Read all non-empty `Competition-Betfair` values from Excel
   - Match each value with Betfair API competitions
   - Support both `"ID_Name"` format and plain name format
   - Return list of Betfair competition IDs

2. **Similarity Matching** (fallback, if no `Competition-Betfair`):
   - Read from `Competition` column
   - Use fuzzy matching to find similar competition names in Betfair API
   - Less accurate, may have false positives

**Examples:**

| Excel Competition-Betfair | Betfair API | Match Result |
|---------------------------|-------------|--------------|
| `"81_Italian Serie A"` | `"Italian Serie A"` (ID: 81) | ✅ **Match** (ID_Name format) |
| `"81_Italian Serie A"` | `"Italian Serie A"` (ID: 81) | ✅ **Match** (name part) |
| `"Italian Serie A"` | `"Italian Serie A"` (ID: 81) | ✅ **Match** (plain name) |

**Code Location:** `src/config/competition_mapper.py` → `map_competitions_direct_from_excel()`

---

## Why Use ID_Name Format?

### Problem: Ambiguous Competition Names

Some competition names appear in multiple countries:
- **"Serie A"**: Exists in both Italy (ID: 4) and Brazil (ID: 24)
- **"Premier League"**: Could refer to different countries
- **"La Liga"**: Spain has "LaLiga Santander"

### Solution: Unique Identifier

By combining ID and name (`"ID_Name"`), we create a unique identifier:
- `"4_Serie A"` → Italy Serie A (unambiguous)
- `"24_Serie A"` → Brazil Serie A (unambiguous)
- `"81_Italian Serie A"` → Betfair Italian Serie A (unambiguous)

This ensures accurate matching even when competition names are similar.

---

## Matching Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Live Score API                           │
│  Match detected: "24_Serie A" (Brazil)                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Parse Competition Name                         │
│  competition_id = "24"                                       │
│  competition_name_only = "Serie A"                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         Match with Excel (Competition-Live)                  │
│  1. Try exact match: "24_Serie A"                            │
│  2. Try normalized match                                     │
│  3. Try name part match: "Serie A"                          │
│  4. If Excel has ID_Name, extract name and match             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Found Match in Excel                            │
│  Get stake percentage for current score                      │
│  Calculate stake amount from Betfair balance                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration in Excel

### Recommended Setup

For best accuracy, use both `Competition-Live` and `Competition-Betfair` columns:

| Competition-Live | Competition-Betfair | Result | Stake % |
|-----------------|-------------------|--------|---------|
| `4_Serie A` | `81_Italian Serie A` | 0-0 | 5.0 |
| `4_Serie A` | `81_Italian Serie A` | 1-1 | 3.5 |
| `24_Serie A` | `13_Brazilian Serie A` | 0-0 | 4.0 |
| `2_Premier League` | `10932509_English Premier League` | 1-1 | 6.0 |

### Legacy Setup (Still Supported)

If you only have the `Competition` column, the bot will still work but matching may be less accurate:

| Competition | Result | Stake % |
|------------|--------|---------|
| `Serie A` | 0-0 | 5.0 |
| `Premier League` | 1-1 | 6.0 |

**Note:** With legacy format, if there are multiple "Serie A" competitions (Italy and Brazil), the bot may match incorrectly.

---

## Troubleshooting

### Issue: "No competition match found"

**Possible causes:**
1. Competition name from Live Score API doesn't exist in Excel
2. Format mismatch (e.g., Excel has `"4_Serie A"` but Live Score returns `"Serie A"`)
3. Typo or spelling difference

**Solution:**
- Check the log file for the exact competition name from Live Score API
- Verify the name exists in Excel's `Competition-Live` or `Competition` column
- Ensure format matches (ID_Name vs plain name)

### Issue: "Multiple matches found"

**Possible causes:**
- Excel has duplicate rows with the same competition and score
- Ambiguous competition name (e.g., "Serie A" without ID)

**Solution:**
- Use `Competition-Live` with ID_Name format to ensure uniqueness
- Remove duplicate rows from Excel

### Issue: Bot not monitoring certain competitions

**Possible causes:**
- Competition doesn't have `Competition-Betfair` value in Excel
- Direct mapping only includes competitions with `Competition-Betfair`

**Solution:**
- Add `Competition-Betfair` value for competitions you want to monitor
- Or remove `Competition-Betfair` column to use similarity matching for all competitions

---

## Code References

- **Stake calculation matching**: `src/logic/bet_executor.py` → `get_stake_from_excel()`
- **Early discard matching**: `src/logic/qualification.py` → `get_excel_targets_for_competition()`
- **Betfair mapping**: `src/config/competition_mapper.py` → `map_competitions_direct_from_excel()`
- **Competition parsing**: `src/football_api/parser.py` → `parse_match_competition()`
- **Text normalization**: `src/config/competition_mapper.py` → `normalize_text()`

---

## Summary

1. **Live Score API** provides competitions in `"ID_Name"` format when available
2. **Excel file** can store competitions in `Competition-Live` (for matching with Live Score) and `Competition-Betfair` (for matching with Betfair)
3. **Matching logic** is flexible and supports:
   - Exact matches
   - ID_Name format matches
   - Name-only matches
   - Normalized text matching
4. **ID_Name format** prevents ambiguity when competition names are similar across different countries
5. **Fallback mechanisms** ensure backward compatibility with legacy Excel formats

For best results, always use `Competition-Live` and `Competition-Betfair` columns with ID_Name format.

