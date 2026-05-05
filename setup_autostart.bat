@echo off
setlocal

set TASK_NAME=YaobiTradingAgent
set LAUNCHER=%~dp0start_agent.bat

echo ========================================
echo  Yaobi Trading Agent - Windows auto start
echo ========================================
echo Task: %TASK_NAME%
echo Launcher: %LAUNCHER%
echo.

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%LAUNCHER%\"" ^
  /sc onlogon ^
  /delay 0001:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f >nul 2>&1

if %ERRORLEVEL%==0 (
    echo [OK] Auto start configured.
    echo It will start about 1 minute after Windows login.
    echo To remove it, run:
    echo schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo [FAILED] Please run this file as administrator.
)

echo.
pause
