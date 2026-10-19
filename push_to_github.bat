@echo off
cd /d "%~dp0"
echo =====================================================================
echo  [ARIA 24/7 VOICE AI] - PUSH CODE TO YOUR GITHUB REPOSITORY
echo =====================================================================
echo.
set "DEFAULT_URL=https://github.com/deegurjar112-ui/call-agent.git"
echo Default Repository: %DEFAULT_URL%
echo.
set /p REPO_URL="Press ENTER to use default URL or paste another: "
if "%REPO_URL%"=="" set "REPO_URL=%DEFAULT_URL%"

echo.
echo [1/3] Setting remote origin to %REPO_URL% ...
git remote set-url origin %REPO_URL%

echo [2/3] Setting main branch ...
git branch -M main

echo [3/3] Pushing code to GitHub ...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [NOTE] If you saw authentication required, please ensure you are logged into GitHub in your browser or git credentials.
) else (
    echo.
    echo =====================================================================
    echo  [SUCCESS] Code successfully pushed to your GitHub!
    echo =====================================================================
)
pause
