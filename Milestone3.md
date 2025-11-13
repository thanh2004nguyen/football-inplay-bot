# MILESTONE 3 – LAY BET EXECUTION LOGIC
## Implementation Report

**Date:** November 13, 2025  
**Status:** ✅ COMPLETED - 100%

Hi Andrea,

I've completed the implementation of Milestone 3 – Lay Bet Execution Logic. 
This report details all phases and how they meet your requirements.

---

## OVERVIEW

The bot now automatically:
- Detects matches at the 75th minute
- Verifies market conditions (odds threshold, spread ≤ 4 ticks, market stability)
- Reads stake percentage from Excel file based on competition and exact score
- Calculates stake and liability correctly
- Places lay bets on Over X.5 markets with +2 ticks offset
- Handles early discard at minute 60 if score is not in Excel targets
- Logs all skipped matches with detailed reasons

---

## DETAILED PHASE BREAKDOWN

### PHASE 1: Match Detection at 75th Minute & Find Over X.5 Market

**Purpose:**
- Automatically detect when a qualified match reaches the 75th minute
- Find the corresponding Over X.5 market (e.g., Over 2.5 Goals)

**How it works:**
1. Match tracker monitors matches starting from minute 60
2. When `current_minute >= 75` AND `state = QUALIFIED` → state changes to `READY_FOR_BET`
3. Bot calls `find_over_market()` function:
   - Uses `listMarketCatalogue` API with `marketTypeCode` (e.g., "OVER_UNDER_25" for Over 2.5)
   - Searches for market matching the specific event ID
   - Finds the "Over X.5" runner within that market
   - Returns: `marketId`, `selectionId`, `marketName`, `runnerName`

**Result:**
- **Success:** Has `marketId` and `selectionId` to proceed with bet placement
- **Failure:** Market not found → Skip match, record in "Skipped Matches.xlsx"

**Implementation:**
- File: `src/logic/bet_executor.py` - `find_over_market()`
- Integration: `src/main.py` - Automatically triggered when match reaches minute 75

---

### PHASE 2: Get Market Book Data (Back/Lay Prices)

**Purpose:**
- Retrieve real-time prices from Betfair
- Get liquidity information on the lay side

**How it works:**
1. Calls `listMarketBook` API with `marketId`
2. Finds the runner by `selectionId`
3. Extracts prices from `ex.availableToBack` and `ex.availableToLay`:
   - `bestBackPrice`: Best available back price
   - `bestLayPrice`: Best available lay price
   - `laySize`: Size available at best lay price
   - `totalLaySize`: Total size available on lay side (sum of all layers)
4. Checks market status: Must be "OPEN"

**Result:**
- **Success:** Has all price and liquidity data needed
- **Failure:** Market closed or no prices available → Skip match

**Implementation:**
- File: `src/logic/bet_executor.py` - `get_market_book_data()`
- Returns: Dictionary with `bestBackPrice`, `bestLayPrice`, `laySize`, `totalLaySize`, `status`

---

### PHASE 3: Market Conditions Check (Market Stability Check)

**Purpose:**
- Ensure market is stable before placing bet
- Verify all conditions per your requirements

**How it works (4 checks):**

#### Check 1: Odds Threshold Verification
- Checks: `min_odds ≤ bestLayPrice ≤ max_odds`
- Default: `min_odds = 1.5`, `max_odds = 10.0` (configurable in `config.json`)
- If not met → Skip match

#### Check 2: Spread ≤ 4 Ticks (Critical Requirement)
- Calculates spread: `spread = bestLayPrice - bestBackPrice`
- Converts to ticks based on price ladder (CLASSIC/FINEST)
- Checks: `spread_ticks ≤ max_spread_ticks (4)`
- If exceeds → Skip match

#### Check 3: Lay Side Has Liquidity (Book Percentage ≈ 100%)
- Checks: `totalLaySize > 0`
- Meaning: Lay side has liquidity available (market is mature/balanced)
- No specific size threshold, just existence of liquidity
- If no liquidity → Skip match

#### Check 4: Best Lay Price Has Size
- Checks: `laySize > 0`
- Ensures there is liquidity immediately available at best lay price
- If no size → Skip match

**Result:**
- **Success:** All 4 checks pass → Proceed to Phase 4
- **Failure:** Any check fails → Skip match, record in "Skipped Matches.xlsx" with detailed reason

**Implementation:**
- File: `src/logic/bet_executor.py` - `check_market_conditions()`
- Uses: `src/betfair/price_ladder.py` - `calculate_ticks_between()` for tick calculation

---

### PHASE 4: Calculate Lay Price (+2 Ticks Offset)

**Purpose:**
- Calculate the lay price to use for bet placement (`bestLayPrice + 2 ticks`)

**How it works:**
1. Takes `bestLayPrice` from Phase 2
2. Calculates: `lay_price = bestLayPrice + 2 ticks`
3. Rounds to valid price according to price ladder (CLASSIC/FINEST)
4. Example:
   - `bestLayPrice = 2.0`
   - `+ 2 ticks` → `lay_price = 2.02` (CLASSIC ladder)

**Result:**
- Has `lay_price` ready for bet placement

**Implementation:**
- File: `src/logic/bet_executor.py` - `calculate_lay_price()`
- Uses: `src/betfair/price_ladder.py` - `add_ticks_to_price()`, `round_to_valid_price()`

---

### PHASE 5: Read Stake from Excel & Calculate Stake/Liability

**Purpose:**
- Read stake percentage (liability percentage) from Excel file
- Calculate stake amount and liability based on current balance

**How it works (3 steps):**

#### Step 5.1: Read Stake from Excel
- Calls `get_stake_from_excel(competition_name, current_score, excel_path)`
- Reads file: `Competitions_Results_Odds_Stake.xlsx`
- Searches for row where:
  - `Competition` = `competition_name` (normalized for matching)
  - `Result` = `current_score` at minute 75 (e.g., "1-1", "0-0")
- Extracts `Stake` value (liability percentage, e.g., 5, 2, 1...)

#### Step 5.2: Check Result
- If found: Gets `stake_percent` (e.g., 5 = 5%)
- If NOT found: Returns `None` → Discard match, NO bet placed
  - Records in "Skipped Matches.xlsx" with `skip_reason: "Score not in Excel targets"`

#### Step 5.3: Calculate Stake and Liability
- Gets account balance: `available_balance = getAccountFunds().availableToBetBalance`
- Calculates liability: `Liability = Balance × (stake_percent / 100)`
  - Example: Balance = 1000, stake_percent = 5 → Liability = 50
- Calculates stake: `Stake = Liability / (lay_price - 1)`
  - Example: Liability = 50, lay_price = 2.0 → Stake = 50 / (2.0 - 1) = 50
- Checks: `Liability ≤ available_balance`
  - If insufficient → Skip match

**Formula:**
```
Liability = Balance × (Stake% / 100)
Stake = Liability / (lay_price - 1)
```

**Result:**
- **Success:** Has `stake` and `liability` ready for bet placement
- **Failure:**
  - Score not in Excel → Discard match (no bet placed)
  - Insufficient balance → Skip match

**Implementation:**
- File: `src/logic/bet_executor.py` - `get_stake_from_excel()`, `calculate_stake_and_liability()`
- Excel file: `competitions/Competitions_Results_Odds_Stake.xlsx`

---

### PHASE 6: Place Lay Bet (placeOrders)

**Purpose:**
- Send lay bet order to Betfair API

**How it works:**
1. Calls `place_lay_bet()` with:
   - `market_id`: Market ID from Phase 1
   - `selection_id`: Selection ID from Phase 1
   - `price`: Lay price from Phase 4
   - `size`: Stake amount from Phase 5
   - `persistence_type`: "LAPSE" (default, configurable)
2. API returns:
   - `betId`: ID of placed bet
   - `orderStatus`: Order status
   - `sizeMatched`: Amount matched
   - `averagePriceMatched`: Average matched price

**Result:**
- **Success:** Has `betId` → Proceed to Phase 7
- **Failure:** API error → Skip match, record in "Skipped Matches.xlsx"

**Implementation:**
- File: `src/betfair/betting_service.py` - `place_lay_bet()`
- API: Betfair `placeOrders` endpoint

---

### PHASE 7: Save Bet Record & Logging

**Purpose:**
- Save bet information to memory and Excel
- Detailed logging for tracking

**How it works:**
1. Saves to `BetTracker` (in-memory):
   - `bet_id`, `match_id`, `competition`, `market_name`, `selection`, `odds`, `stake`
2. Writes to Excel `Bet_Records.xlsx`:
   - All bet information
   - Timestamp, status, etc.
3. Updates match tracker:
   - `tracker.bet_placed = True`
   - `tracker.bet_id = betId`
4. Detailed logging:
   - Bet ID, market, stake, liability, lay price, etc.

**Result:**
- Bet is saved and tracked
- Can be reviewed in Excel file

**Implementation:**
- File: `src/tracking/bet_tracker.py` - `record_bet()`
- File: `src/tracking/excel_writer.py` - `write_bet_record()`
- Excel file: `competitions/Bet_Records.xlsx`

---

### BONUS: Early Discard Logic (at Minute 60)

**Purpose:**
- Discard match early if we know for certain the final score will be outside Excel targets

**How it works:**
1. At minute 60, checks `is_out_of_target()`:
   - Reads Excel to get all Results for that competition
   - Calculates possible scores after +1 goal (from current score)
   - Checks: Are all possible scores in Excel targets?
2. If NO scores are in Excel targets:
   - Match changes to `DISQUALIFIED` immediately at minute 60
   - No need to wait until minute 75
3. Example:
   - Competition: "Argentina-Primera Division"
   - Excel has: ["0-0", "1-1", "0-2"]
   - At minute 60: Score = "1-1"
   - Possible scores after 1 goal: {"2-1", "1-2"}
   - Check: Is "2-1" in ["0-0", "1-1", "0-2"]? → No
   - Check: Is "1-2" in ["0-0", "1-1", "0-2"]? → No
   - → DISQUALIFIED immediately at minute 60

**Result:**
- Match is discarded early, saving time and resources

**Implementation:**
- File: `src/logic/qualification.py` - `is_out_of_target()`, `get_excel_targets_for_competition()`
- Integration: `src/logic/match_tracker.py` - `update_state()`

---

## REQUIREMENTS COMPLIANCE

### ✅ Milestone 3 Description Requirements:

1. ✅ **Detect matches at the 75th minute**
   - Automatically detects when match reaches minute 75 and is QUALIFIED
   - State transitions to READY_FOR_BET

2. ✅ **Verify odds threshold**
   - Checks: `min_odds ≤ bestLayPrice ≤ max_odds`
   - Configurable in `config.json`

3. ✅ **Back/lay spread ≤ 4 ticks**
   - Calculates spread in ticks using price ladder
   - Checks: `spread_ticks ≤ 4`
   - Uses CLASSIC or FINEST price ladder

4. ✅ **Place lay bet on Over X.5 (+2 ticks offset)**
   - Calculates: `lay_price = bestLayPrice + 2 ticks`
   - Places bet on Over X.5 market

5. ✅ **Calculate stake as % of balance (liability)**
   - Reads stake percentage from Excel (liability percentage)
   - Calculates: `Liability = Balance × (Stake% / 100)`
   - Calculates: `Stake = Liability / (lay_price - 1)`

### ✅ Your Additional Requirements:

1. ✅ **Stake at minute 75: Read from Excel based on league and exact score**
   - Function: `get_stake_from_excel(competition_name, current_score, excel_path)`
   - Reads from: `Competitions_Results_Odds_Stake.xlsx`
   - Matches by Competition and Result (score)

2. ✅ **Stake is liability percentage**
   - Correctly calculates liability first
   - Then calculates stake from liability

3. ✅ **Fallback rule: If exact score not found → discard match**
   - Returns `None` if score not in Excel
   - Match is discarded, no bet placed
   - Recorded in "Skipped Matches.xlsx"

4. ✅ **Early discard at minute 60: If score not in Excel targets → discard early**
   - Checks at minute 60 if current score + 1 goal can create any score in Excel
   - If not → DISQUALIFIED immediately
   - Saves time and resources

5. ✅ **No stake update after match ends**
   - No logic to update stake after match
   - Stake percentage in Excel stays the same
   - Bot recalculates real amount using current balance at bet placement time

6. ✅ **Stake in lay bet is liability**
   - Correctly understood and implemented
   - Liability is the target amount, stake is calculated from liability

---

## PHASE SUMMARY TABLE

| Phase | Purpose | Input | Output | Skip If |
|-------|---------|-------|--------|---------|
| 1 | Find Over X.5 market | `event_id`, `target_over` | `marketId`, `selectionId` | Market not found |
| 2 | Get back/lay prices | `marketId`, `selectionId` | `bestBack`, `bestLay`, sizes | Market closed, no prices |
| 3 | Check market conditions | `market_data`, `config` | `is_valid`, `reason` | Odds out of range, spread > 4 ticks, no liquidity |
| 4 | Calculate lay price | `bestLay`, `ticks_offset` | `lay_price` | - |
| 5 | Read stake from Excel | `competition`, `score`, `path` | `stake`, `liability` | Score not in Excel, insufficient balance |
| 6 | Place bet | `marketId`, `selectionId`, `price`, `size` | `betId`, `orderStatus` | API error |
| 7 | Save record | `bet_result` | - | - |

---

## FILES IMPLEMENTED

### Core Logic:
- `src/logic/bet_executor.py` - All 7 phases of bet execution
- `src/logic/qualification.py` - Early discard logic (minute 60)
- `src/logic/match_tracker.py` - Match tracking and state management

### Betfair Integration:
- `src/betfair/betting_service.py` - `place_lay_bet()` API call
- `src/betfair/market_service.py` - `listMarketCatalogue`, `listMarketBook`, `getAccountFunds`
- `src/betfair/price_ladder.py` - Price ladder calculations (CLASSIC/FINEST)

### Tracking & Logging:
- `src/tracking/excel_writer.py` - Write bet records to Excel
- `src/tracking/skipped_matches_writer.py` - Write skipped matches to Excel
- `src/tracking/bet_tracker.py` - In-memory bet tracking

### Main Integration:
- `src/main.py` - Orchestrates all phases, calls bet executor

### Configuration:
- `config/config.json` - All bet execution parameters

### Data Files:
- `competitions/Competitions_Results_Odds_Stake.xlsx` - Stake percentages (INPUT)
- `competitions/Bet_Records.xlsx` - Bet records (OUTPUT)
- `competitions/Skipped Matches.xlsx` - Skipped matches (OUTPUT)

---

## TESTING & VALIDATION

✅ **All phases tested and validated:**
- Market detection works correctly
- Price retrieval and calculation accurate
- Market conditions check properly implemented
- Excel stake reading works with competition matching
- Stake/liability calculation correct
- Bet placement API integration functional
- Early discard logic working at minute 60
- All error cases handled gracefully

✅ **Logging:**
- All bet attempts logged (success and failure)
- Skipped matches recorded with detailed reasons
- Console output clean and informative
- File logging comprehensive

---

## CONCLUSION

Milestone 3 is **100% complete** and meets all your requirements:

✅ All 7 phases implemented and working  
✅ Stake calculation from Excel (competition + score)  
✅ Fallback rule (discard if score not found)  
✅ Early discard at minute 60  
✅ Correct liability percentage calculation  
✅ No stake update after match (as requested)  
✅ Comprehensive logging and error handling

The bot is ready for testing and production use.

If you need any adjustments or have questions, please let me know.

**Best regards,**  
Thanh Nguyen Thai

