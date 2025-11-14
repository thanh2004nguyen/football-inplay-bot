# Setup and Test Guide

This guide will help you set up and test the Betfair Italy Bot.

---

## 1. Download Code from GitHub

1. Clone the repository or download as ZIP
2. Extract to a folder on your computer

---

## 2. Setup Files

After downloading the code, you need to add the following files to the project:

### Add Certificates
- Place your Betfair certificates in the `certificates/` folder:
  - `client-2048.crt`
  - `client-2048.key`

### Add Configuration File
- Place `config.json` in the `config/` folder
- This file contains your API credentials and settings

**Note:** These files are not included in the repository for security reasons. You will receive them separately.

---

## 3. Setup Environment

### Install Python
- Install Python **3.12 or higher**
- Download from: https://www.python.org/downloads/

### Create Virtual Environment

Open terminal/command prompt in the project folder and run:

```bash
python -m venv .venv
```

### Activate Virtual Environment

**Windows:**
```bash
.venv\Scripts\activate
```

**Mac/Linux:**
```bash
source .venv/bin/activate
```

You should see `(.venv)` at the beginning of your command prompt.

### Install Dependencies

```bash
pip install -r requirements.txt
```

Wait for all packages to install.

---

## 4. Run Test Mode

Test mode allows you to test the bot logic **without placing real bets** or deducting real money.

### Step 1: Load Test Scenario

```bash
python tests/load_test_scenario.py scenario_combined_bet_and_skip
```

This will:
- Enable test mode automatically
- Load mock data for testing
- Configure the bot to test both bet placement and skipped matches

### Step 2: Run the Bot

```bash
python src/main.py
```

### Expected Results

**Console Output:**
```
============================================================
TEST MODE ENABLED - Using mock services
============================================================
⚠️  TEST MODE ENABLED
   Bot will NOT place real bets
   All API calls will be simulated
============================================================

...

✅ BET PLACED: Team A v Team B
   Market: Over/Under 2.5 Goals
   Lay @ 2.2, Stake: 41.67 EUR, Liability: 50.0 EUR
   BetId: TEST_...

⚠ Could not place bet for Team K v Team L
```

**Files Created/Updated:**
- `competitions/Bet_Records.xlsx` - Contains 1 bet record (Team A v Team B)
- `competitions/Skipped Matches.xlsx` - Contains 1 skipped match (Team K v Team L)

**Notifications:**
- Sound notification: `success.mp3` will play when bet is placed

### View Test Results

After the test completes, you can open the Excel files to see the results:

1. **Bet_Records.xlsx**: Shows the bet that was placed
   - Bet_ID: `TEST_...`
   - Match: Team A v Team B
   - Stake, Odds, Bankroll, etc.

2. **Skipped Matches.xlsx**: Shows the match that was skipped
   - Match: Team K v Team L
   - Reason: Spread too wide
   - Market conditions details

**To stop the bot:** Press `Ctrl+C` in the terminal

---

## 4.5. Check Account Balance

You can verify that the bot can connect to your Betfair account and retrieve your account balance.

### Run Account Balance Test

```bash
python tests/test_account_balance.py
```

### Expected Result

**Success:**
```
============================================================
Betfair Account Balance Test
============================================================

[1/3] Loading configuration...
✓ Configuration loaded

[2/3] Authenticating with Betfair...
✓ Login successful

[3/3] Retrieving account balance...

============================================================
ACCOUNT BALANCE INFORMATION
============================================================

💰 Available to Bet: 1000.0 EUR
💵 Total Balance: 1000.0 EUR
📊 Exposure: 0.0 EUR
💼 Retained Commission: 0.0 EUR
📈 Exposure Limit: 10000.0 EUR
🎯 Discount Rate: 0.0%
⭐ Points Balance: 0

✅ Account has sufficient balance for betting
   Minimum bet stake: 2 EUR (typical)
   ✅ Balance is sufficient for minimum bet
```

**Failure:**
- Check your credentials in `config/config.json`
- Verify certificate files exist
- Check your Betfair account status

**Note:** This test works in both test mode and real mode. In test mode, it will show the mock balance from test scenario.

---

## 5. Run in Real Mode (After Testing)

Once you've verified the test mode works correctly, you can run the bot in real mode to place actual bets.

### Step 1: Disable Test Mode

1. Open `config/config.json`
2. Find the `test_mode` section
3. Change `"enabled": true` to `"enabled": false`

```json
{
  "test_mode": {
    "enabled": false,  // ← Change to false
    ...
  }
}
```

### Step 2: Verify Credentials

Make sure your credentials in `config/config.json` are correct:
- Betfair API credentials
- Live Score API credentials
- Email/Telegram settings (if using notifications)

### Step 3: Check Account Balance

Ensure you have sufficient balance in your Betfair account.

### Step 4: Run the Bot

```bash
python src/main.py
```

### Expected Results

**Console Output:**
- You will **NOT** see "TEST MODE ENABLED" message
- Bot will connect to real Betfair API
- Bot will monitor live matches
- When conditions are met, bot will place **real bets**
- Real money will be deducted from your account

**Files Updated:**
- `Bet_Records.xlsx` - Real bet records
- `Skipped Matches.xlsx` - Real skipped matches

**Notifications:**
- Sound notifications for bet placed/matched
- Email notifications (if enabled)
- Telegram notifications (if enabled)

---

## Troubleshooting

### Issue: "Module not found" error

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: "Excel file not found"

**Solution:**
- Make sure `competitions/Competitions_Results_Odds_Stake.xlsx` exists
- Check the file path in config

### Issue: "Sound file not found"

**Solution:**
- Create `sounds/` folder in project root
- Add `success.mp3` and `ping.mp3` files
- Or disable sound notifications in config

### Issue: Bot not placing bets in test mode

**Solution:**
- Check that `test_mode.enabled = true` in config
- Verify Excel file has test data
- Check console logs for error messages

### Issue: Bet_Time or Timestamp showing `####` in Excel

**Solution:**
- Close Excel file
- Run: `python tests/fix_excel_datetime.py`
- Reopen Excel file

---

## Important Notes

### Test Mode vs Real Mode

- **Test Mode** (`test_mode.enabled = true`):
  - ✅ Safe - No real bets placed
  - ✅ No money deducted
  - ✅ All API calls simulated
  - ✅ Perfect for testing logic

- **Real Mode** (`test_mode.enabled = false`):
  - ⚠️ **Real bets will be placed**
  - ⚠️ **Real money will be deducted**
  - ⚠️ **Use with caution**
  - ✅ Only use after thorough testing

### Before Running in Real Mode

- [ ] Test mode works correctly
- [ ] Understand the bot's logic
- [ ] Have sufficient account balance
- [ ] Monitor the bot during first runs
- [ ] Verify Excel file has correct data

---

## Summary

1. **Download code** from GitHub
2. **Add certificates and config.json** to project
3. **Setup Python environment** (3.12+)
4. **Install dependencies** (`pip install -r requirements.txt`)
5. **Run test mode** to verify everything works
6. **Switch to real mode** only after testing is successful

**Remember:** Always test in test mode first before running in real mode!

---

## Need Help?

If you encounter any issues:
1. Check the console logs for error messages
2. Verify all files are in the correct locations
3. Ensure all credentials are correct
4. Review the troubleshooting section above

Good luck with your testing! 🚀

