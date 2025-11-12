@echo off
REM Betfair Italy Bot - Milestone 1 Runner Script
REM Activates venv and runs the main script

cd /d "%~dp0.."
call .venv\Scripts\activate.bat

if errorlevel 1 (
    echo Error: Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo ========================================
echo Betfair Italy Bot - Milestone 1
echo ========================================
echo.

python src\main.py

pause

