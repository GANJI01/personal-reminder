@echo off
echo Setting up Personal Reminder...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python 3.x first.
    pause
    exit /b 1
)

REM Install required packages
echo Installing required packages...
pip install tkcalendar pillow schedule pystray

REM Run the autostart installation script
echo Installing autostart...
python install_autostart.py

REM Start the application
echo Starting Personal Reminder...
start pythonw remainder.py

echo Setup complete!
pause 