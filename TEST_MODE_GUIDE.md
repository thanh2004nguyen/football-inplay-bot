# Test Mode Guide

This guide explains how to use the bot's test mode to safely test all functionality without placing real bets.

---

## What is Test Mode?

Test mode is a safe testing environment that:
- ✅ **Simulates all API calls** (Betfair, Live Score)
- ✅ **Runs all bot logic** (matching, qualification, bet placement)
- ✅ **Does NOT place real bets** (no financial transactions)
- ✅ **Does NOT deduct real money** from your account
- ✅ **Tests notifications** (sound, email, Telegram)

**Important:** When `test_mode.enabled = true`, the bot will **NOT** place real bets, even if all conditions are met.

---

## How to Enable Test Mode

### Step 1: Open Configuration File

Edit `config/config.json`:

```json
{
  "test_mode": {
    "enabled": true,  // ← Change to true
    "simulate_bet_placement": true,
    "simulate_bet_matched": false,
    "log_bet_details": true,
    "mock_bet_id_prefix": "TEST_"
  }
}
```

### Step 2: Verify Test Mode is Active

When you run the bot, you should see:

```
============================================================
TEST MODE ENABLED - Using mock services
============================================================
⚠️  TEST MODE ENABLED
   Bot will NOT place real bets
   All API calls will be simulated
============================================================
```

If you see this message, test mode is active.

---

## Test Mode Configuration Options

### `enabled` (boolean)
- `true`: Enable test mode (no real bets)
- `false`: Disable test mode (real bets will be placed)

### `simulate_bet_matched` (boolean)
- `false`: Bet is placed but not matched (tests bet placement only)
- `true`: Bet is placed AND matched immediately (tests bet matched notifications)

### `mock_bet_id_prefix` (string)
- Prefix for mock bet IDs (e.g., `"TEST_"` → Bet IDs like `TEST_1234567890_1`)

### `log_bet_details` (boolean)
- `true`: Log detailed bet information (recommended for testing)

---

## Prerequisites for Testing

### 1. Excel File Must Have Test Data

The Excel file `competitions/Competitions_Results_Odds_Stake.xlsx` must contain:
- **Competition-Live**: Competition identifier (e.g., `"4_Serie A"`)
- **Result**: Score at minute 75 (e.g., `"1-1"`, `"0-0"`)
- **Stake**: Stake percentage (e.g., `5.0`)

**Example:**
| Competition-Live | Competition-Betfair | Result | Stake |
|----------------|-------------------|--------|-------|
| 4_Serie A | 81_Italian Serie A | 1-1 | 5.0 |

**If Excel data is missing:**
- Bot will log: `"Score 1-1 not found in Excel for 4_Serie A"`
- Bet will NOT be placed

### 2. Sound Files Must Exist

Required files in `sounds/` directory:
- `success.mp3` (bet placed sound)
- `ping.mp3` (bet matched sound)

**If sound files are missing:**
- Sound notifications will not play
- Bot will continue running (no error)

### 3. Dependencies Installed

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

---

## Quick Start: Using Test Scenarios

The bot includes pre-configured test scenarios. This is the easiest way to test.

### Step 1: Load a Test Scenario

```bash
python tests/load_test_scenario.py scenario_1_happy_path
```

This will:
- Set `test_mode.enabled = true`
- Load mock data for the scenario
- Update `config.json` automatically

### Step 2: Run the Bot

```bash
python src/main.py
```

### Step 3: Check Results

- **Console**: Look for "✅ BET PLACED" message
- **Logs**: Check `logs/betfair_bot.log`
- **Excel**: Check `competitions/Bet_Records.xlsx` for bet records
- **Sound**: Listen for notification sounds

---

## Available Test Scenarios

### Scenario 1: Happy Path (Bet Placed, NOT Matched)
```bash
python tests/load_test_scenario.py scenario_1_happy_path
python src/main.py
```

**Tests:**
- ✅ Match detection and matching
- ✅ Goal detection in 60-74 window
- ✅ Qualification logic
- ✅ Market conditions check
- ✅ Stake calculation from Excel
- ✅ Bet placement (mock)
- ✅ Excel writing
- ✅ **Sound notification: Bet placed** 🔔

**Expected:** Bet placed successfully with Bet_ID = "TEST_...", sound notification played

---

### Scenario 1b: Happy Path (Bet Placed AND Matched)
```bash
python tests/load_test_scenario.py scenario_1b_happy_path_matched
python src/main.py
```

**Tests:**
- ✅ All tests from Scenario 1
- ✅ **Sound notification: Bet placed** 🔔
- ✅ **Sound notification: Bet matched** 🔔
- ✅ **Telegram notification: Bet matched** 📱

**Expected:** 
- Bet placed successfully
- Bet matched immediately (sizeMatched > 0)
- Both sound notifications played
- Telegram notification sent (if enabled)

---

### Scenario 2: Early Discard (Out of Target)
```bash
python tests/load_test_scenario.py scenario_2_early_discard
python src/main.py
```

**Tests:**
- ✅ Early discard logic (score 0-3 at minute 60)
- ✅ Match skipped (not qualified)

**Expected:** Match detected but skipped (no bet placed)

---

### Scenario 3: VAR Cancelled Goal
```bash
python tests/load_test_scenario.py scenario_3_var_cancelled_goal
python src/main.py
```

**Tests:**
- ✅ VAR cancelled goal detection
- ✅ Match skipped (no valid goal in window)

**Expected:** Match detected but skipped (no bet placed)

---

### Scenario 4: 0-0 Exception
```bash
python tests/load_test_scenario.py scenario_4_zero_zero_exception
python src/main.py
```

**Tests:**
- ✅ 0-0 exception handling
- ✅ Bet placement for 0-0 score

**Expected:** Bet placed for 0-0 score (if competition is in exception list)

---

### Scenario 5: Odds Too Low
```bash
python tests/load_test_scenario.py scenario_5_odds_too_low
python src/main.py
```

**Tests:**
- ✅ Odds check (Under X.5 best back price)
- ✅ Match skipped if odds < min_odds

**Expected:** Match detected but skipped (odds too low)

---

### Scenario 6: Spread Too Wide
```bash
python tests/load_test_scenario.py scenario_6_spread_too_wide
python src/main.py
```

**Tests:**
- ✅ Spread calculation (Over X.5 best lay - Over X.5 best back)
- ✅ Match skipped if spread > max_spread_ticks

**Expected:** Match detected but skipped (spread too wide)

---

### Scenario 7: No Liquidity
```bash
python tests/load_test_scenario.py scenario_7_no_liquidity
python src/main.py
```

**Tests:**
- ✅ Liquidity check (minimum size available)
- ✅ Match skipped if insufficient liquidity

**Expected:** Match detected but skipped (no liquidity)

---

### Scenario 8: Insufficient Funds
```bash
python tests/load_test_scenario.py scenario_8_insufficient_funds
python src/main.py
```

**Tests:**
- ✅ Account balance check
- ✅ Match skipped if insufficient funds

**Expected:** Match detected but skipped (insufficient funds)

---

### Scenario 9: No Goal in Window
```bash
python tests/load_test_scenario.py scenario_9_no_goal_in_window
python src/main.py
```

**Tests:**
- ✅ Goal window check (60-74 minutes)
- ✅ Match skipped if no goal in window

**Expected:** Match detected but skipped (no goal in window)

---

### Scenario 10: Market Unavailable
```bash
python tests/load_test_scenario.py scenario_10_market_unavailable
python src/main.py
```

**Tests:**
- ✅ Market availability check
- ✅ Match skipped if market not found

**Expected:** Match detected but skipped (market unavailable)

---

## Running All Test Scenarios

To run all test scenarios automatically:

```bash
python tests/run_all_tests.py
```

This will:
1. Load each scenario
2. Run the bot
3. Check results
4. Generate a test report

---

## Manual Testing (Without Scenarios)

If you want to test with your own data:

### Step 1: Enable Test Mode

Edit `config/config.json`:
```json
{
  "test_mode": {
    "enabled": true
  }
}
```

### Step 2: Ensure Excel Has Data

Make sure `competitions/Competitions_Results_Odds_Stake.xlsx` has:
- Competition-Live: Your competition identifier
- Result: The score you want to test
- Stake: Stake percentage

### Step 3: Run the Bot

```bash
python src/main.py
```

**Note:** In manual testing, the bot will use real API calls (if credentials are valid) but will NOT place real bets. Mock services are only used when test scenarios are loaded.

---

## Understanding Test Results

### Successful Test

**Console Output:**
```
✅ BET PLACED: Team A v Team B
   Market: Over/Under 2.5 Goals
   Lay @ 2.2, Stake: 41.67 EUR, Liability: 50.0 EUR
   BetId: TEST_1763108931411_1
```

**Excel Record:**
- Bet_ID: `TEST_...` (starts with TEST_ prefix)
- Bankroll_Before: Initial balance
- Bankroll_After: Balance after stake deduction
- Status: `Pending`

**Logs:**
- `[TEST MODE] Simulating lay bet placement`
- `Bet placed successfully: BetId=TEST_...`
- `Played bet_placed sound`

---

### Failed Test (Match Skipped)

**Console Output:**
```
⚠ Match skipped: [reason]
```

**Common Reasons:**
- `"Score 1-1 not found in Excel for 4_Serie A"` → Excel data missing
- `"Market conditions not met: Odds too low"` → Odds check failed
- `"Market conditions not met: Spread too wide"` → Spread check failed
- `"No goal in 60-74 window"` → Qualification failed

**Check:**
- Excel file has correct data
- Mock data matches test scenario
- Logs for detailed error messages

---

## Disabling Test Mode

When you're ready to place real bets:

### Step 1: Disable Test Mode

Edit `config/config.json`:
```json
{
  "test_mode": {
    "enabled": false  // ← Change to false
  }
}
```

### Step 2: Verify Real Mode

When you run the bot, you should **NOT** see:
```
TEST MODE ENABLED - Using mock services
```

**Warning:** In real mode, the bot will place real bets and deduct real money from your account. Make sure:
- ✅ You understand the bot's logic
- ✅ You have tested thoroughly in test mode
- ✅ You have sufficient funds
- ✅ You are monitoring the bot

---

## Troubleshooting

### Issue: Bot Not Placing Bets in Test Mode

**Possible Causes:**
1. Excel file missing data for the competition/result
2. Mock data doesn't match test scenario
3. Market conditions not met (odds, spread, liquidity)

**Solution:**
1. Check logs: `logs/betfair_bot.log`
2. Verify Excel has correct data
3. Check mock data in test scenario

---

### Issue: Sound Notifications Not Playing

**Possible Causes:**
1. Sound files missing (`sounds/success.mp3`, `sounds/ping.mp3`)
2. Sound notifications disabled in config

**Solution:**
1. Check `sounds/` directory has required files
2. Verify `notifications.sound_enabled = true` in config

---

### Issue: Excel Not Updated

**Possible Causes:**
1. Excel file is open (locked)
2. File permissions issue
3. Path incorrect

**Solution:**
1. Close Excel file before running bot
2. Check file permissions
3. Verify path in logs

---

### Issue: Test Mode Still Placing Real Bets

**Possible Causes:**
1. `test_mode.enabled = false` (not enabled)
2. Config file not saved
3. Wrong config file being used

**Solution:**
1. Double-check `config/config.json` has `"enabled": true`
2. Save config file
3. Restart bot

---

## Best Practices

### Before Testing
- [ ] Enable test mode (`test_mode.enabled = true`)
- [ ] Verify Excel has test data
- [ ] Check sound files exist
- [ ] Review test scenario description

### During Testing
- [ ] Monitor console output
- [ ] Check logs for errors
- [ ] Verify Excel records
- [ ] Listen for sound notifications

### After Testing
- [ ] Review test results
- [ ] Check Excel for bet records
- [ ] Verify notifications worked
- [ ] Document any issues

---

## Summary

1. **Test mode is safe**: No real bets, no real money deducted
2. **Use test scenarios**: Pre-configured scenarios make testing easy
3. **Check prerequisites**: Excel data and sound files must exist
4. **Review results**: Check console, logs, and Excel files
5. **Disable when ready**: Set `enabled = false` for real betting

**Remember:** Always test thoroughly in test mode before enabling real betting!

