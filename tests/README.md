# Test Scripts

This directory contains test scripts to verify various components of the Betfair Italy Bot.

## Available Tests

### 1. `test_account_balance.py`
**Purpose:** Check Betfair account balance and funds information

**What it tests:**
- ✅ Betfair authentication (certificate-based login)
- ✅ Account balance retrieval
- ✅ Available funds for betting
- ✅ Balance sufficiency check (minimum 2 EUR)

**Usage:**
```bash
# From project root
cd "D:\Projects\UpWork\Andrea Natali\BetfairItalyBot"
.venv\Scripts\activate
python tests\test_account_balance.py
```

**Output:**
- Available to Bet balance
- Total Balance
- Exposure
- Retained Commission
- Full account funds details

---

### 2. `test_betfair_connection.py`
**Purpose:** Test connectivity to Betfair Italy Exchange

**What it tests:**
- ✅ Betfair website accessibility
- ✅ API endpoint connectivity
- ✅ Certificate authentication
- ✅ Login functionality

**Usage:**
```bash
python tests\test_betfair_connection.py
```

---

### 3. `test_email_notifications.py`
**Purpose:** Test email notification functionality

**What it tests:**
- ✅ Email configuration loading
- ✅ Gmail SMTP connection
- ✅ Email sending capability
- ✅ Error handling

**Usage:**
```bash
python tests\test_email_notifications.py
```

**Note:** Requires email configuration in `config/config.json`:
```json
"notifications": {
  "email_enabled": true,
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your_email@gmail.com",
    "sender_password": "your_app_password",
    "recipient_email": "recipient@example.com"
  }
}
```

---

### 4. `test_sound_notifications.py`
**Purpose:** Test sound notification functionality

**What it tests:**
- ✅ Sound file existence
- ✅ Sound playback capability
- ✅ `playsound3` library availability

**Usage:**
```bash
python tests\test_sound_notifications.py
```

**Note:** Requires sound files in `sounds/` directory:
- `sounds/success.mp3` (bet placed sound)
- `sounds/ping.mp3` (bet matched sound)

---

## Running All Tests

### Method 1: Run individually
```bash
# Activate virtual environment first
.venv\Scripts\activate

# Run each test
python tests\test_account_balance.py
python tests\test_betfair_connection.py
python tests\test_email_notifications.py
python tests\test_sound_notifications.py
```

### Method 2: Run from project root
```bash
cd "D:\Projects\UpWork\Andrea Natali\BetfairItalyBot"
.venv\Scripts\activate
python tests\test_account_balance.py
```

---

## Prerequisites

1. **Virtual Environment:** Activate before running tests
   ```bash
   .venv\Scripts\activate
   ```

2. **Configuration:** Ensure `config/config.json` is properly configured:
   - Betfair credentials (app_key, username, password)
   - Certificate paths
   - Email settings (for email test)
   - Sound settings (for sound test)

3. **Dependencies:** All required packages from `requirements.txt` must be installed

---

## Troubleshooting

### Import Errors
- **Error:** `ModuleNotFoundError: No module named 'config'`
- **Solution:** Make sure you're running from project root, not from `tests/` directory

### Configuration Errors
- **Error:** `Configuration file not found`
- **Solution:** Ensure `config/config.json` exists and is properly formatted

### Certificate Errors
- **Error:** `Certificate file not found`
- **Solution:** Check certificate paths in `config/config.json` and ensure files exist

### Authentication Errors
- **Error:** `Login failed`
- **Solution:** 
  - Verify username and password
  - Check certificate is uploaded to Betfair account
  - Verify app_key is correct
  - Check if Betfair is under maintenance

---

## Test Results

### Expected Results

**test_account_balance.py:**
- ✅ Login successful
- ✅ Account balance retrieved
- ✅ Balance information displayed

**test_betfair_connection.py:**
- ✅ Website accessible
- ✅ API endpoints reachable
- ✅ Authentication working

**test_email_notifications.py:**
- ✅ Email sent successfully
- ✅ Test email received

**test_sound_notifications.py:**
- ✅ Sound files found
- ✅ Sounds played successfully

---

## Notes

- All tests use the same configuration as the main bot (`config/config.json`)
- Tests are independent and can be run in any order
- Tests do not modify any bot data or place actual bets
- `test_account_balance.py` only reads account information, does not place bets

