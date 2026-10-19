@echo off
cd /d "%~dp0"
title 1-Click AI Voice Agent Public Demo (localtunnel)
color 0B
cls
echo ==============================================================================
echo     🎙️ 24/7 AI VOICE RECEPTIONIST - NPX LOCALTUNNEL PUBLIC DEMO
echo ==============================================================================
echo.
:: Detect Python executable dynamically
set "PYTHON_EXE=python"
if exist "%USERPROFILE%\.venvs\livekit_agent\Scripts\python.exe" set "PYTHON_EXE=%USERPROFILE%\.venvs\livekit_agent\Scripts\python.exe"
if exist "..\.venvs\livekit_agent\Scripts\python.exe" set "PYTHON_EXE=..\.venvs\livekit_agent\Scripts\python.exe"
if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

echo [1/3] Starting LiveKit Voice Agent Worker (Aria) in background...
start "LiveKit Agent Worker (Aria)" "%PYTHON_EXE%" agent.py dev

echo [2/3] Starting WebRTC & Token Dispenser Server on port 8080...
start "AI Voice Web & Token Server" "%PYTHON_EXE%" demo_server.py

echo.
echo Waiting 2 seconds for server to initialize...
timeout /t 2 /nobreak >nul

echo.
echo ==============================================================================
echo  ✅ LOCAL DEMO LINK:  http://localhost:8080
echo  🌐 PUBLIC HTTPS TUNNEL VIA NPX:
echo     Starting npx localtunnel on port 8080...
echo ==============================================================================
echo.
npx localtunnel --port 8080
pause
