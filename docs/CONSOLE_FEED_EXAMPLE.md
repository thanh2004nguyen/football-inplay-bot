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

#### 2.2. Live API Matches (Every 60 seconds)
```
Live API: 4 live match(es) available
  [1] Gremio v Vasco da Gama (Brazilian Serie A) - 2-1 @ 67' [LIVE]
  [2] SE Palmeiras v EC Vitoria Salvador (Brazilian Serie A) - 0-0 @ 38' [LIVE]
  [3] Botafogo FR v Sport Recife (Brazilian Serie A) - 1-0 @ 52' [LIVE]
  [4] Santos v Mirassol (Brazilian Serie A) - 0-1 @ 45' [LIVE]
```

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
✘ Match SE Palmeiras v EC Vitoria Salvador: Disqualified (no goal in 60-74, no 0-0 exception)
```

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

#### 3.6. Skipped Matches Section (At Minute 75)
```
[SKIPPED] Gremio v Vasco da Gama – Reason: spread > 4 ticks
[SKIPPED] Palmeiras v EC Vitoria – Reason: Under price below reference odds
[SKIPPED] Botafogo FR v Sport Recife – Reason: Current score not in target list at 75'
[SKIPPED] Santos v Mirassol – Reason: No Excel config for this score
```

---

### 4. Bet Placement

#### 4.1. Bet Placed Successfully (At Exactly Minute 75')
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

**Note:** The bet is evaluated and placed at exactly minute 75' (not at 76', 77', etc.). The bot:
1. Re-checks that current score (2-1) is still in target list
2. Reads from Excel: stake % (5%) and reference odds (1.75) for this competition and score
3. Checks Under X.5 best back (1.80) ≥ reference odds (1.75) → OK
4. Checks Over X.5 spread (3 ticks) ≤ 4 ticks → OK
5. Calculates liability: Bankroll (300.00) × 5% = 15.00
6. Calculates lay stake: 15.00 / (3.20 - 1) = 6.82
7. Places LAY bet on Over 2.5 at best lay (3.10) + 2 ticks = 3.20

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

1. **Live Matches List**: Shows all available matches from Betfair and Live API
2. **Tracking Table**: Displays matches in 60-74 minute window with:
   - Match name
   - Current minute
   - Current score (🟢 green dot if TARGET - score reached in 60-74 window or 0-0 at 60')
   - Target scores from Excel
   - Current state (TRACKING, TARGET (TRACKING), TARGET (READY_FOR_BET), etc.)
3. **Real-time Updates**: Table updates every 10 seconds (or as configured)
4. **Green Dot (🟢) Logic**:
   - Shows green dot if current score is in target list AND score was reached by a goal between 60-74 minutes
   - Special case: 0-0 at minute 60' gets green dot immediately if 0-0 is in target list
   - NO green dot if score was already present before minute 60 and no goal in 60-74 window
   - Green dot is removed if later goal changes score to something not in target list
5. **Summary of Ready Matches**: 
   - Shows "🎯 X match(es) ready for bet placement"
   - Only includes matches that are:
     - Still TARGET at minute 75
     - Current score still in target list
     - Under X.5 price ≥ reference odds (from Excel)
     - Spread ≤ 4 ticks
     - Excel config exists for that competition and score
6. **Bet Placement**: 
   - Triggered at exactly minute 75' (not at 76', 77', etc.)
   - Re-checks all conditions before placing bet
   - Shows detailed [BET PLACED] block with all information
7. **Skipped Matches**: 
   - Logs matches that entered 60-74 tracking but didn't trigger bet at 75'
   - Reasons include: spread > 4 ticks, Under price below reference, score not in targets, no Excel config
8. **Event Logs**: Clear messages for qualification, bet placement, and discards

---

## Color Coding & Symbols:
- 🟢 **Green dot**: Match is TARGET (score in targets AND reached in 60-74 window, or 0-0 at 60')
- ✓ **Checkmark**: Match qualified (goal in 60-74 or 0-0 exception)
- 🎯 **Target**: Match ready for bet placement (at 75' and meets all conditions)
- ✘ **Cross**: Match discarded (no goal in 60-74, no 0-0 exception)
- ⏭️ **Skip**: Match skipped (too late to start tracking, or conditions not met at 75')

## Important Notes:

1. **Green Dot Rules**:
   - Green dot appears ONLY if score was reached by a goal between 60-74 minutes
   - Exception: 0-0 at minute 60' gets green dot immediately if 0-0 is in target list
   - If score was already present before 60' and no goal in 60-74 → NO green dot
   - If match has green dot but later goal changes score → green dot is removed

2. **Bet Trigger**:
   - Bet is evaluated and placed at exactly minute 75' (not before, not after)
   - All conditions are re-checked at minute 75'
   - If any condition fails, match is skipped with clear reason

3. **Summary Count**:
   - "🎯 X match(es) ready for bet placement" only counts matches that:
     - Are at minute 75+
     - Still have TARGET status
     - Meet ALL conditions (score, odds, spread, Excel config)

