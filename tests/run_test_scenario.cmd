@echo off
REM Script to load and run a test scenario
REM Usage: run_test_scenario.cmd scenario_1_happy_path

if "%1"=="" (
    echo Usage: run_test_scenario.cmd ^<scenario_name^>
    echo.
    echo Available scenarios:
    echo   scenario_1_happy_path - Happy Path (Bet placed, NOT matched)
    echo   scenario_1b_happy_path_matched - Happy Path (Bet placed AND matched - TEST NOTIFICATIONS)
    echo   scenario_2_early_discard - Early Discard (Out of target)
    echo   scenario_3_var_cancelled_goal - VAR Cancelled Goal
    echo   scenario_4_zero_zero_exception - 0-0 Exception
    echo   scenario_5_odds_too_low - Odds Too Low
    echo   scenario_6_spread_too_wide - Spread Too Wide
    echo   scenario_7_no_liquidity - No Liquidity
    echo   scenario_8_insufficient_funds - Insufficient Funds
    echo   scenario_9_no_goal_in_window - No Goal in Window
    echo   scenario_10_market_unavailable - Market Unavailable
    exit /b 1
)

echo Loading test scenario: %1
python tests\load_test_scenario.py %1

if %ERRORLEVEL% NEQ 0 (
    echo Failed to load scenario
    exit /b 1
)

echo.
echo Scenario loaded successfully!
echo Test mode is now enabled in config.json
echo.
echo You can now run the bot:
echo   python src\main.py
echo.
pause

