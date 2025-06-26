@echo off
echo Starting ACC/BIM 360 Issues Fetcher (Streamlit Version)
echo =====================================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo Error: .env file not found
    echo Please copy config_template.env to .env and add your APS credentials
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Checking dependencies...
pip install -r requirements.txt

REM Run the Streamlit application
echo Starting Streamlit application...
echo.
echo The application will open in your default web browser at http://localhost:8501
echo.
streamlit run streamlit_app.py

pause
