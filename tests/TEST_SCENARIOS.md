# Test Scenarios Guide

## Cách Sử Dụng

### 1. Load Test Scenario

```bash
# Load scenario vào config.json
python tests/load_test_scenario.py scenario_1_happy_path
```

### 2. Chạy Bot

```bash
# Chạy bot với scenario đã load
python src/main.py
```

### 3. Xem Kết Quả

- Logs: `logs/betfair_bot.log`
- Excel: `competitions/Bet_Records.xlsx` (nếu bet placed)
- Skipped Matches: `competitions/Skipped Matches.xlsx` (nếu skip)

---

## Danh Sách Test Scenarios

### Scenario 1: Happy Path ✅
**Mô tả:** Goal trong 60-74, tất cả conditions OK, bet được placed (NOT matched)

**Test Cases:**
- ✅ Match detection và matching
- ✅ Goal detection trong window 60-74
- ✅ Qualification logic
- ✅ Market conditions check (odds, spread, liquidity)
- ✅ Stake calculation từ Excel
- ✅ Bet placement (mock)
- ✅ Excel writing
- ✅ **Sound notification: Bet placed sound** 🔔

**Kỳ vọng:** Bet placed successfully với Bet_ID = "TEST_...", sound notification played

---

### Scenario 1b: Happy Path - Bet Matched ✅🔔📱
**Mô tả:** Goal trong 60-74, tất cả conditions OK, bet được placed VÀ matched ngay lập tức

**Test Cases:**
- ✅ Tất cả test cases từ Scenario 1
- ✅ **Sound notification: Bet placed sound** 🔔
- ✅ **Sound notification: Bet matched sound** 🔔
- ✅ **Telegram notification: Bet matched** 📱

**Kỳ vọng:** 
- Bet placed successfully
- Bet matched immediately (sizeMatched > 0)
- Sound notifications: Bet placed + Bet matched
- Telegram notification sent (nếu enabled)

---

### Scenario 2: Early Discard ❌
**Mô tả:** Score 0-3 tại phút 60, out of target

**Test Cases:**
- ✅ Early discard check tại phút 60
- ✅ Excel target matching
- ✅ Out of target detection

**Kỳ vọng:** Match DISQUALIFIED ngay tại phút 60, không track tiếp

---

### Scenario 3: VAR Cancelled Goal ❌
**Mô tả:** Goal ở phút 65 nhưng bị VAR cancel

**Test Cases:**
- ✅ VAR check enabled
- ✅ Cancelled goal filtering
- ✅ Valid goal counting

**Kỳ vọng:** Match DISQUALIFIED (không có valid goal trong window)

---

### Scenario 4: 0-0 Exception ✅
**Mô tả:** Score 0-0 tại phút 65, competition trong exception list

**Test Cases:**
- ✅ 0-0 exception check
- ✅ Competition matching
- ✅ Window check (60-74)

**Kỳ vọng:** Match QUALIFIED với reason "0-0 exception"

**Lưu ý:** Cần thêm competition vào `zero_zero_exception_competitions` trong config

---

### Scenario 5: Odds Too Low ❌
**Mô tả:** Under X.5 best back = 1.2 (quá thấp, < min_odds 1.5)

**Test Cases:**
- ✅ Odds check trên Under X.5 best back
- ✅ Range validation [min_odds, max_odds]

**Kỳ vọng:** Match SKIP với reason "Odds too low"

---

### Scenario 6: Spread Too Wide ❌
**Mô tả:** Spread = 8 ticks (quá rộng, > max_spread_ticks 4)

**Test Cases:**
- ✅ Spread calculation (Over X.5 lay - Over X.5 back)
- ✅ Ticks calculation với price ladder
- ✅ Spread threshold check

**Kỳ vọng:** Match SKIP với reason "Spread too wide"

---

### Scenario 7: No Liquidity ❌
**Mô tả:** Không có liquidity trên Over X.5 lay side

**Test Cases:**
- ✅ Liquidity check
- ✅ Book percentage check

**Kỳ vọng:** Match SKIP với reason "No liquidity"

---

### Scenario 8: Insufficient Funds ❌
**Mô tả:** Liability > available balance (balance = 10.0, liability > 10.0)

**Test Cases:**
- ✅ Balance check
- ✅ Liability calculation
- ✅ Insufficient funds handling

**Kỳ vọng:** Match SKIP với reason "Insufficient funds"

---

### Scenario 9: No Goal in Window ❌
**Mô tả:** Không có goal trong window 60-74 (goal ở phút 45)

**Test Cases:**
- ✅ Goal detection trong window
- ✅ Window boundary check
- ✅ Disqualification logic

**Kỳ vọng:** Match DISQUALIFIED tại phút 74

---

### Scenario 10: Market Unavailable ❌
**Mô tả:** Over/Under market không tìm thấy

**Test Cases:**
- ✅ Market finding logic
- ✅ Error handling khi market không có

**Kỳ vọng:** Match SKIP với reason "Market unavailable"

---

## Test Checklist

Sau khi chạy mỗi scenario, kiểm tra:

- [ ] Logs có đúng message không?
- [ ] State transitions đúng không?
- [ ] Qualification/disqualification đúng không?
- [ ] Market conditions check đúng không?
- [ ] Bet placement (nếu có) có mock Bet_ID không?
- [ ] Excel records có đúng không?
- [ ] Skipped matches có được ghi không?

---

## Lưu Ý

1. **0-0 Exception:** Cần thêm competition vào `zero_zero_exception_competitions` trong config để test scenario 4

2. **Excel Data:** Một số scenarios cần Excel có data tương ứng:
   - Scenario 1, 4, 8: Cần có Competition-Live và Result trong Excel
   - Scenario 2: Cần check Excel targets để verify out of target

3. **Test Mode:** Luôn đảm bảo `test_mode.enabled = true` khi test

4. **Reset Config:** Sau khi test xong, có thể set `test_mode.enabled = false` để chạy real mode

