@echo off
title Trade SyS Bot
echo Starting Trade SyS Bot...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Bot crashed! Check error above.
    pause
)
