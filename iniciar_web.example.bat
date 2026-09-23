@echo off
cd /d "%~dp0"
start "App tareas web" powershell -NoExit -ExecutionPolicy Bypass -Command ".\.venv\Scripts\Activate.ps1; uvicorn main:app --reload"
start "" "http://localhost:8000"
