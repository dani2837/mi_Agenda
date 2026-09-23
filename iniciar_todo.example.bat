@echo off
cd /d "%~dp0"
start "App tareas web" powershell -NoExit -ExecutionPolicy Bypass -Command ".\.venv\Scripts\Activate.ps1; uvicorn main:app --reload"
timeout /t 2 /nobreak > nul
start "Bot Telegram tareas" powershell -NoExit -ExecutionPolicy Bypass -Command ".\.venv\Scripts\Activate.ps1; python bot.py"
start "" "http://localhost:8000"
