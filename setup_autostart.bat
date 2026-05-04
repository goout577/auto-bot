@echo off
setlocal

set TASK_NAME=YaobiTradingAgent
set LAUNCHER=%~dp0start_agent.bat

echo ========================================
echo  Yaobi Trading Agent - 开机自启配置
echo ========================================
echo.
echo 任务名称: %TASK_NAME%
echo 启动脚本: %LAUNCHER%
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
    echo [成功] 开机自启已配置！
    echo        下次登录 Windows 后，Agent 将在 1 分钟内自动启动。
    echo.
    echo 如需取消自启，运行：
    echo   schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo [失败] 请以管理员身份运行此脚本。
    echo        右键 setup_autostart.bat → 以管理员身份运行
)

echo.
pause
