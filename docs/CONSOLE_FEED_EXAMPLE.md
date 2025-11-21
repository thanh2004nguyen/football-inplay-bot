# Bot Console Feed Example

## Example Console Output Structure

### 1. Startup & Initialization
```
┌───────────────────────────────────────────────────────────────────────────────┐
│                                Setup Checklist                                 │
├───────────────────────────────────────────────────────────────────────────────┤
│  ✓ Email notifications: user@example.com → recipient@example.com              │
│  ✓ Login (Password): Success - Account balance: 300.25                       │
│  ✓ Bet tracker: Initialized (bankroll: 300.25)                               │
│  ✓ Excel writer: Bet_Records.xlsx                                            │
│  ✓ Reading competitions from Excel: Competitions_Results_Odds_Stake.xlsx     │
│  ✓ Mapped competitions (4 total):                                           │
│      • Live: [2] Premier League | Betfair: [10932509] English Premier League │
│      • Live: [4] Serie A | Betfair: [81] Italian Serie A                     │
└───────────────────────────────────────────────────────────────────────────────┘

Setup completed, starting bot...
Monitoring phase started – tracking live matches...
```

---

### 2. Each Iteration (Every 10 seconds)

#### 2.1. Betfair Live Matches
```
[1] Betfair: 4 live match(es) available
  [1] Gremio v Vasco da Gama (Brazilian Serie A) - 15 market(s)
  [2] SE Palmeiras v EC Vitoria Salvador (Brazilian Serie A) - 15 market(s)
  [3] Botafogo FR v Sport Recife (Brazilian Serie A) - 2 market(s)
  [4] Santos v Mirassol (Brazilian Serie A) - 1 market(s)
```

**Important Note - Live Match Verification:**
- Bot uses **MarketBook API** to verify that matches are actually live (not just marked as inPlay in MarketCatalogue)
- Only matches with `status = "OPEN"` AND `inPlay = true` are considered truly live
- This prevents false positives where MarketCatalogue shows `inPlay = true` but market is actually SUSPENDED or CLOSED
- **Both Betfair and Live API matches are filtered by Excel competitions before processing**
- **Flow:** 
  - **Betfair:** MarketCatalogue (filter by Excel competition IDs) → MarketBook verification (status=OPEN + inPlay=true) → Only verified live matches are processed
  - **Live API:** Get live matches (filter by Excel competition IDs via API parameter) → Additional filter by competition ID in code (fallback) → Only matches from Excel competitions are processed

#### 2.2. Live API Matches (Every 60 seconds, or 10s in intensive mode)
```
Live API: 4 live match(es) available  # Already filtered by competitions in Excel
  [1] Gremio v Vasco da Gama (Brazilian Serie A) - 2-1 @ 67' [LIVE]
  [2] SE Palmeiras v EC Vitoria Salvador (Brazilian Serie A) - 0-0 @ 38' [LIVE]
  [3] Botafogo FR v Sport Recife (Brazilian Serie A) - 1-0 @ 52' [LIVE]
  [4] Santos v Mirassol (Brazilian Serie A) - 0-1 @ 45' [LIVE]
```

**Note:**
- Live API matches are filtered by competition IDs from Excel (column `Competition-Live`)
- Only shows matches from competitions in Excel file
- Polling interval automatically switches 60s ↔ 10s based on number of matches in 60'-76' (if `dynamic_polling_enabled = true`)

#### 2.3. New Matches Started Tracking
```
📊 Tracking List

1. Gremio v Vasco da Gama (min 67, score 2-1) [1-1, 2-1, 2-2]
2. Botafogo FR v Sport Recife (min 52, score 1-0) [0-0, 1-0, 1-1]

Matched: 2/4 event(s) matched and started tracking
```

#### 2.4. Skipped Matches (Too Late)
```
  ⏭️  Skipping: minute 75 > 74 - Premier League - Arsenal v Chelsea (2-1) [1-1, 2-1, 2-2] LIVE
```

#### 2.5. Matching Refresh (Every 60 minutes)
```
[120] 🔄 Refreshing Betfair ↔ LiveScore matching (every 60 minutes)...
🔄 Match cache cleared for refresh
🔄 Competition mapping refreshed: 4 competition(s) (no change)

[120] Betfair: 5 live match(es) available (refresh)
  [1] Gremio v Vasco da Gama (Brazilian Serie A) - 15 market(s)
  [2] SE Palmeiras v EC Vitoria Salvador (Brazilian Serie A) - 15 market(s)
  [3] Botafogo FR v Sport Recife (Brazilian Serie A) - 2 market(s)
  [4] Santos v Mirassol (Brazilian Serie A) - 1 market(s)
  [5] Flamengo v Corinthians (Brazilian Serie A) - 12 market(s)

Live API: 5 live match(es) available (refresh)
  [1] Gremio v Vasco da Gama (Brazilian Serie A) - 2-1 @ 67' [LIVE]
  [2] SE Palmeiras v EC Vitoria Salvador (Brazilian Serie A) - 0-0 @ 60' [LIVE]
  [3] Botafogo FR v Sport Recife (Brazilian Serie A) - 1-0 @ 65' [LIVE]
  [4] Santos v Mirassol (Brazilian Serie A) - 0-1 @ 45' [LIVE]
  [5] Flamengo v Corinthians (Brazilian Serie A) - 0-0 @ 55' [LIVE]

🆕 New matches detected during refresh:
  - Flamengo v Corinthians (min 55, score 0-0)
```

**Note:**
- Matching between Betfair events and LiveScore API matches is automatically refreshed every 60 minutes
- Match cache is cleared during refresh to allow re-matching of new events
- New Betfair events that appear after bot startup can now be matched with LiveScore matches that may have become available
- Competition mapping from Excel is also refreshed during this process

---

### 3. Tracking Table (Updated Every Iteration)

#### 3.1. When Matches Are Being Tracked (60-74 minutes)
```
[1] Tracking 3 match(es) from minute 60-74:

============================================================================================================
Match | Min | Score | Targets | State
------------------------------------------------------------------------------------------------------------
Gremio v Vasco da Gama | 67' | 🟢 2-1 | 1-1, 2-1, 2-2 | TARGET (TRACKING)
Botafogo FR v Sport Recife | 65' | 1-0 | 0-0, 1-0, 1-1 | TRACKING
SE Palmeiras v EC Vitoria Salvador | 60' | 🟢 0-0 | 0-0, 0-1, 1-0 | TARGET (TRACKING)
============================================================================================================

🎯 0 match(es) ready for bet placement
```

**Note:** 
- **Gremio v Vasco da Gama** has green dot (🟢) because score 2-1 was reached by a goal scored between 60-74 minutes
- **SE Palmeiras** has green dot (🟢) because it's minute 60 with score 0-0, and 0-0 is in the target list (special case)
- **Botafogo FR** has NO green dot because score 1-0 was already present before minute 60 and no goal was scored in 60-74 window yet

#### 3.2. State Changes (Real-time Events)
```
Match QUALIFIED: Gremio v Vasco da Gama - Goal in 60-74 window (minute 68, team: Gremio)
  ✓ QUALIFIED: Gremio v Vasco da Gama - Goal in 60-74 window (minute 68, team: Gremio)

Match READY FOR BET: Gremio v Vasco da Gama
  🎯 READY FOR BET: Gremio v Vasco da Gama
```

#### 3.3. Discarded Matches (No Goal in 60-74)
```
✘ Match Botafogo FR v Sport Recife: Disqualified (no goal in 60-74, no 0-0 exception)
```

**Note:** 
- **Important**: The message "Disqualified (no goal in 60-74, no 0-0 exception)" appears **only when 0-0 is NOT in the target list**
- For matches where 0-0 **IS** in the target list (like Palmeiras with targets [0-0, 0-1, 1-0]):
  - If the match is 0-0 at minute 60, it will be qualified immediately and stay TARGET (TRACKING)
  - Match stays TARGET even if no goal is scored between 60-74
  - At minute 75, if still 0-0 and all other conditions are OK, it becomes TARGET (READY_FOR_BET)
  - This match will **NOT** show the "no 0-0 exception" message because 0-0 is in the target list

#### 3.4. Updated Tracking Table After Events
```
[2] Tracking 2 match(es) from minute 60-74:

============================================================================================================
Match | Min | Score | Targets | State
------------------------------------------------------------------------------------------------------------
Gremio v Vasco da Gama | 75' | 🟢 2-1 | 1-1, 2-1, 2-2 | TARGET (READY_FOR_BET)
Botafogo FR v Sport Recife | 68' | 1-0 | 0-0, 1-0, 1-1 | TRACKING
============================================================================================================

🎯 1 match(es) ready for bet placement
```

**Note:** The summary "🎯 1 match(es) ready for bet placement" only includes matches that:
- Are still TARGET at minute 75
- Current score is still in target list
- Under X.5 price ≥ reference odds (from Excel)
- Spread ≤ 4 ticks
- Excel config exists for that competition and score

#### 3.5. Match Loses TARGET Status (Goal After 60-74 Changes Score)
```
[2] Tracking 2 match(es) from minute 60-74:

============================================================================================================
Match | Min | Score | Targets | State
------------------------------------------------------------------------------------------------------------
Gremio v Vasco da Gama | 76' | 3-1 | 1-1, 2-1, 2-2 | TRACKING
Botafogo FR v Sport Recife | 70' | 1-0 | 0-0, 1-0, 1-1 | TRACKING
============================================================================================================

🎯 0 match(es) ready for bet placement
```

**Note:** Gremio lost TARGET status because a goal after minute 74 changed the score from 2-1 (in targets) to 3-1 (not in targets).

#### 3.6. Skipped/Expired Matches Section (After Minute 75)
```
[SKIPPED] Gremio v Vasco da Gama – Reason: spread > 4 ticks
[SKIPPED] Palmeiras v EC Vitoria – Reason: Under price below reference odds
[SKIPPED] Botafogo FR v Sport Recife – Reason: Current score not in target list at 75'
[SKIPPED] Santos v Mirassol – Reason: No Excel config for this score
[EXPIRED] Flamengo v Corinthians – Reason: Conditions never all true during minute 75
```

**Note:**
- **Skipped matches**: Conditions were checked during minute 75 but one or more conditions failed
- **Expired matches**: All conditions were never simultaneously true during the entire 75th minute (75:00 to 75:59)
- Once minute 75 has passed (minute > 75), no bet will be placed for that match

---

### 4. Bet Placement

#### 4.1. Bet Placed Successfully (During Minute 75)
```
Attempting to place lay bet for Gremio v Vasco da Gama (minute 75, score: 2-1)

[BET PLACED]
Match: Gremio v Vasco da Gama
Competition: Brazil Serie A
Minute: 75'
Score: 2-1
Market: Over 2.5 (LAY)
Lay price: 3.20 (best lay + 2 ticks)
Liability: 15.00 (5% of bankroll)
Lay stake: 6.82
Spread: 3 ticks
Condition: Under back 1.80 >= reference 1.75 → OK
BetId: 123456789

Bet placed successfully: BetId=123456789, Stake=6.82, Liability=15.00
Bet matched immediately: BetId=123456789, SizeMatched=6.82
```

**Note:** The entry window is the **entire 75th minute (75:00 to 75:59)**. The bot:
1. Checks conditions continuously throughout minute 75
2. Places bet **as soon as all conditions are satisfied simultaneously** during minute 75
3. Re-checks that current score (2-1) is still in target list
4. Reads from Excel: stake % (5%) and reference odds (1.75) for this competition and score
5. Checks Under X.5 best back (1.80) ≥ reference odds (1.75) → OK
6. Checks Over X.5 spread (3 ticks) ≤ 4 ticks → OK
7. Calculates liability: Bankroll (300.00) × 5% = 15.00
8. Calculates lay stake: 15.00 / (3.20 - 1) = 6.82
9. Places LAY bet on Over 2.5 at best lay (3.10) + 2 ticks = 3.20
10. **Never places bet after minute 75 has passed** (i.e., nothing at 76', 77', etc.)

#### 4.2. Updated Table After Bet
```
[3] Tracking 1 match(es) from minute 60-74:

============================================================================================================
Match | Min | Score | Targets | State
------------------------------------------------------------------------------------------------------------
Botafogo FR v Sport Recife | 70' | 1-0 | 0-0, 1-0, 1-1 | TRACKING
============================================================================================================

🎯 0 match(es) ready for bet placement
```

---

### 5. Waiting for Matches to Reach 60 Minutes

```
Tracking: 2 match(es) (waiting for minute 60-74), 0 ready for bet
```

---

### 6. No Matches Available

```
[5] Betfair: 0 live match(es) available
Live API: No live matches available
Matched: 0 Betfair event(s) found, but no Live API matches available
```

---

## Key Features:

1. **Live Match Verification**: 
   - Bot verifies matches using MarketBook API to ensure they are actually live
   - Only matches with `status = "OPEN"` AND `inPlay = true` are processed
   - Prevents false positives from MarketCatalogue (which may show inPlay=true for SUSPENDED/CLOSED markets)
   - Matches are filtered by Excel competitions before verification (if configured)
   - **Why this matters:** MarketCatalogue can return markets with `inPlay = true` but status = SUSPENDED/CLOSED, which are not actually live

2. **Live Matches List**: Shows all available matches from Betfair and Live API
3. **Tracking Table**: Displays matches in 60-74 minute window with:
   - Match name
   - Current minute
   - Current score (🟢 green dot if TARGET - score reached in 60-74 window or 0-0 at 60')
   - Target scores from Excel
   - Current state (TRACKING, TARGET (TRACKING), TARGET (READY_FOR_BET), etc.)
4. **Real-time Updates**: Table updates every 10 seconds (or as configured)
5. **Green Dot (🟢) Logic**:
   - Shows green dot if current score is in target list AND score was reached by a goal between 60-74 minutes
   - Special case: 0-0 at minute 60' gets green dot immediately if 0-0 is in target list
   - NO green dot if score was already present before minute 60 and no goal in 60-74 window
   - Green dot is removed if later goal changes score to something not in target list
6. **Summary of Ready Matches**: 
   - Shows "🎯 X match(es) ready for bet placement"
   - Only includes matches that are:
     - Still TARGET at minute 75
     - Current score still in target list
     - Under X.5 price ≥ reference odds (from Excel)
     - Spread ≤ 4 ticks
     - Excel config exists for that competition and score
7. **Bet Placement**: 
   - Entry window: **entire 75th minute (75:00 to 75:59)**
   - Conditions are checked continuously throughout minute 75
   - Bet is placed **as soon as all conditions are satisfied simultaneously** during minute 75
   - **Never places bet after minute 75 has passed** (i.e., nothing at 76', 77', etc.)
   - If conditions never all true during minute 75 → match is expired
   - Shows detailed [BET PLACED] block with all information
8. **Skipped Matches**: 
   - Logs matches that entered 60-74 tracking but didn't trigger bet at 75'
   - Reasons include: spread > 4 ticks, Under price below reference, score not in targets, no Excel config
9. **Event Logs**: Clear messages for qualification, bet placement, and discards
10. **Automatic Matching Refresh**: 
   - Betfair ↔ LiveScore mapping is automatically refreshed every 60 minutes
   - Match cache is cleared during refresh to allow new events to be matched
   - New Betfair events that appear after bot startup can be matched with LiveScore matches that become available
   - Competition mapping from Excel is also refreshed during this process

---

## Color Coding & Symbols:
- 🟢 **Green dot**: Match is TARGET (score in targets AND reached in 60-74 window, or 0-0 at 60')
- ✓ **Checkmark**: Match qualified (goal in 60-74 or 0-0 exception)
- 🎯 **Target**: Match ready for bet placement (at 75' and meets all conditions)
- ✘ **Cross**: Match discarded (no goal in 60-74, no 0-0 exception)
- ⏭️ **Skip**: Match skipped (too late to start tracking, or conditions not met at 75')

## Important Notes:

1. **Live Match Verification**:
   - Bot uses a two-step verification process:
     - **Step 1:** MarketCatalogue API - Gets markets with `inPlay = true` filtered by Excel competitions
     - **Step 2:** MarketBook API - Verifies actual status (`status = "OPEN"` AND `inPlay = true`)
   - Only matches that pass both steps are considered truly live
   - This ensures bot only processes matches that are actually being played right now
   - **Why MarketCatalogue alone is not enough:**
     - MarketCatalogue may return `inPlay = true` for markets that are SUSPENDED, CLOSED, or scheduled
     - MarketBook provides the actual current status of the market
     - Example: A match may show `inPlay = true` in MarketCatalogue but `status = "SUSPENDED"` in MarketBook → Not actually live!

2. **Green Dot Rules**:
   - Green dot appears ONLY if score was reached by a goal between 60-74 minutes
   - Exception: 0-0 at minute 60' gets green dot immediately if 0-0 is in target list
   - If score was already present before 60' and no goal in 60-74 → NO green dot
   - If match has green dot but later goal changes score → green dot is removed

3. **Bet Trigger (Entry Window)**:
   - Entry window: **entire 75th minute (75:00 to 75:59)**
   - Conditions are checked continuously throughout minute 75
   - Bet is placed **as soon as all conditions are satisfied simultaneously** during minute 75
   - All conditions must be true at the same time: score in targets, Under odds OK, spread ≤ 4 ticks, Excel config found, etc.
   - **Never places bet after minute 75 has passed** (minute > 75)
   - If conditions never all true during minute 75 → match is expired (no bet placed)
   - If any condition fails during minute 75 → match is skipped with clear reason

4. **Summary Count**:
   - "🎯 X match(es) ready for bet placement" only counts matches that:
     - Are at minute 75+
     - Still have TARGET status
     - Meet ALL conditions (score, odds, spread, Excel config)

5. **0-0 Exception Logic**:
   - If 0-0 is in the target list and match is 0-0 at minute 60: match is qualified immediately
   - Match stays TARGET (TRACKING) even if no goal is scored between 60-74
   - At minute 75, if still 0-0 and all conditions OK: becomes TARGET (READY_FOR_BET)
   - Message "Disqualified (no goal in 60-74, no 0-0 exception)" appears ONLY when 0-0 is NOT in target list

6. **Matching Refresh**:
   - Betfair ↔ LiveScore mapping refreshes automatically every 60 minutes
   - Match cache is cleared to allow re-matching of new events
   - This ensures new Betfair events that appear after bot startup can be tracked

7. **Bet Placement Entry Window**:
   - Entry window is the **entire 75th minute (75:00 to 75:59)**
   - Bot checks conditions continuously throughout minute 75
   - Bet is placed **once** as soon as all conditions are satisfied simultaneously
   - If conditions never all true during minute 75 → match expires (no bet placed)
   - **Never places bet after minute 75 has passed** (minute > 75)

---

## Issues Fixed (Latest Updates):

### Issue 7: Dynamic Polling & Fast Polling Implementation ✅
**Problem:** Customer requested:
1. Livescore API - dynamic polling (60s ↔ 10s) based on matches in 60'-76'
2. Betfair API - fast polling (1s) for matches at 74'-76' ready to place bet
3. Strict discard at minute 60' - remove matches that cannot return to target results

**Solution:**
- **Livescore API Dynamic Polling:**
  - Default mode: 60s when there are no matches in 60'-76'
  - Intensive mode: 10s when there is at least 1 match in 60'-76' and not discarded
  - Automatically returns to 60s when there are no more valid matches
  - Implemented but disabled by default (can be enabled via config `dynamic_polling_enabled`)
  
- **Betfair API Fast Polling:**
  - Normal mode: normal polling interval (10s)
  - Fast mode: 1s for matches at 74'-76' that are candidates (READY_FOR_BET or QUALIFIED)
  - Automatically returns to normal when bet is placed or match is no longer valid
  
- **Strict Discard at 60':**
  - Remove matches that cannot return to target results
  - Check: match already has score outside targets OR only needs 1 more goal to permanently leave all targets
  - Only keep matches that can reach target with at least 1 more goal
  - **VAR Delay Logic (Updated):** Instead of discarding immediately, wait 3-5 minutes (configurable) before discarding to account for VAR decisions
  - If VAR cancels a goal during delay period, match is no longer impossible → discard candidate is cleared
  - If match becomes qualified (goal scored) during delay → discard candidate is cleared
  - Only discard after delay period if match is still impossible

**Files Modified:**
- `config/config.json`: Added config flags for dynamic polling and fast polling
- `src/main.py`: Implemented dynamic polling logic for Livescore and fast polling for Betfair
- `src/logic/qualification.py`: Added function `is_impossible_match_at_60()` for strict discard
- `src/logic/match_tracker.py`: Integrated strict discard logic

**Config Options:**
```json
{
  "live_score_api": {
    "dynamic_polling_enabled": false,  // Enable when paid plan is available
    "default_polling_interval_seconds": 60,
    "intensive_polling_interval_seconds": 10
  },
  "monitoring": {
    "fast_polling_enabled": true,
    "fast_polling_interval_seconds": 1,
    "fast_polling_window": {"start_minute": 74, "end_minute": 76}
  },
  "match_tracking": {
    "strict_discard_at_60": true,
    "discard_delay_minutes": 4
  }
}
```

---

### Issue 9: VAR Delay for Discard Candidates ✅
**Problem:** Customer requested that matches marked for discard at minute 60' should wait 3-5 minutes before actually being discarded, to account for VAR decisions that might cancel goals and bring the match back into a playable state.

**Solution:**
- **Discard Candidate Tracking:**
  - When match is "impossible" at minute 60', mark as discard candidate instead of discarding immediately
  - Track timestamp when match becomes discard candidate
  - Wait for configurable delay period (default: 4 minutes, range: 3-5 minutes recommended)
  
- **Re-check Logic During Delay:**
  - Re-check if match is still impossible on every update (not just when score changes)
  - If score changes (VAR might have cancelled goal) → re-check if match is still impossible
  - If match becomes qualified (goal scored in 60-74) → clear discard candidate
  - If match is no longer impossible → clear discard candidate
  
- **Discard After Delay:**
  - Only discard match after delay period has passed AND match is still impossible
  - This avoids losing good opportunities when VAR cancels goals

**Files Modified:**
- `config/config.json`: Added `discard_delay_minutes` config (default: 4 minutes)
- `src/logic/match_tracker.py`: 
  - Added discard candidate tracking fields (`discard_candidate_since`, `discard_candidate_reason`, `discard_candidate_score`)
  - Modified `update_state()` to implement delay logic instead of immediate discard
  - Re-check impossible match status on every update during delay period
  - Clear discard candidate when match becomes qualified or no longer impossible
- `src/main.py`: Pass `discard_delay_minutes` from config to MatchTracker

**Config Options:**
```json
{
  "match_tracking": {
    "strict_discard_at_60": true,
    "discard_delay_minutes": 4
  }
}
```

**Result:**
- Matches are not discarded immediately when marked as impossible at minute 60'
- System waits 3-5 minutes (configurable) to account for VAR decisions
- If VAR cancels a goal during delay, match continues tracking
- If match becomes qualified during delay, discard candidate is cleared
- Only matches that remain impossible after delay period are discarded

---

### Issue 8: Live API Competition Filtering ✅
**Problem:** Live API is fetching all live matches, not filtering by competitions in Excel like Betfair.

**Solution:**
- **Extract Live API Competition IDs from Excel:**
  - Read `Competition-Live` column from Excel
  - Extract competition IDs from format `"ID_Name"` (e.g., `"4_Serie A"` → ID is `"4"`)
  - Store in `live_api_competition_ids` in services
  
- **Filter Live API Matches:**
  - Add parameter `competition_ids` to `get_live_matches()`
  - Send `competition_id` parameter to Live API (according to API documentation)
  - Fallback filter: if API doesn't filter correctly, filter again by competition ID in code
  
- **Automatically load on startup:**
  - Load Live API competition IDs from Excel in `setup_utils.py`
  - Pass to `get_live_matches()` every time API is called

**Files Modified:**
- `src/config/competition_mapper.py`: Added function `get_live_api_competition_ids_from_excel()`
- `src/football_api/live_score_client.py`: Added parameter `competition_ids` to `get_live_matches()`
- `src/utils/setup_utils.py`: Load Live API competition IDs from Excel
- `src/main.py`: Pass Live API competition IDs to `get_live_matches()`

**Result:**
- Both Betfair and Live API only fetch matches from competitions in Excel
- More accurate matching and reduced number of unnecessary matches
- Log will display number of matches filtered by Excel competitions

**Example Log:**
```
Live API: 3 live match(es) available  # Filtered from 11 matches down to 3 matches according to Excel
  [1] Inter Milan v AC Milan (4_Serie A) - 1-0 @ 35' [IN PLAY]
  [2] Real Madrid v Barcelona (3_LaLiga Santander) - 0-0 @ 42' [IN PLAY]
  [3] Manchester United v Liverpool (2_Premier League) - 2-1 @ 55' [IN PLAY]
```

---

## Issues Fixed (Latest Updates):

### Issue 1: Refresh Mapping Interval Too Fast ✅
**Problem:** Matching refresh was running every 30 seconds, causing excessive API calls and noisy logs.

**Solution:** Changed refresh interval from 30 seconds to 60 minutes as requested.

**Files Modified:**
- `src/main.py`: Updated `matching_refresh_interval` from 30 to 3600 seconds

---

### Issue 2: Bot Tracking Matches Not in Excel ✅
**Problem:** Bot was displaying and tracking matches from competitions not in the Excel file (e.g., showing Argentina matches when only Brazilian Serie A was in Excel).

**Solution:** 
- Added filtering to only fetch markets from competitions that exist in Excel
- Uses `competition_ids` from Excel mapping to filter Betfair markets
- Only matches with competitions in Excel are processed

**Files Modified:**
- `src/utils/setup_utils.py`: Loads competition IDs from Excel
- `src/main.py`: Filters markets by `competition_ids` before processing

---

### Issue 3: Mapping Betfair ↔ LiveScore Wrong Flow ✅
**Problem:** Bot was fetching all live matches from Betfair first, then trying to match with Excel, instead of filtering by Excel competitions first.

**Solution:**
- Correct flow: Load Excel competitions → Get Betfair competition IDs → Filter Betfair markets by these IDs → Match with LiveScore API
- Markets are now filtered by Excel competitions before matching with LiveScore

**Files Modified:**
- `src/main.py`: Reordered logic to filter by Excel competitions first
- `src/config/competition_mapper.py`: Enhanced mapping to get competition IDs from Excel

---

### Issue 4: Some Matches Show [N/A] Target List ✅
**Problem:** Some matches displayed [N/A] for target scores even though the competition existed in Excel, due to competition name mismatch between Betfair/LiveScore API and Excel.

**Solution:**
- **Added ID-based matching**: Competition matching now uses both ID and name
- **Priority order:**
  1. Match by competition ID (from `Competition-Betfair` column in Excel) - most accurate
  2. Match by exact name
  3. Match by normalized name (case-insensitive, special characters removed)
  4. Match by "ID_Name" format
- **Enhanced Excel loading**: Reads `Competition-Betfair` column to extract competition IDs
- **Fallback logic**: If Live API competition name doesn't match, tries Betfair competition name

**Files Modified:**
- `src/logic/qualification.py`: 
  - Added `competition_id` parameter to `get_competition_targets()`
  - Enhanced `load_competition_map_from_excel()` to load Competition-Betfair column
  - Added ID-based matching logic with priority
- `src/main.py`: Passes competition ID from Betfair API to matching functions

**Result:** Significantly reduced [N/A] occurrences by matching competitions more accurately using both ID and name.

---

### Issue 5: Using Wrong Source / Cloudflare Warnings ⚠️
**Problem:** User reported Cloudflare warnings when accessing Betfair website (apps.betfair.com, betfair.it).

**Solution:** 
- Bot uses **Betfair API** and **Stream API** only, not web scraping
- No changes needed - bot already uses correct API endpoints
- Cloudflare warnings are not relevant as bot doesn't access websites directly

---

### Issue 6: Logging Missing Reasons for Matched vs Skipped ✅
**Problem:** Log only showed "Matched: 1/4 event(s)" but didn't explain why 3 events were not matched.

**Solution:**
- **Added detailed rejection reason analysis**: Function `analyze_rejection_reason()` in `matcher.py`
- **Logs specific reasons** for each unmatched event:
  - Team names don't match (with similarity score)
  - Competition mismatch
  - Kick-off time mismatch
  - No Live API matches available
- **Enhanced logging output**: After "Matched: X/Y event(s)", shows detailed list of unmatched events with reasons

**Files Modified:**
- `src/football_api/matcher.py`: 
  - Added `analyze_rejection_reason()` function
  - Enhanced `match_betfair_to_live_api()` to collect unmatched events with reasons
- `src/main.py`: 
  - Logs detailed rejection reasons for unmatched events
  - Shows each unmatched event with specific reason (team mismatch, competition mismatch, etc.)

**Example Output:**
```
Matched: 1/4 event(s)
❌ 3 event(s) not matched:
  - Team A v Team B (Competition Name): Team names don't match (best similarity: 0.45, required: 0.70); Competition mismatch
  - Team C v Team D (Competition Name): No Live API matches available
```

---

## Summary of All Fixes:

| Issue | Status | Description |
|-------|--------|-------------|
| 1. Refresh interval too fast | ✅ Fixed | Changed from 30s to 60 minutes |
| 2. Tracking matches not in Excel | ✅ Fixed | Added Excel competition filtering |
| 3. Wrong mapping flow | ✅ Fixed | Filter by Excel competitions first |
| 4. [N/A] target list | ✅ Fixed | Added ID-based matching + name matching |
| 5. Cloudflare warnings | ⚠️ N/A | Bot uses API, not web scraping |
| 6. Missing rejection reasons | ✅ Fixed | Added detailed logging for unmatched events |
| 7. Dynamic polling & fast polling | ✅ Fixed | Livescore 60s↔10s, Betfair 1s at 74'-76', strict discard at 60' |
| 8. Live API competition filtering | ✅ Fixed | Filter Live API matches by Excel competitions |
| 9. VAR delay for discard candidates | ✅ Fixed | Wait 3-5 minutes before discarding impossible matches to account for VAR decisions |
| 10. LiveScore API error handling | ✅ Fixed | Retry logic (2 retries), User-Agent header, distinguish "API unreachable" vs "0 matches" |
| 11. Betfair matching issue (Brazil Serie A/B) | ✅ Fixed | Stream API integration + Excel competition filtering |
| 12. Config cleanup | ✅ Fixed | Removed unused config fields (min_odds, max_odds, stake_percent, max_liability) |
| 13. Dynamic polling enabled for paid plan | ✅ Fixed | Enabled dynamic polling (60s↔10s) after customer upgraded to paid plan |

---

## Latest Fixes (November 2025):

### Issue 10: LiveScore API Error Handling ✅
**Problem:** Customer reported frequent connection errors:
- `RemoteDisconnected('Remote end closed connection without response')`
- `ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host')`
- `WinError 10054` errors
- Bot was treating these errors as "0 live matches" instead of "API temporarily unreachable"

**Solution:**
- **Retry Logic:**
  - Added automatic retry mechanism (2 retries, total 3 attempts)
  - Random delay between 0.5-1.0 seconds between retries
  - Only retries for connection errors (`RemoteDisconnected`, `ConnectionResetError`, `WinError 10054`, `Timeout`)
  - Does not retry for HTTP errors (4xx, 5xx)
  
- **User-Agent Header:**
  - Added User-Agent header to all LiveScore API requests (as recommended by LiveScore API support)
  - Header: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36`
  - Helps prevent `WinError 10054` connection reset errors
  
- **Error Distinction:**
  - `get_live_matches()` now returns:
    - `None` = API not reachable (connection error after retries)
    - `[]` = 0 matches (API call successful but no matches)
    - `[matches...]` = matches found
  - Logs clearly distinguish between "API not reachable" and "0 matches"
  
- **Packages Added:**
  - Added `pyopenssl>=23.2.0` to `requirements.txt`
  - Added `ndg-httpsclient>=0.5.1` to `requirements.txt`
  - Added `pyasn1>=0.5.0` to `requirements.txt`
  - These packages improve TLS/SSL handshake stability

**Files Modified:**
- `src/football_api/live_score_client.py`: 
  - Added retry logic in `_make_request()` method
  - Added User-Agent header to session
  - Modified `get_live_matches()` to return `None` when API is unreachable
- `src/main.py`: 
  - Updated to handle `None` return value from `get_live_matches()`
  - Logs "LiveScore API not reachable for this cycle, skipping this poll" when API is unreachable
- `requirements.txt`: Added SSL/TLS support packages

**Result:**
- Bot now handles transient network errors gracefully
- Clear distinction between "API unreachable" and "no matches"
- Reduced false "0 matches" logs when API has connection issues
- More stable connection to LiveScore API

**Example Log:**
```
Connection error in Live Score API request (attempt 1/3): ('Connection aborted.', ConnectionResetError(10054, ...))
Retrying in 0.75 seconds...
LiveScore API not reachable for this cycle, skipping this poll
```

---

### Issue 11: Betfair Matching Issue (Brazil Serie A/B Not Detected) ✅
**Problem:** Customer reported that Brazil Serie A and Serie B matches were correctly detected on LiveScore but not detected on Betfair, even though they were live on Betfair.

**Root Cause:**
- Betfair REST API `listMarketCatalogue` with `inPlay=True` filter was unreliable
- Markets returned with `inPlay=True` but actual status was `SUSPENDED` or `CLOSED`
- MarketBook verification was failing due to missing `marketDefinition` in response
- Pagination issues with 200 market limit

**Solution:**
- **Stream API Integration:**
  - Replaced `listMarketCatalogue` + `listMarketBook` verification with Stream API approach
  - New function `get_live_markets_from_stream_api()` in `main.py`
  - Stream API only returns markets that are actually `OPEN` and `inPlay=True` (verified in real-time)
  
- **Stream API Flow:**
  1. Fetch market IDs from REST API (`listMarketCatalogue` with `inPlay=True`, `max_results=200`)
  2. Connect to Stream API via SSL socket
  3. Authenticate with Stream API
  4. Subscribe to market IDs (batches of 200)
  5. Collect messages for 5 seconds
  6. Filter for `inPlay=True` and `status="OPEN"` from Stream API messages
  7. Return only verified live markets
  
- **Excel Competition Filtering:**
  - Filter markets by `competition_ids` from Excel after getting from Stream API
  - Only keep matches from competitions mapped in Excel
  - Improved error handling for missing `competition_id`

**Files Modified:**
- `src/main.py`: 
  - Added `get_live_markets_from_stream_api()` function
  - Replaced `listMarketCatalogue` calls with Stream API approach
  - Enhanced competition filtering logic with error handling
- `src/betfair/market_service.py`: 
  - Improved pagination for `listMarketCatalogue`
  - Enhanced `marketProjection` to include `COMPETITION` and `EVENT` data

**Result:**
- Bot now correctly detects all live matches on Betfair (including Brazil Serie A/B)
- Only processes markets that are actually `OPEN` and `inPlay`
- More accurate matching between Betfair and LiveScore
- Better error handling for edge cases

**Example Log:**
```
Betfair lives: 34952362_Tijuana v FC Juarez, 12345678_Gremio v Vasco da Gama
Betfair: 1 available matches after comparing with Excel.
```

---

### Issue 12: Config Cleanup ✅
**Problem:** Customer asked about unused config fields:
- `min_odds: 1.5`
- `max_odds: 10`
- `stake_percent: 5%`
- `max_liability: 100`
- These values are not used as stake and odds come from Excel file

**Solution:**
- **Removed Unused Fields:**
  - Removed `max_odds` from `config.json`
  - Removed `stake_percent` from `config.json`
  - Removed `max_liability` from `config.json`
  
- **Kept with Clarification:**
  - `min_odds: 1.5` - Kept as fallback value when `Min_Odds` column is missing in Excel
  - Added comment: "min_odds: Fallback value when Min_Odds column is missing in Excel. Bot prioritizes Min_Odds from Excel (per competition + result), uses this config value only if Excel doesn't have it."
  
- **Added Notes:**
  - Added `_note_stake_liability`: "Stake and liability are read from Excel file (Stake column), not from config. Each competition + result has its own Stake value in Excel."
  - Clarified that `target_over: 2.5` is used as fallback logic when Excel targets are not available

**Files Modified:**
- `config/config.json`: Removed unused fields, added clarifying comments

**Result:**
- Cleaner config file with only used fields
- Clear documentation of where values come from (Excel vs config)
- No confusion about unused parameters

---

### Issue 13: Dynamic Polling Enabled for Paid Plan ✅
**Problem:** Customer purchased paid plan for LiveScore API and requested to enable dynamic polling feature.

**Solution:**
- **Config Updated:**
  - Changed `api_plan` from `"trial"` to `"paid"`
  - Changed `rate_limit_per_day` from `1500` to `14500`
  - Changed `dynamic_polling_enabled` from `false` to `true`
  
- **Dynamic Polling Behavior:**
  - Default mode: 60 seconds when no matches in 60'-76' window
  - Intensive mode: 10 seconds when at least 1 match in 60'-76' window and not discarded
  - Automatically switches back to 60s when no more valid matches in window

**Files Modified:**
- `config/config.json`: Updated for paid plan configuration

**Result:**
- Dynamic polling is now active
- More frequent updates when matches are in critical 60'-76' window
- Efficient use of paid plan's 14500 requests/day limit

