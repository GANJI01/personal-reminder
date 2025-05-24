import os
import sys
import winreg
import subprocess
from pathlib import Path

def install_autostart():
    # Get the path to the current script
    if getattr(sys, 'frozen', False):
        # If the application is run as a frozen executable
        app_path = sys.executable
    else:
        # If the application is run as a Python script
        app_path = os.path.abspath(__file__)
        if app_path.endswith('install_autostart.py'):
            # Get the path to the main application script
            app_path = os.path.join(os.path.dirname(app_path), 'remainder.py')
            app_path = f'pythonw "{app_path}"'

    # Create the registry key
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "PersonalReminder", 0, winreg.REG_SZ, app_path)
        winreg.CloseKey(key)
        print("Successfully installed Personal Reminder to start with Windows.")
    except Exception as e:
        print(f"Error installing autostart: {e}")
        return False
    return True

if __name__ == "__main__":
    if install_autostart():
        print("Personal Reminder will now start automatically with Windows.")
    else:
        print("Failed to install autostart. Please run as administrator.") 