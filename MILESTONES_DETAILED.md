# Milestones Detailed Documentation
## Betfair Italy Bot - Complete Implementation Guide

**Last Updated:** November 12, 2025  
**Project:** Automated Betfair Exchange Bot for Italian Market

---

## Table of Contents

1. [Milestone 1: Authentication & Market Detection](#milestone-1-authentication--market-detection)
2. [Milestone 2: Live Data Integration & Match Logic](#milestone-2-live-data-integration--match-logic)
3. [Project Structure](#project-structure)
4. [Configuration Guide](#configuration-guide)

---

# Milestone 1: Authentication & Market Detection

**Status:** ✅ **COMPLETED - 100%**

## Overview

Milestone 1 establishes the foundation for the bot by implementing secure authentication with Betfair Italy Exchange and detecting in-play football markets from specified competitions.

## Objectives

- ✅ Secure connection to Betfair Italy Exchange API
- ✅ Certificate-based non-interactive login
- ✅ Session management with automatic keep-alive
- ✅ In-play market detection from specified competitions
- ✅ Competition mapping from Excel file
- ✅ Robust error handling and network resilience
- ✅ Comprehensive logging system

---

## Phase 1: Authentication & Session Management

### Requirements

1. **Certificate-Based Login**
   - Use SSL certificates (.crt and .key files)
   - Non-interactive login endpoint: `https://identitysso-cert.betfair.it/api/certlogin`
   - Secure session token retrieval

2. **Session Management**
   - Automatic keep-alive mechanism (every 300 seconds)
   - Automatic re-login on session expiry
   - Session token update across all services

### Implementation Details

**Files Created:**
- `src/auth/cert_login.py` - Certificate-based authentication
- `src/auth/keep_alive.py` - Session keep-alive manager

**Key Features:**
- Certificate-based authentication using `requests` with SSL certificates
- Session token storage and management
- Keep-alive thread running in background
- Callback mechanism for session expiry detection
- Automatic re-login on 401 errors

**Technical Details:**
- Login endpoint: `https://identitysso-cert.betfair.it/api/certlogin`
- Keep-alive endpoint: `https://identitysso.betfair.com/api/keepAlive`
- Session timeout: 3600 seconds (1 hour)
- Keep-alive interval: 300 seconds (5 minutes)

---

## Phase 2: Market Detection

### Requirements

1. **Market Retrieval**
   - Retrieve in-play football markets from Betfair API
   - Filter by event type (Football = 1)
   - Filter by competition IDs (from Excel file mapping)
   - Filter in-play markets only

2. **Real-time Monitoring**
   - Polling interval: 10 seconds (configurable)
   - Continuous market detection loop
   - Detailed logging of detected markets

### Implementation Details

**Files Created:**
- `src/betfair/market_service.py` - Market data retrieval

**Key Features:**
- `listMarketCatalogue` API integration
- Competition-based filtering
- In-play market detection
- Market details logging (ID, name, event, competition)

**API Endpoints Used:**
- `listEventTypes` - Get event types
- `listCompetitions` - Get competitions for event types
- `listMarketCatalogue` - Get market catalogue with filters
- `getAccountFunds` - Get account balance

---

## Phase 3: Competition Mapping from Excel

### Requirements

1. **Excel File Reading**
   - Read competition names from `Competitions_Results_Odds_Stake.xlsx`
   - Extract unique competition names from 'Competition' column

2. **Mapping Algorithm**
   - Advanced similarity matching
   - Normalize competition names (handle sponsor names, number words, special characters)
   - Map Excel competition names to Betfair API competition IDs

### Implementation Details

**Files Created:**
- `src/config/competition_mapper.py` - Excel to Betfair ID mapping

**Key Features:**
- Text normalization (lowercase, remove special characters, normalize numbers)
- Country and league name mappings
- Jaccard similarity calculation with subset handling
- 80% similarity threshold for matching
- Handles sponsor names (e.g., "English Sky Bet League 2" matches "England-League Two")

**Matching Logic:**
- Normalize Excel competition names
- Normalize Betfair competition names
- Calculate similarity using Jaccard similarity
- Handle subset relationships (e.g., "english league 2" is subset of "english sky bet league 2")
- Match if similarity >= 80%

---

## Phase 4: Error Handling & Resilience

### Requirements

1. **Network Error Handling**
   - Infinite retry on network connection errors
   - Smart detection of internet connectivity issues
   - Automatic reconnection when internet is restored

2. **Session Expiry Handling**
   - Automatic re-login on session expiry (401 errors)
   - Keep-alive callback triggers re-login
   - Session token update across all services

3. **Graceful Shutdown**
   - Handle KeyboardInterrupt (Ctrl+C)
   - No traceback on user interruption
   - Clean shutdown of all threads

### Implementation Details

**Error Types Handled:**
- `requests.exceptions.ConnectionError` - Network connection errors
- `requests.exceptions.Timeout` - Request timeout
- `requests.exceptions.HTTPError` (401) - Session expiry
- `KeyboardInterrupt` - User interruption

**Retry Logic:**
- Infinite retry for network errors
- Distinguish between "no internet" and other network errors
- Skip unnecessary re-login when internet is down
- Automatic resume when connection is restored

---

## Phase 5: Logging System

### Requirements

1. **File Logging**
   - Comprehensive logging to `logs/betfair_bot.log`
   - Log rotation (10MB max, 5 backup files)
   - Clear log on each start (configurable)
   - Timestamped entries for debugging

2. **Console Output**
   - Clean format (no timestamps, logger names, or log levels)
   - Real-time output for user monitoring
   - Error messages clearly displayed

### Implementation Details

**Files Created:**
- `src/core/logging_setup.py` - Logging configuration

**Log Levels:**
- **INFO**: Normal operations, successful matches, market detection
- **WARNING**: Network errors, session expiry, unmatched competitions (DEBUG level)
- **ERROR**: Critical errors, authentication failures
- **DEBUG**: Detailed debugging information

**Features:**
- Dual formatters (file vs console)
- File rotation with size limit
- Configurable clear on start
- Detailed logging for debugging

---

## Milestone 1 Deliverables

### ✅ Source Code
- Complete Python source code
- Modular architecture
- Well-documented code

### ✅ Configuration Files
- `config/config.json` - Main configuration
- `.env` - Environment variables (password)
- `config/config.example.json` - Template configuration

### ✅ Documentation
- `README.md` - Setup and running instructions
- `MILESTONE1_REPORT.md` - Completion report
- Inline code documentation

### ✅ Test Results
- Authentication successful
- Market detection working (50+ markets detected)
- Competition mapping successful (8/45 competitions matched)
- Network resilience tested
- Session management verified

---

# Milestone 2: Live Data Integration & Match Logic

**Status:** 🔄 **IN PROGRESS**

## Overview

Milestone 2 integrates external live football API to retrieve match data, implements match tracking logic to detect goals in minutes 60-74, handles VAR (cancelled goals), and implements 0-0 exception for specific competitions.

## Objectives

- ✅ Filter market types (exclude Winner/Champion markets)
- ⏳ Integrate Live Score API (live-score-api.com)
- ⏳ Match Betfair events with Live API matches
- ⏳ Track matches and detect goals in minutes 60-74
- ⏳ Handle VAR (cancelled goals)
- ⏳ Handle 0-0 exception (only for specified competitions)
- ⏳ Bet tracking and Excel export

---

## Phase 1: Filter Market Types

### Requirements

1. **Market Type Filtering**
   - Only consider markets related to specific matches
   - Exclude long-term markets (Winner, Champion, Season Winner, Top Scorer, etc.)
   - Ensure bot only triggers when finding match-specific markets

2. **Allowed Market Types**
   - Over/Under X.5 (0.5, 1.5, 2.5, 3.5, 4.5)
   - Match Odds
   - Both Teams to Score
   - Correct Score
   - First Goal Scorer
   - Next Goal
   - Half Time Score
   - Asian Handicap
   - European Handicap
   - Draw No Bet
   - Double Chance

3. **Excluded Market Types**
   - Winner (Outright)
   - Champion
   - Season Winner
   - Top Scorer (season-long)
   - Relegation
   - Promotion

### Implementation Details

**Files to Create:**
- `src/betfair/market_filter.py` - Market type filtering

**Key Functions:**
- `is_match_specific_market(market)` - Check if market is match-specific
- `filter_match_specific_markets(markets)` - Filter market list

**Filtering Logic:**
- Check market type code against allowed/excluded lists
- Check market name for excluded keywords
- Default: exclude if unsure (safer approach)

**Keywords to Exclude:**
- "winner", "champion", "outright", "season", "league winner"
- "top scorer", "relegation", "promotion", "championship", "title"

---

## Phase 2: Live Score API Integration

### Requirements

1. **API Connection**
   - Connect to live-score-api.com
   - Authentication with API Key and Secret
   - Handle rate limiting (trial: 1500/day, paid: 14500/day)

2. **Data Retrieval**
   - Get live matches list
   - Get match details (score, minute, goals)
   - Parse goal timeline (including cancelled/VAR status)

3. **Rate Limiting**
   - Trial plan: 1500 requests/day (~62 requests/hour)
   - Paid plan: 14500 requests/day (~604 requests/hour)
   - Automatic rate limit calculation based on plan

### Implementation Details

**Files to Create:**
- `src/football_api/live_score_client.py` - API client, authentication, rate limiting
- `src/football_api/parser.py` - Parse API responses

**API Details:**
- Base URL: `https://live-score-api.com/api/v1`
- API Key: `5vm1iY7mSjjK5ucr`
- API Secret: `sdGH2ss0BWkJxOqDjMECLMZD5iobNBCf`
- Documentation: https://live-score-api.com/documentation/reference/6/getting_livescores

**Key Methods:**
- `get_live_matches()` - Get list of live matches
- `get_match_details(match_id)` - Get match details (score, minute, goals)
- `parse_goals_timeline()` - Parse goal timeline with cancelled status

**Rate Limiting:**
- Configurable `api_plan` ("trial" or "paid")
- Auto-set `rate_limit_per_day` based on plan
- Rate limiter tracks requests and enforces limits

---

## Phase 3: Matching Logic

### Requirements

1. **Match Betfair Events with Live API Matches**
   - Match based on team names (fuzzy matching)
   - Match based on competition name
   - Match based on kick-off time (±30 minutes)

2. **Caching**
   - Cache mapping: Betfair Event ID → Live API Match ID
   - Avoid repeated queries
   - Update cache when new matches found

### Implementation Details

**Files to Create:**
- `src/football_api/matcher.py` - Match Betfair ↔ Live API

**Matching Criteria:**
1. **Team Names**
   - Normalize team names (lowercase, remove special characters)
   - Fuzzy matching (handle variations)
   - Handle team aliases

2. **Competition**
   - Match competition name
   - Use competition mapping from Milestone 1

3. **Time**
   - Match kick-off time (±30 minutes tolerance)
   - Handle timezone differences

**Caching Strategy:**
- Store mapping in memory (dictionary)
- Key: Betfair Event ID
- Value: Live API Match ID
- Update when new matches detected

---

## Phase 4: Match Tracking & Goal Detection

### Requirements

1. **Match State Tracking**
   - Track match state: WAITING_60, MONITORING_60_74, QUALIFIED, DISQUALIFIED, READY_FOR_BET
   - Store match data: score, minute, goals, qualification status
   - Update match data from Live API

2. **Goal Detection (Minutes 60-74)**
   - Detect goals in 60-74 minute window
   - Handle VAR: Check and exclude cancelled goals
   - Track goal timeline

3. **0-0 Exception**
   - Only apply to competitions specified in Excel file
   - Read from Excel: competitions with Result = "0-0"
   - If score is 0-0 at minute 60-74 AND competition in exception list → QUALIFIED

### Implementation Details

**Files to Create:**
- `src/logic/match_tracker.py` - Track match state
- `src/logic/qualification.py` - Qualification logic

**Match States:**
- `WAITING_60` - Waiting for minute 60
- `MONITORING_60_74` - Monitoring minutes 60-74
- `QUALIFIED` - Match qualified (goal in 60-74 or 0-0 exception)
- `DISQUALIFIED` - Match disqualified (no goal, no 0-0 exception)
- `READY_FOR_BET` - Ready to place bet (minute 75+)

**Goal Detection Logic:**
```python
def check_goal_in_60_74(goals, current_minute):
    """
    Check if there's a valid goal in 60-74 minute window
    """
    valid_goals = []
    for goal in goals:
        # Skip cancelled goals (VAR)
        if goal.get('cancelled', False):
            continue
        
        # Check if goal is in 60-74 window
        if 60 <= goal.get('minute', 0) <= 74:
            valid_goals.append(goal)
    
    return len(valid_goals) > 0
```

**0-0 Exception Logic:**
```python
def is_qualified(score, goals_60_74, current_minute, competition_name, 
                 zero_zero_exception_competitions):
    """
    Check if match is qualified
    """
    # 0-0 exception (ONLY for specified competitions)
    if score == "0-0" and 60 <= current_minute <= 74:
        if competition_name in zero_zero_exception_competitions:
            return True, "0-0 exception (competition allowed)"
        else:
            return False, "0-0 but competition not in exception list"
    
    # Check goals in 60-74 window
    valid_goals = [g for g in goals_60_74 if not g.get('cancelled', False)]
    if valid_goals:
        return True, f"Goal in 60-74 (minute {valid_goals[0].get('minute')})"
    
    return False, "No qualification"
```

**Reading 0-0 Exception from Excel:**
```python
def get_competitions_with_zero_zero_exception(excel_path: str) -> Set[str]:
    """
    Read Excel to identify competitions with 0-0 exception
    """
    df = pd.read_excel(excel_path)
    
    # Filter rows where Result = "0-0"
    zero_zero_rows = df[df['Result'].astype(str).str.strip().str.lower() == '0-0']
    
    # Get competition names
    competitions = zero_zero_rows['Competition'].dropna().unique().tolist()
    
    return set(competitions)
```

**Tracking Flow:**
1. **Minute 0-59**: Wait for minute 60
2. **Minute 60**: Start monitoring
3. **Minute 60-74**:
   - Update match data from Live API (every 5-10 seconds)
   - Check for new goals
   - Filter cancelled goals (VAR)
   - Check 0-0 exception (if applicable)
   - Mark QUALIFIED if conditions met
4. **Minute 75**: If QUALIFIED → Ready for bet (Milestone 3)

---

## Phase 5: Bet Tracking & Excel Export

### Requirements

1. **Bet Recording**
   - Record all placed bets with details
   - Track outcomes when match ends
   - Calculate profit/loss

2. **Bankroll Management**
   - Update bankroll after each bet
   - Track bankroll before and after each bet
   - Calculate total bankroll

3. **Excel Export**
   - Export bet records to Excel
   - Update bankroll column
   - Evaluate performance by league
   - Monitor overall trends

### Implementation Details

**Files to Create:**
- `src/tracking/bet_tracker.py` - Track bets and outcomes
- `src/tracking/excel_writer.py` - Export to Excel

**Excel Structure (Additional Columns):**
- `Bet_Time` - When bet was placed
- `Odds` - Odds at time of bet
- `Stake` - Stake amount
- `Outcome` - Bet outcome (Won/Lost/Pending)
- `Profit/Loss` - Profit or loss amount
- `Bankroll_Before` - Bankroll before bet
- `Bankroll_After` - Bankroll after bet
- `Status` - Bet status

**Tracking Features:**
- Record bet when placed (Milestone 3)
- Update outcome when match ends
- Calculate profit/loss automatically
- Update bankroll column
- Group by competition for performance analysis

---

## Milestone 2 Configuration

### Additional Config in `config.json`:

```json
{
  "live_score_api": {
    "api_key": "5vm1iY7mSjjK5ucr",
    "api_secret": "sdGH2ss0BWkJxOqDjMECLMZD5iobNBCf",
    "base_url": "https://live-score-api.com/api/v1",
    "api_plan": "trial",
    "rate_limit_per_day": 1500,
    "polling_interval_seconds": 10
  },
  "match_tracking": {
    "goal_detection_window": {
      "start_minute": 60,
      "end_minute": 74
    },
    "var_check_enabled": true,
    "zero_zero_exception": true,
    "zero_zero_exception_competitions": []
  },
  "bet_tracking": {
    "excel_path": "competitions/Competitions_Results_Odds_Stake.xlsx",
    "track_outcomes": true,
    "update_bankroll": true
  }
}
```

**Note:** `zero_zero_exception_competitions` will be automatically loaded from Excel file on startup.

---

## Milestone 2 Operational Flow

```
1. Bot Startup
   └── Read competitions from Excel → Map to Betfair IDs
   └── Load 0-0 exception competitions from Excel

2. Detection Loop (every 10 seconds)
   ├── Get in-play markets from Betfair
   ├── Filter: ONLY keep match-specific markets
   └── If found → Match with Live API

3. Matching
   ├── Get live matches from Live API
   ├── Match Betfair event with Live API match
   └── If match successful → Start tracking

4. Tracking Loop (every 5-10 seconds)
   ├── Update match data from Live API
   ├── Check current minute
   ├── Minute 60-74:
   │   ├── Detect new goals
   │   ├── Filter cancelled goals (VAR)
   │   ├── Check 0-0 exception (if competition in list)
   │   └── Mark QUALIFIED if conditions met
   └── Minute 75: If QUALIFIED → Ready for bet (Milestone 3)

5. Bet Tracking (when bet placed - Milestone 3)
   ├── Record bet to Excel
   ├── Update bankroll
   └── Track outcome when match ends
```

---

## Milestone 2 Deliverables

### ⏳ Source Code (In Progress)
- Market filter module
- Live Score API client
- Match tracker
- Qualification logic
- Bet tracker

### ⏳ Configuration
- Updated `config.json` with Live Score API settings
- Rate limiting configuration
- 0-0 exception configuration

### ⏳ Documentation
- API integration documentation
- Match tracking logic documentation
- Bet tracking documentation

### ⏳ Test Results (Pending)
- API connection test
- Matching logic test
- Goal detection test
- VAR handling test
- 0-0 exception test

---

# Project Structure

## Current Structure (Milestone 1)

```
BetfairItalyBot/
├── src/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── cert_login.py          # Certificate-based authentication
│   │   └── keep_alive.py          # Session keep-alive manager
│   ├── betfair/
│   │   ├── __init__.py
│   │   └── market_service.py      # Market data retrieval
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py              # Configuration loader
│   │   └── competition_mapper.py  # Excel to Betfair ID mapping
│   ├── core/
│   │   ├── __init__.py
│   │   └── logging_setup.py       # Logging configuration
│   └── main.py                    # Main entry point
├── config/
│   ├── config.json                # Configuration file
│   └── config.example.json        # Template configuration
├── certificates/
│   ├── client-2048.crt            # SSL certificate
│   └── client-2048.key             # Private key
├── competitions/
│   └── Competitions_Results_Odds_Stake.xlsx  # Competition list
├── logs/
│   └── betfair_bot.log            # Application logs
├── .env                            # Environment variables
├── requirements.txt                # Python dependencies
└── README.md                       # Setup instructions
```

## Planned Structure (Milestone 2)

```
BetfairItalyBot/
├── src/
│   ├── auth/                      # (Existing)
│   ├── betfair/
│   │   ├── market_service.py      # (Existing)
│   │   └── market_filter.py      # NEW - Phase 1
│   ├── football_api/              # NEW - Phase 2, 3
│   │   ├── __init__.py
│   │   ├── live_score_client.py   # Phase 2
│   │   ├── parser.py               # Phase 2
│   │   └── matcher.py              # Phase 3
│   ├── logic/                      # NEW - Phase 4
│   │   ├── __init__.py
│   │   ├── match_tracker.py        # Phase 4
│   │   └── qualification.py        # Phase 4
│   ├── tracking/                   # NEW - Phase 5
│   │   ├── __init__.py
│   │   ├── bet_tracker.py          # Phase 5
│   │   └── excel_writer.py         # Phase 5
│   ├── config/                     # (Existing)
│   ├── core/                        # (Existing)
│   └── main.py                      # UPDATE - integrate all phases
├── config/
│   └── config.json                  # UPDATE - add Live Score API config
└── ... (other files)
```

---

# Configuration Guide

## Milestone 1 Configuration

See `MILESTONE1_REPORT.md` for detailed configuration.

## Milestone 2 Additional Configuration

### Live Score API Configuration

```json
{
  "live_score_api": {
    "api_key": "5vm1iY7mSjjK5ucr",
    "api_secret": "sdGH2ss0BWkJxOqDjMECLMZD5iobNBCf",
    "base_url": "https://live-score-api.com/api/v1",
    "api_plan": "trial",
    "rate_limit_per_day": 1500,
    "polling_interval_seconds": 10
  }
}
```

**Configuration Options:**
- `api_plan`: "trial" (1500 requests/day) or "paid" (14500 requests/day)
- `rate_limit_per_day`: Auto-set based on plan, but can be overridden
- `polling_interval_seconds`: How often to poll Live API for match updates

### Match Tracking Configuration

```json
{
  "match_tracking": {
    "goal_detection_window": {
      "start_minute": 60,
      "end_minute": 74
    },
    "var_check_enabled": true,
    "zero_zero_exception": true,
    "zero_zero_exception_competitions": []
  }
}
```

**Configuration Options:**
- `goal_detection_window`: Minutes to monitor for goals
- `var_check_enabled`: Enable/disable VAR (cancelled goals) checking
- `zero_zero_exception`: Enable/disable 0-0 exception
- `zero_zero_exception_competitions`: Auto-loaded from Excel (Result = "0-0")

### Bet Tracking Configuration

```json
{
  "bet_tracking": {
    "excel_path": "competitions/Competitions_Results_Odds_Stake.xlsx",
    "track_outcomes": true,
    "update_bankroll": true
  }
}
```

**Configuration Options:**
- `excel_path`: Path to Excel file for bet tracking
- `track_outcomes`: Enable/disable outcome tracking
- `update_bankroll`: Enable/disable bankroll updates

---

## Important Notes

### Rate Limiting

- **Trial Plan**: 1500 requests/day (~62 requests/hour)
- **Paid Plan**: 14500 requests/day (~604 requests/hour)
- Bot automatically calculates rate limit based on `api_plan`
- Rate limiter tracks requests and enforces limits

### 0-0 Exception

- **Important**: Only applies to competitions specified in Excel file
- Bot reads Excel file to identify competitions with `Result = "0-0"`
- If competition is NOT in exception list, 0-0 score will NOT qualify
- This is a critical requirement from the client

### VAR Handling

- Bot checks for cancelled goals in goal timeline
- Cancelled goals are excluded from qualification check
- Only valid (non-cancelled) goals in 60-74 window count

---

## Next Steps

### Milestone 2 Implementation Order

1. **Phase 1**: Filter Market Types (Priority: High)
2. **Phase 2**: Live Score API Integration
3. **Phase 3**: Matching Logic
4. **Phase 4**: Match Tracking & Goal Detection
5. **Phase 5**: Bet Tracking & Excel Export

### Milestone 3 (Future)

- Lay bet execution logic
- Odds checking and spread calculation
- Stake calculation based on bankroll percentage
- Order placement and management

### Milestone 4 (Future)

- Notifications (email/Telegram/Slack)
- Enhanced logging and reporting
- Final testing and documentation
- User interface (if requested)

---

**Document Version:** 1.0  
**Last Updated:** November 12, 2025  
**Status:** Milestone 1 ✅ Complete | Milestone 2 🔄 In Progress

