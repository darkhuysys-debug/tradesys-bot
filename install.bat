@echo off
echo ========================================
echo   Trade SyS - Windows Installer
echo ========================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/3] Checking Python version...
python --version
echo.

echo [2/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo [3/3] Creating config directory...
if not exist "%USERPROFILE%\.tradesys" mkdir "%USERPROFILE%\.tradesys"

echo.
echo ========================================
echo   Installation complete!
echo   Run 'run.bat' to start the bot.
echo ========================================
pause
