# Betfair Italy Bot

Automated betting bot for Betfair Exchange (Italy) - Milestone 1: Authentication & Market Detection

## Overview

This bot connects to Betfair Italy Exchange API, authenticates using certificate-based login, and detects live football markets from selected competitions.

## Requirements

- Python 3.10 or higher
- Betfair Italy Exchange account
- Betfair Application Key
- SSL Certificate (.crt and .key files) for non-interactive login

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

1. Edit `config/config.json` and fill in:
   - `betfair.app_key`: Your Betfair Application Key
   - `betfair.username`: Your Betfair username
   - `betfair.certificate_path`: Path to your .crt file
   - `betfair.key_path`: Path to your .key file

2. Create `.env` file in project root and fill in:
   ```bash
   BETFAIR_APP_KEY=your_app_key_here
   BETFAIR_USERNAME=your_username_here
   BETFAIR_PASSWORD=your_password_here
   BETFAIR_CERT_PATH=path/to/client-2048.crt
   BETFAIR_KEY_PATH=path/to/client-2048.key
   ```

   Or set environment variables directly:
   ```bash
   set BETFAIR_PASSWORD=your_password_here
   ```

### 4. Configure Monitoring

Edit `config/config.json` under `monitoring` section:
- `competition_ids`: List of competition IDs to monitor (empty = all)
- `polling_interval_seconds`: How often to check for markets (default: 10)
- `in_play_only`: Only detect in-play markets (default: true)

## Running the Bot

### Activate Virtual Environment

```bash
cd "D:\Projects\UpWork\Andrea Natali\BetfairItalyBot"
.venv\Scripts\activate
```

### Run Milestone 1

```bash
python src\main.py
```

The bot will:
1. Load configuration
2. Authenticate with Betfair
3. Start keep-alive manager
4. Begin detecting in-play markets
5. Log all activities to `logs/betfair_bot.log`

### Stop the Bot

Press `Ctrl+C` to stop gracefully.

## Project Structure

```
BetfairItalyBot/
├── config/
│   └── config.json            # Configuration file
├── src/
│   ├── auth/
│   │   ├── cert_login.py      # Certificate-based authentication
│   │   └── keep_alive.py       # Session keep-alive manager
│   ├── betfair/
│   │   └── market_service.py   # Market data retrieval
│   ├── config/
│   │   └── loader.py           # Configuration loader
│   ├── core/
│   │   └── logging_setup.py    # Logging configuration
│   └── main.py                 # Main entry point
├── logs/                       # Log files (auto-created)
├── .venv/                      # Virtual environment
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Logging

Logs are written to:
- File: `logs/betfair_bot.log` (with rotation)
- Console: Enabled by default

Log format includes:
- Timestamp
- Log level
- Module name
- Message

## Milestone 1 Deliverables

✅ Secure connection to Betfair Exchange (Italy)  
✅ Certificate-based authentication  
✅ Session management with keep-alive  
✅ Live market detection for football  
✅ Filtering by competitions  
✅ Detailed logging  

## Troubleshooting

### Login Fails

- Check certificate files exist and paths are correct
- Verify certificate is uploaded to Betfair account
- Ensure username/password are correct
- Check App Key is valid for Italian Exchange

### No Markets Found

- Verify competitions are currently in-play
- Check `competition_ids` in config (empty = all competitions)
- Ensure `in_play_only` is set correctly

### Session Expired

- Keep-alive should prevent this, but if it happens:
- The bot will need to re-authenticate
- Check keep-alive interval in config

## Next Steps (Future Milestones)

- Milestone 2: Live data integration & match logic
- Milestone 3: Lay bet execution logic
- Milestone 4: Notifications & final testing

## Support

For issues or questions, refer to:
- Betfair API Documentation: https://betfair-developer-docs.atlassian.net/
- Project checklist: `Tài liệu/checklist.txt`

