@echo off
echo ACC/BIM 360 Issues Fetcher
echo ========================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

REM Check if requirements are installed
python -c "import aps_toolkit" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install requirements
        pause
        exit /b 1
    )
)

REM Check for configuration
if not exist ".env" (
    if not exist "config_template.env" (
        echo ERROR: Configuration template not found
        pause
        exit /b 1
    )
    echo.
    echo WARNING: No .env file found
    echo Please copy config_template.env to .env and configure your APS credentials
    echo.
    echo Would you like to:
    echo 1. Run diagnostics to check setup
    echo 2. Continue anyway
    echo 3. Exit
    choice /c 123 /m "Choose option"
    if errorlevel 3 exit /b 0
    if errorlevel 2 goto run_app
    if errorlevel 1 goto run_diagnostics
)

:run_app
REM Run the application
echo Starting ACC/BIM 360 Issues Fetcher...
python script.py
goto end

:run_diagnostics
echo Running diagnostics...
python diagnose.py
echo.
echo Would you like to run the main application now? (Y/N)
choice /c YN /m "Run main app"
if errorlevel 2 goto end
python script.py

:end
pause
