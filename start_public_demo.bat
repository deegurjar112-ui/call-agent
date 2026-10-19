@echo off
cd /d "%~dp0"
title 1-Click AI Voice Agent Public Demo
color 0A
cls
echo ==============================================================================
echo        🎙️ 24/7 AI VOICE RECEPTIONIST - 1-CLICK PUBLIC DEMO SYSTEM
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
echo  ✅ LOCAL DEMO LINK (Test on this PC):
echo     http://localhost:8080
echo.
echo  🌐 GENERATING PUBLIC HTTPS DEMO LINK (For Clients & Mobile Phones)...
echo     Starting secure OpenSSH tunnel via localhost.run...
echo.
echo  👉 INSTRUCTIONS FOR CLIENT DEMO:
echo     1. Look for the "https://xxxx.lhr.life" link displayed below.
echo     2. Copy that link and send it via WhatsApp, SMS, or Email to any client.
echo     3. Client opens it on their iPhone/Android or laptop, taps "Start Call",
echo        and speaks directly with Aria!
echo ==============================================================================
echo.
ssh -o StrictHostKeyChecking=no -R 80:localhost:8080 nokey@localhost.run

echo.
echo Tunnel closed. If you need an alternative tunnel, you can also run:
echo npx localtunnel --port 8080
echo.
pause
