@echo off
echo ====================================
echo  RetailPool AI - Install Bot Dependencies
echo ====================================
echo.

cd /d %~dp0

echo [1/2] Installing Python packages...
.venv\Scripts\python.exe -m pip install python-telegram-bot reportlab apscheduler python-dotenv

echo.
echo [2/2] Verifying imports...
.venv\Scripts\python.exe -c "from retailpool.bot.app import create_application; print('[OK] Bot module imports successfully')"

echo.
echo ====================================
echo  Installation complete!
echo  
echo  To start the bot:
echo    .venv\Scripts\python.exe run_bot.py --polling
echo  
echo  To start with FastAPI backend:
echo    .venv\Scripts\python.exe run_dev.py
echo    (in another terminal)
echo    .venv\Scripts\python.exe run_bot.py --polling
echo ====================================
pause
