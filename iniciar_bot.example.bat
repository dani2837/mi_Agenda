@echo off
cd /d "%~dp0"
start "Bot Telegram tareas" powershell -NoExit -ExecutionPolicy Bypass -Command ".\.venv\Scripts\Activate.ps1; python bot.py"
