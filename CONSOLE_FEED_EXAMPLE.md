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
  Match                                    | Min   | Score       | Targets                  | State                    
  ------------------------------------------------------------------------------------------------------------
  Gremio v Vasco da Gama                  | 67'   | 🟢 2-1      | 1-1, 2-1, 2-2           | TARGET (TRACKING)        
  Botafogo FR v Sport Recife               | 65'   | 1-0         | 0-0, 1-0, 1-1           | TRACKING                 
  SE Palmeiras v EC Vitoria Salvador       | 60'   | 0-0         | 0-0, 0-1, 1-0           | TRACKING                 
  ============================================================================================================

  🎯 0 match(es) ready for bet placement
```

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
  Match                                    | Min   | Score       | Targets                  | State                    
  ------------------------------------------------------------------------------------------------------------
  Gremio v Vasco da Gama                  | 75'   | 🟢 3-1      | 1-1, 2-1, 2-2           | TARGET (READY_FOR_BET)   
  Botafogo FR v Sport Recife               | 68'   | 1-0         | 0-0, 1-0, 1-1           | TRACKING                 
  ============================================================================================================

  🎯 1 match(es) ready for bet placement
```

---

### 4. Bet Placement

#### 4.1. Bet Placed Successfully
```
Attempting to place lay bet for Gremio v Vasco da Gama (minute 75, score: 3-1)
  ✅ BET PLACED: Gremio v Vasco da Gama
     Market: Over/Under 2.5 Goals
     Lay @ 1.85, Stake: 10.0 EUR, Liability: 8.5 EUR
     BetId: 123456789
Bet placed successfully: BetId=123456789, Stake=10.0, Liability=8.5
Bet matched immediately: BetId=123456789, SizeMatched=10.0
```

#### 4.2. Updated Table After Bet
```
[3] Tracking 1 match(es) from minute 60-74:

  ============================================================================================================
  Match                                    | Min   | Score       | Targets                  | State                    
  ------------------------------------------------------------------------------------------------------------
  Botafogo FR v Sport Recife               | 70'   | 1-0         | 0-0, 1-0, 1-1           | TRACKING                 
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
   - Current score (🟢 green if score is in targets)
   - Target scores from Excel
   - Current state (WAITING_60, TRACKING, QUALIFIED, READY_FOR_BET, etc.)
3. **Real-time Updates**: Table updates every 10 seconds
4. **State Indicators**:
   - `WAITING_60`: Match hasn't reached minute 60 yet
   - `TRACKING`: Monitoring for goals in 60-74 window
   - `QUALIFIED`: Goal detected in 60-74 window
   - `READY_FOR_BET`: Match is at minute 75+ and qualified
   - `TARGET`: Current score matches one of the target scores
   - `[STALE]`: Match data hasn't updated in > 2 minutes
5. **Event Logs**: Clear messages for qualification, bet placement, and discards
6. **Summary**: Shows count of matches ready for bet placement

---

## Color Coding (if terminal supports):
- 🟢 Green circle: Score matches target
- ✓ Checkmark: Match qualified
- 🎯 Target: Ready for bet
- ✘ Cross: Match discarded
- ⏭️ Skip: Match skipped (too late)

