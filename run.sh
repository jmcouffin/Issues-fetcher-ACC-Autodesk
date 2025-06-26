#!/bin/bash

echo "ACC/BIM 360 Issues Fetcher"
echo "=========================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.7+ from your package manager or https://python.org"
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 is not installed"
    echo "Please install pip3 using your package manager"
    exit 1
fi

# Check if requirements are installed
python3 -c "import aps_toolkit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install requirements"
        exit 1
    fi
fi

# Check for configuration
if [ ! -f ".env" ]; then
    if [ ! -f "config_template.env" ]; then
        echo "ERROR: Configuration template not found"
        exit 1
    fi
    echo
    echo "WARNING: No .env file found"
    echo "Please copy config_template.env to .env and configure your APS credentials"
    echo
    read -p "Press Enter to continue..."
fi

# Check for tkinter on Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    python3 -c "import tkinter" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "ERROR: tkinter is not installed"
        echo "On Ubuntu/Debian, install with: sudo apt-get install python3-tk"
        echo "On CentOS/RHEL, install with: sudo yum install tkinter"
        exit 1
    fi
fi

# Run the application
echo "Starting ACC/BIM 360 Issues Fetcher..."
python3 script.py
