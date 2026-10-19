@echo off
cd /d "%~dp0"
echo ==========================================================
echo Starting LiveKit Voice Agent in DEV Mode...
echo (Connecting to LiveKit Cloud for Web Sandbox / Phone Calls)
echo ==========================================================
:: Detect Python executable dynamically
set "PYTHON_EXE=python"
if exist "%USERPROFILE%\.venvs\livekit_agent\Scripts\python.exe" set "PYTHON_EXE=%USERPROFILE%\.venvs\livekit_agent\Scripts\python.exe"
if exist "..\.venvs\livekit_agent\Scripts\python.exe" set "PYTHON_EXE=..\.venvs\livekit_agent\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

"%PYTHON_EXE%" agent.py dev
pause
