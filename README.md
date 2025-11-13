# Betfair Italy Bot

Automated betting bot for Betfair Exchange (Italy) - Complete Implementation (Milestones 1-4)

## Overview

This bot automates lay betting on Betfair Italy Exchange for football matches. It monitors live matches, detects qualification conditions (goals between 60-74 minutes), and automatically places lay bets on Over X.5 markets when conditions are met.

**Key Features:**
- ✅ Certificate-based authentication with automatic session management
- ✅ Live match detection and tracking from Live Score API
- ✅ Automatic qualification detection (goals in 60-74 minute window)
- ✅ Automatic lay bet placement on Over X.5 markets
- ✅ Sound and email notifications for important events
- ✅ Comprehensive logging and error handling
- ✅ Rate limiting for both Betfair and Live Score APIs
- ✅ Excel tracking for bet records and skipped matches

## Requirements

- Python 3.10 or higher
- Betfair Italy Exchange account
- Betfair Application Key
- SSL Certificate (.crt and .key files) for non-interactive login
- Live Score API account (trial or paid plan)
- Excel file: `competitions/Competitions_Results_Odds_Stake.xlsx` (for stake calculation)

## Setup Instructions

### 1. Install Dependencies

```bash
# Activate virtual environment
.venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 2. Configure Certificate

1. Generate a self-signed certificate (if not already done):
   ```bash
   openssl genrsa -out client-2048.key 2048
   openssl req -new -key client-2048.key -out client-2048.csr
   openssl x509 -req -days 365 -in client-2048.csr -signkey client-2048.key -out client-2048.crt
   ```

2. Upload the certificate to your Betfair account:
   - Go to: https://myaccount.betfair.it/accountdetails/mysecurity?showAPI=1
   - Scroll to "Automated Betting Program Access"
   - Upload your `client-2048.crt` file

### 3. Configure the Bot

1. Copy `config/config.example.json` to `config/config.json`:
   ```bash
   copy config\config.example.json config\config.json
   ```

2. Edit `config/config.json` and fill in required settings:

   **Betfair Settings:**
   - `betfair.app_key`: Your Betfair Application Key
   - `betfair.username`: Your Betfair username
   - `betfair.password`: Your Betfair password (or set as environment variable)
   - `betfair.certificate_path`: Path to your .crt file (default: `certificates/client-2048.crt`)
   - `betfair.key_path`: Path to your .key file (default: `certificates/client-2048.key`)

   **Live Score API Settings:**
   - `live_score_api.api_key`: Your Live Score API key
   - `live_score_api.api_secret`: Your Live Score API secret
   - `live_score_api.api_plan`: "trial" or "paid" (affects rate limits)
   - `live_score_api.rate_limit_per_day`: 1500 (trial) or 14500 (paid)
   - `live_score_api.polling_interval_seconds`: 60 (recommended)

   **Notifications (Optional):**
   - `notifications.sound_enabled`: true/false
   - `notifications.email_enabled`: true/false
   - `notifications.email.*`: SMTP settings for email alerts

   **Note:** You can also set `BETFAIR_PASSWORD` as environment variable instead of putting it in config.json:
   ```bash
   set BETFAIR_PASSWORD=your_password_here
   ```

3. Prepare Excel file:
   - Place `Competitions_Results_Odds_Stake.xlsx` in `competitions/` folder
   - This file contains stake percentages for each competition and score
   - The bot reads this file to determine stake when placing bets

4. Prepare sound files (optional):
   - Place `success.mp3` and `ping.mp3` in `sounds/` folder
   - These are played when bets are placed and matched

## Running the Bot

### Method 1: Using Command Line

1. Activate virtual environment:
   ```bash
   cd "D:\Projects\UpWork\Andrea Natali\BetfairItalyBot"
   .venv\Scripts\activate
   ```

2. Run the bot:
   ```bash
   python src\main.py
   ```

### Method 2: Using Startup Script (Windows)

1. Double-click `scripts/run_bot.cmd` (or create one based on `run_milestone1.cmd`)

### What the Bot Does

The bot will:
1. Load and validate configuration
2. Authenticate with Betfair Italy Exchange
3. Initialize Live Score API client
4. Start keep-alive manager (maintains session)
5. Begin monitoring live football matches
6. Track matches from minute 60
7. Detect goals in 60-74 minute window
8. Qualify matches based on conditions
9. Place lay bets automatically at minute 75
10. Log all activities to `logs/betfair_bot.log`
11. Export bet records to `competitions/Bet_Records.xlsx`
12. Export skipped matches to `competitions/Skipped Matches.xlsx`

### Stop the Bot

Press `Ctrl+C` to stop gracefully. The bot will:
- Complete current operations
- Save any pending data
- Close connections properly

## Project Structure

```
BetfairItalyBot/
├── config/
│   ├── config.json             # Main configuration file
│   └── config.example.json     # Configuration template
├── certificates/               # SSL certificates for Betfair
│   ├── client-2048.crt
│   └── client-2048.key
├── competitions/               # Excel files
│   ├── Competitions_Results_Odds_Stake.xlsx  # Input: Stake percentages
│   ├── Bet_Records.xlsx        # Output: Bet records
│   └── Skipped Matches.xlsx    # Output: Skipped matches log
├── sounds/                     # Sound notification files
│   ├── success.mp3             # Played when bet is placed
│   └── ping.mp3                # Played when bet is matched
├── logs/                       # Log files (auto-created)
│   └── betfair_bot.log
├── scripts/
│   └── run_milestone1.cmd      # Windows startup script
├── src/
│   ├── auth/                   # Authentication
│   │   ├── cert_login.py       # Certificate-based login
│   │   └── keep_alive.py       # Session keep-alive
│   ├── betfair/                # Betfair API integration
│   │   ├── market_service.py    # Market data retrieval
│   │   ├── betting_service.py  # Bet placement
│   │   ├── market_filter.py    # Market filtering
│   │   └── price_ladder.py     # Price calculations
│   ├── football_api/           # Live Score API integration
│   │   ├── live_score_client.py # API client with rate limiting
│   │   ├── parser.py           # Response parsing
│   │   └── matcher.py          # Match matching logic
│   ├── logic/                  # Core business logic
│   │   ├── match_tracker.py    # Match tracking
│   │   ├── qualification.py    # Qualification logic
│   │   └── bet_executor.py     # Bet execution
│   ├── tracking/               # Data tracking
│   │   ├── bet_tracker.py      # In-memory bet tracking
│   │   ├── excel_writer.py     # Excel export
│   │   └── skipped_matches_writer.py
│   ├── notifications/          # Notifications (Milestone 4)
│   │   ├── sound_notifier.py   # Sound notifications
│   │   └── email_notifier.py   # Email notifications
│   ├── config/                 # Configuration management
│   │   ├── loader.py           # Config loader
│   │   └── competition_mapper.py
│   ├── core/
│   │   └── logging_setup.py    # Logging configuration
│   └── main.py                 # Main entry point
├── .venv/                      # Virtual environment
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── Milestone1.md              # Milestone 1 report
├── Milestone2.md              # Milestone 2 report
├── Milestone3.md              # Milestone 3 report
└── Milestone4.md              # Milestone 4 report
```

## How It Works

### Bot Workflow

1. **Initialization:**
   - Loads configuration from `config.json`
   - Authenticates with Betfair using certificate
   - Initializes Live Score API client
   - Sets up logging and notifications

2. **Market Detection:**
   - Polls Betfair API every 10 seconds (configurable)
   - Filters for in-play football markets
   - Matches with Live Score API data

3. **Match Tracking:**
   - Tracks matches from minute 60
   - Monitors for goals in 60-74 minute window
   - Applies qualification logic (goals, VAR, 0-0 exception)
   - Early discard at minute 60 if score won't qualify

4. **Bet Execution:**
   - At minute 75, checks market conditions:
     - Spread ≤ 4 ticks
     - Odds within range (1.5 - 10.0)
     - Sufficient liquidity
   - Reads stake percentage from Excel file
   - Places lay bet on Over X.5 (+2 ticks offset)
   - Records bet in Excel

5. **Notifications:**
   - Plays sound when bet is placed
   - Plays sound when bet is matched
   - Sends email for critical errors (maintenance, terms)

## Logging

Logs are written to:
- **File:** `logs/betfair_bot.log` (with rotation, max 10MB, 5 backups)
- **Console:** Enabled by default (can be disabled in config)

Log format includes:
- Timestamp
- Log level (DEBUG, INFO, WARNING, ERROR)
- Module name
- Message

## Configuration Guide

### Key Configuration Sections

**`betfair`**: Betfair API credentials and endpoints  
**`monitoring`**: Which competitions to monitor, polling intervals  
**`live_score_api`**: Live Score API keys, rate limits, polling intervals  
**`match_tracking`**: Goal detection window, VAR check, 0-0 exception  
**`bet_execution`**: Odds thresholds, spread limits, stake settings  
**`notifications`**: Sound and email notification settings  
**`betfair_api`**: Data weight limits (for API rate limiting)  

See `config/config.example.json` for detailed comments and explanations.

## Troubleshooting

### Login Fails

- ✅ Check certificate files exist and paths are correct in `config.json`
- ✅ Verify certificate is uploaded to Betfair account: https://myaccount.betfair.it/accountdetails/mysecurity?showAPI=1
- ✅ Ensure username/password are correct
- ✅ Check App Key is valid for Italian Exchange
- ✅ If maintenance error: Check https://www.betfair.it for maintenance status
- ✅ Bot will automatically retry login (every 60 seconds by default)

### No Markets Found

- ✅ Verify competitions are currently in-play
- ✅ Check `competition_ids` in config (empty = all competitions)
- ✅ Ensure `in_play_only` is set to `true`
- ✅ Check if Excel file has competition mappings

### Rate Limit Errors

**Live Score API:**
- ✅ Check `rate_limit_per_day` matches your plan (1500 trial, 14500 paid)
- ✅ Increase `polling_interval_seconds` if hitting limits
- ✅ Bot automatically tracks and enforces limits

**Betfair API:**
- ✅ Bot automatically validates data weight (190 points max)
- ✅ Requests are automatically split if needed
- ✅ No action required, handled automatically

### Bet Not Placed

- ✅ Check account balance is sufficient
- ✅ Verify market conditions (spread, odds, liquidity)
- ✅ Check Excel file has stake percentage for that competition/score
- ✅ Review `competitions/Skipped Matches.xlsx` for reasons
- ✅ Check logs for detailed error messages

### Sound Notifications Not Working

- ✅ Verify `sound_enabled: true` in config
- ✅ Check sound files exist in `sounds/` folder
- ✅ Install `playsound3`: `pip install playsound3`
- ✅ Check logs for error messages

### Email Notifications Not Working

- ✅ Verify `email_enabled: true` in config
- ✅ For Gmail: Use App Password (not regular password)
- ✅ Enable 2-Step Verification: https://myaccount.google.com/apppasswords
- ✅ Check SMTP settings (server, port, credentials)
- ✅ Check logs for SMTP error messages

## API Documentation References

### Betfair API
- **Main Documentation:** https://betfair-developer-docs.atlassian.net/
- **Market Data Request Limits:** [Market Data Request Limits](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687478/Market+Data+Request+Limits)
- **Non-Interactive Bot Login:** Certificate-based authentication guide
- **Betting on Italian Exchange:** Italy-specific endpoints and requirements

### Live Score API
- **Documentation:** https://livescore-api.com/documentation
- **Rate Limits:** Configured in `config.json` (1500/day trial, 14500/day paid)

## Milestones Completed

- ✅ **Milestone 1:** Authentication & Market Detection
- ✅ **Milestone 2:** Live Data Integration & Match Logic
- ✅ **Milestone 3:** Lay Bet Execution Logic
- ✅ **Milestone 4:** Notifications, Logging & Final Testing

See individual milestone reports (`Milestone1.md`, `Milestone2.md`, `Milestone3.md`, `Milestone4.md`) for detailed information.

## Support

For detailed information:
- **Milestone Reports:** See `Milestone1.md` through `Milestone4.md`
- **Configuration:** See `config/config.example.json` for all options
- **Betfair API Docs:** https://betfair-developer-docs.atlassian.net/

