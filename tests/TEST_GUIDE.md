# Hướng Dẫn Test Tất Cả Scenarios

## Tại Sao Có 2 Option Test?

### Scenario 1 vs Scenario 1b

**Scenario 1** (`scenario_1_happy_path`):
- Bet được placed nhưng **KHÔNG matched** ngay
- Test: Bet placed sound only
- Mục đích: Test logic bet placement khi bet chưa matched

**Scenario 1b** (`scenario_1b_happy_path_matched`):
- Bet được placed **VÀ matched ngay lập tức**
- Test: Bet placed sound + Bet matched sound + Telegram notification
- Mục đích: Test notifications khi bet matched

**Lý do:** Một bet chỉ có thể matched hoặc không matched, không thể test cả 2 cùng lúc. Đây là 2 test case khác nhau.

---

## Cách Test Tất Cả Scenarios

### Option 1: Test Từng Scenario (Recommended)

```bash
# Test từng scenario một
python tests/load_test_scenario.py scenario_1_happy_path
python src/main.py
# Xem kết quả, sau đó test scenario tiếp theo

python tests/load_test_scenario.py scenario_1b_happy_path_matched
python src/main.py
# ... tiếp tục với các scenarios khác
```

### Option 2: Test Tự Động (Script)

```bash
# Chạy script tự động
python tests/run_all_tests.py
```

Script sẽ:
1. Load từng scenario vào config.json
2. Bạn cần chạy `python src/main.py` để test
3. Sau đó load scenario tiếp theo

---

## File Excel Test

### Vấn Đề

Bot cần Excel file để:
- Map competitions (Competition-Live → Competition-Betfair)
- Lấy stake % theo Result (ví dụ: "1-1" → 5.0%)

Hiện tại chỉ có file Excel thật, chưa có file test.

### Giải Pháp

**Option 1: Dùng File Excel Thật**
- Đảm bảo file `Competitions_Results_Odds_Stake.xlsx` có data cho test scenarios
- Cần có row với:
  - Competition-Live: "4_Serie A"
  - Result: "1-1", "0-0", "0-3", etc.
  - Stake: giá trị tương ứng

**Option 2: Tạo File Excel Test**
```bash
# Tạo file Excel test
python tests/create_test_excel.py
# File sẽ được tạo: competitions/Competitions_Results_Odds_Stake_TEST.xlsx
```

---

## Danh Sách Tất Cả Test Scenarios

1. **scenario_1_happy_path** - Bet placed (NOT matched) → Test bet placed sound
2. **scenario_1b_happy_path_matched** - Bet placed AND matched → Test tất cả notifications
3. **scenario_2_early_discard** - Early discard (out of target)
4. **scenario_3_var_cancelled_goal** - VAR cancelled goal
5. **scenario_4_zero_zero_exception** - 0-0 exception
6. **scenario_5_odds_too_low** - Odds too low
7. **scenario_6_spread_too_wide** - Spread too wide
8. **scenario_7_no_liquidity** - No liquidity
9. **scenario_8_insufficient_funds** - Insufficient funds
10. **scenario_9_no_goal_in_window** - No goal in window
11. **scenario_10_market_unavailable** - Market unavailable

---

## Checklist Trước Khi Test

- [ ] File Excel có data cho test scenarios (hoặc đã tạo test Excel)
- [ ] Sound files có sẵn: `sounds/success.mp3`, `sounds/ping.mp3`
- [ ] Telegram bot đã được start (`/start` với bot)
- [ ] Test mode enabled trong config (tự động khi load scenario)

---

## Kết Quả Mong Đợi

Sau khi test mỗi scenario, kiểm tra:

- [ ] Logs: `logs/betfair_bot.log` có đúng message không?
- [ ] Sound: Có phát sound không? (nếu test scenario 1 hoặc 1b)
- [ ] Telegram: Có nhận notification không? (nếu test scenario 1b)
- [ ] Excel: Có ghi bet record không? (nếu bet placed)
- [ ] State: Match state transitions đúng không?

