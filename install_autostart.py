import os
import sys
import winreg
import subprocess
from pathlib import Path

def install_autostart(app_path_to_register):
    """Installs the application to start automatically with Windows via the registry."""
    if app_path_to_register is None:
         print("Error: Application path for autostart not provided.")
         return False

    # Create the registry key
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        # Use KEY_WRITE to ensure we have permission to set the value
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
        
        # Ensure the command run includes 'pythonw' if it's a script, for silent startup
        command_to_run = app_path_to_register
        # Only add pythonw if it's a .py file and not already starting with python/pythonw
        if command_to_run.lower().endswith('.py') and not command_to_run.lower().startswith(('python ', 'pythonw ')):
             # Use pythonw for silent execution of script
             command_to_run = f'pythonw "{command_to_run}"'

        winreg.SetValueEx(key, "PersonalReminder", 0, winreg.REG_SZ, command_to_run)
        winreg.CloseKey(key)
        # print("Successfully installed Personal Reminder to start with Windows.") # Print moved outside
    except PermissionError:
        print("Permission denied: Could not write to the registry. Please run this script with administrator privileges if the issue persists.")
        return False
    except FileNotFoundError:
        # This might happen if the Run key path is unexpectedly missing
        print(f"Error: Registry key path not found: {key_path}")
        return False
    except Exception as e:
        print(f"Error installing autostart: {e}")
        return False
    return True

# Removed uninstall_autostart function as it's not requested, simplifying the edit

if __name__ == "__main__":
    # Determine the path to the script or executable that should run.
    # We prioritize the compiled executable in 'dist' if it exists.
    
    app_to_run_path = None # Initialize variable

    # Prioritize the compiled executable in 'dist' if it exists
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
    dist_exe_path = os.path.join(dist_dir, "PersonalReminder.exe")
    
    # Check if running as a bundled executable (this script itself) - low priority for autostart target
    if getattr(sys, 'frozen', False):
         # This install script is likely not the target app itself
         pass # Don't set app_to_run_path here
         
    if os.path.exists(dist_exe_path):
        # Compiled executable exists, launch that
        app_to_run_path = dist_exe_path
        print(f"Found compiled executable: {app_to_run_path}")
    else:
        # Fallback to running the python script from the main directory
        script_path = os.path.abspath(__file__).replace("install_autostart.py", "remainder.py")
        if os.path.exists(script_path):
             app_to_run_path = script_path
             print(f"Compiled executable not found, using script: {app_to_run_path}")
        else:
             print("Error: Neither compiled executable nor remainder.py script found for autostart.")
             # Do not proceed if target not found
             sys.exit(1)

    # Removed log_file_path as it wasn't used in the installation logic.
    # log_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "autostart.log")) # Log file for autostart script itself

    # Attempt to install autostart with the determined path
    if install_autostart(app_to_run_path):
        # Success message moved here to only show on success
        print("Successfully installed Personal Reminder to start with Windows.")
    else:
        # Error message already printed by the function
        pass # Error message already printed by the function 