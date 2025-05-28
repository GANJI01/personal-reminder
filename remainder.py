import json
from datetime import date, datetime, time, timedelta # Ensure time is imported from datetime
from dateutil.relativedelta import relativedelta
import uuid
import os
import tkinter as tk
from tkinter import ttk # Import Themed Tkinter
from tkinter import font as tkFont
from tkinter import messagebox
from tkcalendar import Calendar
from PIL import Image, ImageTk
import schedule
import time as py_time # Renamed to avoid conflict with datetime.time
import threading
import sys
import pystray
from pystray import MenuItem as item, Menu
import atexit
import logging
from logging.handlers import RotatingFileHandler
import traceback

# --- PATH HELPER FUNCTIONS (FOR PYINSTALLER COMPATIBILITY) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # For development, or if not bundled by PyInstaller
        # Use the directory of the script file
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def data_file_path(filename):
    """ Get path for data files, typically next to EXE or script """
    if getattr(sys, 'frozen', False):
        # Running as a bundled executable (PyInstaller)
        exe_dir = os.path.dirname(sys.executable)
        # If running from 'dist', look in the parent directory
        if os.path.basename(exe_dir).lower() == 'dist':
            application_path = os.path.dirname(exe_dir)
        else:
            # Otherwise, look next to the executable
            application_path = exe_dir
    else:
        # Running as a script
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, filename)

# --- CONSTANTS ---
APP_NAME = "Personal Reminder"
# Use path helpers for file locations
LOGO_FILE = resource_path("logo.png")
DATA_FILE = data_file_path("reminders.json")
CONFIG_FILE = data_file_path("app_config.json")
LOCK_FILE = data_file_path('app.lock') # Lock file also next to exe/script

INDIVIDUAL_NOTIFICATION_CHECK_INTERVAL_SECONDS = 60 # Check every minute instead of every second
NOTIFICATION_WINDOW_MINUTES = 0 # As per your setting (affects check_and_notify_due_reminders old logic, new logic is different)

# Recurring reminder constants
RECURRENCE_TYPES = {
    "None": None,
    "Daily": "daily",
    "Weekdays": "weekdays",
    "Weekly": "weekly",
    "Biweekly": "biweekly",
    "Monthly": "monthly",
    "Yearly": "yearly"
}

# End condition types
END_CONDITION_TYPES = {
    "Never": "never",
    "After": "occurrences",
    "On Date": "date"
}

# Maximum number of occurrences for "After" end condition
MAX_OCCURRENCES = 999

SNOOZE_OPTIONS = {
    "5 minutes": 5,
    "10 minutes": 10,
    "15 minutes": 15,
    "30 minutes": 30,
    "1 hour": 60
}

# --- LOGGING SETUP ---
def setup_logging():
    """Set up logging configuration for the application."""
    log_file = data_file_path("app.log")
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Create logger
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)
    
    # Create handlers
    file_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)  # 1MB per file, 5 backups
    console_handler = logging.StreamHandler()
    
    # Create formatters and add them to handlers
    formatter = logging.Formatter(log_format, date_format)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logging()

# --- ERROR HANDLING ---
def log_error(error_msg, exc_info=None):
    """Log an error message with optional exception info."""
    if exc_info:
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
    else:
        logger.error(error_msg)

def log_info(info_msg):
    """Log an info message."""
    logger.info(info_msg)

def log_debug(debug_msg):
    """Log a debug message."""
    logger.debug(debug_msg)

# --- SINGLE INSTANCE LOCK ---
def check_single_instance():
    # This check should ideally only prevent multiple *full app instances*.
    # The `startup_check` might be okay to run even if the main app is running,
    # or we ensure it's very quick and cleans up its own (if it used a lock).
    # For now, this global lock will prevent any second launch if lock exists.

    # Determine the correct lock file path based on how the app is run
    current_app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    current_dir = os.path.dirname(current_app_path)
    
    # If running from dist, the lock file is in dist. Otherwise, it's in the base dir.
    # Note: The data_file_path logic for the executable looks *up* if in dist, 
    # but the lock file logic here needs to check relative to the executable itself.
    # Let's use a more direct check based on the running executable's location.
    is_running_from_dist_dir = os.path.basename(current_dir).lower() == 'dist'
    actual_lock_file_path = os.path.join(current_dir, 'app.lock') # Lock file is always next to the running executable

    log_debug(f"Checking for lock file: {actual_lock_file_path}")

    if os.path.exists(actual_lock_file_path):
        log_info(f"Lock file '{actual_lock_file_path}' exists.")
        try:
            with open(actual_lock_file_path, 'r') as f:
                pid_str = f.read().strip()
                pid = int(pid_str) if pid_str.isdigit() else -1
            log_debug(f"Found PID {pid} in lock file.")

            # Attempt to check if the process is actually running
            # This is a basic attempt and might not work in all environments or permissions.
            is_process_running = False
            if pid > 0:
                try:
                    # On Windows, signal 0 checks existence without sending a signal
                    os.kill(pid, 0) 
                    is_process_running = True
                    log_debug(f"Process with PID {pid} appears to be running.")
                except OSError as e:
                    # Process does not exist or permission error
                    log_debug(f"Process with PID {pid} check failed: {e}")
                    is_process_running = False # Process is not running or we can't verify
                except Exception as e:
                     log_error(f"Unexpected error checking PID {pid}: {e}", exc_info=True)
                     is_process_running = False # Assume not running on error

            if is_process_running:
                 log_info("Another instance is confirmed to be running.")
                 messagebox.showwarning(APP_NAME, "Another instance of the application is already running.")
                 sys.exit(0) # Exit if another instance is running
            else:
                 # Lock file exists but process is not running. Clean it up.
                 log_info(f"Lock file '{actual_lock_file_path}' found but process {pid} is not running. Attempting to clean up.")
                 try:
                     os.remove(actual_lock_file_path)
                     log_info("Stale lock file cleaned up successfully.")
                 except Exception as e:
                     log_error(f"Error cleaning up stale lock file '{actual_lock_file_path}': {e}", exc_info=True)
                     # Even if cleanup fails, we assume the process is not running and continue

        except FileNotFoundError: # Should be caught by os.path.exists, but for safety
             log_debug("Lock file disappeared during check.")
             pass # File was deleted between check and open
        except Exception as e: # Catch errors reading the PID from the file
            log_error(f"Error reading or processing PID from lock file '{actual_lock_file_path}': {e}", exc_info=True)
            log_info(f"Assuming lock file '{actual_lock_file_path}' is stale due to read error. Attempting to clean up.")
            try:
                 os.remove(actual_lock_file_path)
                 log_info("Stale lock file cleaned up successfully after read error.")
            except Exception as e_del:
                 log_error(f"Error cleaning up lock file '{actual_lock_file_path}' after read error: {e_del}", exc_info=True)
            # Continue execution as we assume the previous instance is not running

    # If no lock file exists, or if a stale one was cleaned up, create a new one.
    # Only create the lock file if not running a utility command (like startup_check)
    is_utility_run = len(sys.argv) > 1 and sys.argv[1] in ['startup_check', 'start_minimized']
    if not is_utility_run:
        try:
            with open(actual_lock_file_path, 'w') as f:
                f.write(str(os.getpid()))
            log_debug(f"Created new lock file with PID {os.getpid()} at '{actual_lock_file_path}'.")
            # Register cleanup *only* if we successfully created the lock file
            atexit.register(lambda file_path=actual_lock_file_path: cleanup_lock_file(file_path))
        except Exception as e:
            log_error(f"Error creating lock file '{actual_lock_file_path}': {e}", exc_info=True)
            # Application might continue, but without lock protection

def cleanup_lock_file(file_path):
    """Cleans up the specified lock file on exit."""
    log_debug(f"Attempting to clean up lock file: {file_path}")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            log_debug(f"Lock file '{file_path}' cleaned up successfully.")
        except Exception as e:
            log_error(f"Error cleaning up lock file '{file_path}': {e}", exc_info=True)

# --- GLOBAL VARIABLES ---
tk_root_window = None
scheduler_stop_event = threading.Event()
app_instance_ref = None
tray_icon_object = None
main_gui_visible = True
app_to_run_path = None # Global variable for autostart path

# --- DATA HANDLING FUNCTIONS --- (Your existing ones)
def load_reminders():
    if not os.path.exists(DATA_FILE):
        log_debug(f"Data file {DATA_FILE} does not exist. Returning empty list.")
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            content = f.read()
            if not content.strip():
                log_debug("Data file is empty. Returning empty list.")
                return []
            reminders = json.loads(content)
            if not isinstance(reminders, list):
                log_error("Data file does not contain a list. Returning empty list.")
                return []
            reminders.sort(key=lambda r: (str(r.get("date", "")), str(r.get("time", ""))))
            log_debug(f"Successfully loaded {len(reminders)} reminders.")
            return reminders
    except Exception as e:
        log_error(f"Error loading reminders from {DATA_FILE}", exc_info=True)
        messagebox.showerror("Load Error", f"Could not load reminders from {DATA_FILE}.\nError: {e}")
        return []

def save_reminders(reminders):
    try:
        reminders.sort(key=lambda r: (str(r.get("date", "")), str(r.get("time", ""))))
        with open(DATA_FILE, 'w') as f:
            json.dump(reminders, f, indent=4)
        log_debug(f"Successfully saved {len(reminders)} reminders.")
    except Exception as e:
        log_error(f"Error saving reminders to {DATA_FILE}", exc_info=True)
        messagebox.showerror("Save Error", f"Could not save reminders to {DATA_FILE}.\nError: {e}")

def load_app_config():
    if not os.path.exists(CONFIG_FILE): return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
            if not content.strip(): return {}
            return json.loads(content)
    except Exception as e:
        log_error(f"Error loading app config: {e}")
        return {}

def save_app_config(config_data):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        log_error(f"Error saving app config: {e}")

# --- TIME FORMATTING --- (Your existing one)
def format_time_to_ampm(time_str_24h):
    if not time_str_24h: return "N/A"
    try:
        t_obj = datetime.strptime(time_str_24h, "%H:%M").time()
        return t_obj.strftime("%I:%M %p")
    except ValueError:
        return time_str_24h

# --- NOTIFICATION & SCHEDULER --- (Your existing, with your check_and_notify_due_reminders logic)
def show_individual_reminder_popup_thread_safe(title, reminder_time_24h, reminder_id=None):
    if tk_root_window:
        tk_root_window.after(0, lambda t=title, rt=reminder_time_24h, rid=reminder_id: 
                           actual_show_individual_popup(t, rt, rid))

def actual_show_individual_popup(reminder_title, reminder_time_24h, reminder_id=None):
    try:
        popup = tk.Toplevel(tk_root_window)
        popup.title("Reminder Due!")
        popup.attributes('-topmost', True)
        app_icon_photo = getattr(app_instance_ref, 'app_icon_photo', None)
        if app_icon_photo:
             popup.iconphoto(True, app_icon_photo)
        
        formatted_time_ampm = format_time_to_ampm(reminder_time_24h)
        label_text = f"Reminder: {reminder_title}\nTime: {formatted_time_ampm}"
        
        label = ttk.Label(popup, text=label_text, padding="20", wraplength=300, justify=tk.CENTER)
        label.pack(pady=10, padx=10)

        # Add buttons frame
        button_frame = ttk.Frame(popup)
        button_frame.pack(pady=10)

        # Snooze button with dropdown
        if reminder_id:
            snooze_var = tk.StringVar(value="5 minutes")
            snooze_menu = ttk.OptionMenu(button_frame, snooze_var, "5 minutes", *SNOOZE_OPTIONS.keys())
            snooze_menu.pack(side=tk.LEFT, padx=5)
            
            def do_snooze():
                minutes = SNOOZE_OPTIONS[snooze_var.get()]
                if snooze_reminder(reminder_id, minutes):
                    popup.destroy()
            
            ttk.Button(button_frame, text="Snooze", command=do_snooze).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="OK", command=popup.destroy).pack(side=tk.LEFT, padx=5)
        popup.lift()
        popup.focus_force()
    except Exception as e:
        log_error(f"Error in actual_show_individual_popup: {e}")

def mark_reminder_as_notified(reminder_id):
    reminders = load_reminders()
    for r in reminders:
        if r.get("id") == reminder_id: r["notified_individually"] = True; break
    save_reminders(reminders)

def calculate_next_recurrence(reminder):
    """Calculate the next occurrence date for a recurring reminder."""
    if not reminder.get("recurrence_type"):
        return None
    
    current_date = datetime.strptime(reminder["date"], "%Y-%m-%d").date()
    today = date.today()
    
    if current_date < today:
        current_date = today
    
    recurrence_type = reminder["recurrence_type"]
    
    if recurrence_type == "daily":
        return (current_date + timedelta(days=1)).strftime("%Y-%m-%d")
    elif recurrence_type == "weekdays":
        next_date = current_date + timedelta(days=1)
        # Skip weekends
        while next_date.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
            next_date += timedelta(days=1)
        return next_date.strftime("%Y-%m-%d")
    elif recurrence_type == "weekly":
        return (current_date + timedelta(days=7)).strftime("%Y-%m-%d")
    elif recurrence_type == "biweekly":
        return (current_date + timedelta(days=14)).strftime("%Y-%m-%d")
    elif recurrence_type == "monthly":
        # Use relativedelta for robust month calculations
        next_month_date = current_date + relativedelta(months=1)
        return next_month_date.strftime("%Y-%m-%d")
    elif recurrence_type == "yearly":
        # Use relativedelta for consistent year calculations
        next_year_date = current_date + relativedelta(years=1)
        return next_year_date.strftime("%Y-%m-%d")
    return None

def snooze_reminder(reminder_id, minutes):
    """Snooze a reminder for the specified number of minutes."""
    reminders = load_reminders()
    for reminder in reminders:
        if reminder.get("id") == reminder_id:
            reminder["notified_individually"] = False
            # Update the time to current time + snooze minutes
            current_time = datetime.now()
            snooze_time = current_time + timedelta(minutes=minutes)
            reminder["time"] = snooze_time.strftime("%H:%M")
            reminder["date"] = snooze_time.strftime("%Y-%m-%d")
            save_reminders(reminders)
            return True
    return False

def check_and_notify_due_reminders():
    """Check for due reminders and notify if needed."""
    log_debug("Checking for due reminders...")
    try:
        reminders = load_reminders()
        current_time = datetime.now()
        log_debug(f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        updated_reminders = []
        data_changed = False

        for reminder in reminders:
            reminder_id = reminder.get("id", "N/A")
            reminder_title = reminder.get("title", "N/A")
            reminder_date = reminder.get("date", "N/A")
            reminder_time_str = reminder.get("time", "N/A")
            notified_status = reminder.get("notified_individually", False)

            log_debug(f"Checking reminder {reminder_id} ('{reminder_title}') on {reminder_date} at {reminder_time_str}. Notified: {notified_status}")

            # Skip if already notified
            if notified_status:
                log_debug(f"Skipping reminder {reminder_id} - already notified.")
                updated_reminders.append(reminder)
                continue

            # Try to parse reminder time
            try:
                reminder_datetime = datetime.strptime(f"{reminder_date} {reminder_time_str}", "%Y-%m-%d %H:%M")
                log_debug(f"Parsed reminder datetime: {reminder_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            except ValueError:
                log_error(f"Invalid date or time format for reminder ID {reminder_id}: {reminder_date} {reminder_time_str}")
                updated_reminders.append(reminder)
                continue # Skip this reminder due to invalid format

            # Check if reminder is due
            if reminder_datetime <= current_time:
                log_debug(f"Reminder {reminder_id} is due. Triggering notification.")
                # Show notification for current instance using the correct function
                show_individual_reminder_popup_thread_safe(
                    reminder.get("title"),
                    reminder.get("time"),
                    reminder.get("id")
                )
                reminder["notified_individually"] = True
                data_changed = True
                log_debug(f"Marked reminder {reminder_id} as notified_individually=True.")

                # Handle recurring reminders
                if reminder.get("recurrence_type") is not None:
                    log_debug(f"Handling recurrence for reminder {reminder_id}.")
                    # Check end conditions
                    end_type = reminder.get("recurrence_end_type", "never")
                    series_ended = False

                    if end_type == "occurrences":
                        current_count = reminder.get("recurrence_current_count", 0)
                        max_occurrences = reminder.get("recurrence_end_value")
                        log_debug(f"Occurrences end condition: current={current_count}, max={max_occurrences}.")
                        if current_count >= max_occurrences:
                            series_ended = True
                            log_debug(f"Series ended for {reminder_id} - max occurrences reached.")
                        else:
                            reminder["recurrence_current_count"] = current_count + 1
                            log_debug(f"Incremented occurrence count for {reminder_id} to {reminder["recurrence_current_count"]}.")

                    # Calculate next date before checking date-based end condition
                    next_date_str = calculate_next_recurrence(reminder)
                    log_debug(f"Calculated next recurrence date for {reminder_id}: {next_date_str}")
                    
                    # Check date-based end condition using the next calculated date
                    if not series_ended and end_type == "date":
                        recurrence_end_date_str = reminder.get("recurrence_end_value")
                        if recurrence_end_date_str:
                            try:
                                recurrence_end_date_obj = datetime.strptime(recurrence_end_date_str, "%Y-%m-%d").date()
                                # Ensure next_date_str is not None before parsing
                                if next_date_str:
                                    next_calculated_date_obj = datetime.strptime(next_date_str, "%Y-%m-%d").date()
                                    
                                    if next_calculated_date_obj > recurrence_end_date_obj:
                                        log_debug(f"Next calculated date {next_date_str} is past end date {recurrence_end_date_str}. Series ends for {reminder_id}.")
                                        series_ended = True
                                else:
                                     log_debug(f"Next date calculation returned None for {reminder_id}, cannot check end date condition.")
                                     series_ended = True # Or handle as an error

                            except (ValueError, TypeError) as e_date_conv:
                                log_error(f"Invalid end date format '{recurrence_end_date_str}' or issue with next date '{next_date_str}' for reminder ID {reminder_id}: {e_date_conv}", exc_info=True)
                                series_ended = True # Assume series ends on error

                    # Create next occurrence if series hasn't ended and a next date was calculated
                    if not series_ended and next_date_str:
                        new_reminder = reminder.copy()
                        new_reminder["id"] = str(uuid.uuid4()) # Assign new ID
                        new_reminder["date"] = next_date_str
                        new_reminder["time"] = reminder_time_str # Keep the same time as the original
                        new_reminder["notified_individually"] = False
                        # Preserve current count for occurrences type (already incremented on original)
                        # For recurring reminders, the count is stored on the NEXT instance.
                        if end_type == "occurrences":
                             # The count was incremented on the *current* reminder before this check.
                             # The *new* reminder should inherit this incremented count.
                             new_reminder["recurrence_current_count"] = reminder["recurrence_current_count"]
                        else:
                             new_reminder["recurrence_current_count"] = None # Ensure it's None for non-occurrences

                        updated_reminders.append(new_reminder)
                        data_changed = True
                        log_debug(f"Created next occurrence for {reminder_id} with new ID {new_reminder['id']} on {next_date_str}.")

                # Add the original (now notified) reminder
                updated_reminders.append(reminder)
            else:
                # Not due yet, keep as is
                log_debug(f"Reminder {reminder_id} is not yet due.")
                updated_reminders.append(reminder)

        # Save changes if any were made
        if data_changed:
            log_debug("Changes detected, saving reminders.")
            save_reminders(updated_reminders)
        else:
            log_debug("No changes to reminders, skipping save.")

    except Exception as e:
        log_error(f"Error checking due reminders: {e}", exc_info=True)

    log_debug("Finished checking due reminders.")

def delete_past_reminders():
    """Delete reminders from past dates."""
    reminders = load_reminders()
    today = date.today()
    updated_reminders = []
    deleted_count = 0
    
    for reminder in reminders:
        try:
            reminder_date = datetime.strptime(reminder.get("date", ""), "%Y-%m-%d").date()
            if reminder_date < today:
                deleted_count += 1
                log_debug(f"Deleting past reminder: {reminder.get('title')} ({reminder.get('date')})")
                continue
            updated_reminders.append(reminder)
        except ValueError:
            log_error(f"Invalid date format in reminder: {reminder}", exc_info=True)
            updated_reminders.append(reminder)
    
    if deleted_count > 0:
        save_reminders(updated_reminders)
        log_info(f"Deleted {deleted_count} past reminders.")

def run_scheduler():
    log_info("Scheduler thread started.")
    schedule.every(INDIVIDUAL_NOTIFICATION_CHECK_INTERVAL_SECONDS).seconds.do(check_and_notify_due_reminders)
    schedule.every().day.at("00:00").do(delete_past_reminders)
    while not scheduler_stop_event.is_set():
        schedule.run_pending()
        py_time.sleep(1)
    log_info("Scheduler thread stopped.")

# --- GUI HELPER & LOGIC FUNCTIONS --- (Your existing display_reminders_popup)
def display_reminders_popup(reminders_list, title="Today's Upcoming Reminders", parent_window=None):
    temp_root_for_display = None
    if not parent_window or not parent_window.winfo_exists():
        log_debug("display_reminders_popup: No valid parent_window, creating temporary root.")
        temp_root_for_display = tk.Tk()
        temp_root_for_display.withdraw()
    
    current_parent = temp_root_for_display if temp_root_for_display else parent_window

    if not reminders_list:
        messagebox.showinfo(title, "No reminders to show for this period.", parent=current_parent)
        if temp_root_for_display: temp_root_for_display.destroy()
        return

    popup = tk.Toplevel(current_parent) 
    popup.title(title)
    popup.attributes('-topmost', True)
    app_icon_photo = getattr(app_instance_ref, 'app_icon_photo', None)
    if app_icon_photo:
         popup.iconphoto(True, app_icon_photo)
    
    text_area = tk.Text(popup, wrap=tk.WORD, height=7, width=45, padx=10, pady=10)
    text_area.pack(pady=5, fill="both", expand=True)
    text_area.insert(tk.END, f"{title}:\n\n")
    for r_item in reminders_list:
        formatted_time_ampm = format_time_to_ampm(r_item.get('time', 'N/A'))
        text_area.insert(tk.END, f"{formatted_time_ampm} - {r_item.get('title','N/A')}\n")
    text_area.config(state=tk.DISABLED)
    ttk.Button(popup, text="OK", command=popup.destroy).pack(pady=5)
    
    popup.lift(); popup.focus_force()
    popup.wait_window() 
    if temp_root_for_display: temp_root_for_display.destroy()


# --- REMINDER FETCHING LOGIC --- (Your versions)
def get_all_todays_reminders(): # Used by startup_check logic in __main__ for true "today"
    reminders = load_reminders()
    today_actual_str = date.today().strftime("%Y-%m-%d")
    return [r for r in reminders if r.get("date") == today_actual_str]

def get_upcoming_todays_reminders(): # Used by ReminderApp for its initial popup
    reminders = load_reminders()
    today = date.today()
    
    # Your logic to show tomorrow's if it's evening
    current_hour = datetime.now().hour
    if current_hour >= 18: # 6 PM or later
        target_date = today + timedelta(days=1) # Use timedelta for robust date increment
        title_prefix = "Tomorrow's"
    else:
        target_date = today
        title_prefix = "Today's"
        
    target_date_str = target_date.strftime("%Y-%m-%d")
    now_t_for_upcoming = datetime.now().time() # Only for "upcoming" part
    
    upcoming_for_target_day = []
    for r in reminders:
        if r.get("date") == target_date_str:
            if r.get("time"):
                try:
                    reminder_time_obj = datetime.strptime(r["time"], "%H:%M").time()
                    # If target is today, check if reminder time is >= now.
                    # If target is tomorrow, all reminders for that day are "upcoming" from today's perspective.
                    if target_date == today:
                        if reminder_time_obj >= now_t_for_upcoming:
                            upcoming_for_target_day.append(r)
                    else: # Target is tomorrow
                        upcoming_for_target_day.append(r)
                except ValueError:
                    pass # Ignore invalid time format
            else: # No time specified, include if date matches
                 upcoming_for_target_day.append(r)

    return upcoming_for_target_day, title_prefix


# --- SYSTEM TRAY ACTIONS --- (Your existing ones, slightly adapted for app_icon_photo)
def actual_show_main_window():
    global tk_root_window, main_gui_visible
    if tk_root_window and hasattr(tk_root_window, 'deiconify'):
        tk_root_window.deiconify(); tk_root_window.lift(); tk_root_window.focus_force()
        main_gui_visible = True
def show_main_window_action(icon=None, menu_item=None):
    if tk_root_window: tk_root_window.after(0, actual_show_main_window)
def add_reminder_action_from_tray(icon=None, menu_item=None):
    if tk_root_window and app_instance_ref: tk_root_window.after(0, app_instance_ref.open_add_reminder_window)
def quit_application_action(icon=None, menu_item=None):
    global tk_root_window, scheduler_stop_event, tray_icon_object
    log_info("Quit action initiated.")
    scheduler_stop_event.set()
    if tray_icon_object: tray_icon_object.stop()
    if tk_root_window: tk_root_window.after(0, tk_root_window.quit)

def on_main_window_close_button():
    global tk_root_window, main_gui_visible
    if tk_root_window: tk_root_window.withdraw(); main_gui_visible = False
    log_info("App hidden to system tray.")

# --- GUI APPLICATION CLASSES ---
class ReminderApp:
    def __init__(self, root):
        global app_instance_ref; app_instance_ref = self
        self.root = root
        self.root.title(APP_NAME)
        self.root.protocol("WM_DELETE_WINDOW", on_main_window_close_button)
        self.app_icon_photo = None

        try:
            img = Image.open(LOGO_FILE) # Load the image file
            self.app_icon_photo = ImageTk.PhotoImage(img) # Convert for Tkinter
            self.root.iconphoto(True, self.app_icon_photo) # Set as window icon
        except Exception as e:
            log_error(f"Warn: App logo '{LOGO_FILE}' not found/loadable: {e}")
            self.app_icon_photo = None
        
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=10, sticky=tk.EW)

        ttk.Button(button_frame, text="Add", command=self.open_add_reminder_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update", command=self.open_update_reminder_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete", command=self.delete_selected_reminder).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.populate_reminders_list).pack(side=tk.LEFT, padx=5)
        
        # Filter frame
        filter_frame = ttk.Frame(main_frame)
        filter_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky=tk.EW)

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                   values=["All", "Today", "Upcoming", "Past", "Recurring"],
                                   state="readonly", width=10)
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        ttk.Label(filter_frame, text="Sort by:").pack(side=tk.LEFT, padx=5)
        self.sort_var = tk.StringVar(value="Date")
        sort_combo = ttk.Combobox(filter_frame, textvariable=self.sort_var,
                                 values=["Date", "Time", "Title"],
                                 state="readonly", width=10)
        sort_combo.pack(side=tk.LEFT, padx=5)
        sort_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_filters())

        # Title label
        self.title_label = ttk.Label(main_frame, text="Upcoming Reminders", font=("Helvetica", 16, "bold"), anchor="center")
        self.title_label.grid(row=2, column=0, columnspan=2, pady=(5,0), sticky=tk.EW)

        # Treeview
        self.tree = ttk.Treeview(main_frame, columns=("#", "Title", "Date", "Time", "Repeat"), show="headings")
        self.tree.heading("#", text="#", anchor="center")
        self.tree.column("#", width=40, minwidth=30, stretch=tk.NO, anchor="center")

        self.tree.heading("Title", text="Reminder Name")
        self.tree.column("Title", width=250, minwidth=150)
        
        self.tree.heading("Date", text="Date", anchor="center")
        self.tree.column("Date", width=100, minwidth=80, anchor="center")
        
        self.tree.heading("Time", text="Time", anchor="center")
        self.tree.column("Time", width=100, minwidth=80, anchor="center")
        
        self.tree.heading("Repeat", text="Repeat", anchor="center")
        self.tree.column("Repeat", width=80, minwidth=60, anchor="center")

        self.tree.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=3, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)
        main_frame.rowconfigure(3, weight=1)

        self.populate_reminders_list()

        # Now that the default filter is set, populate the list
        self.populate_reminders_list()

    def apply_filters(self):
        """Apply current filter and sort settings to the reminders list."""
        reminders = load_reminders()
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        
        # Apply filter
        filter_type = self.filter_var.get()
        if filter_type == "Today":
            reminders = [r for r in reminders if r.get("date") == today_str]
            self.title_label.config(text="Today's Reminders")
        elif filter_type == "Upcoming":
            reminders = [r for r in reminders if r.get("date") > today_str]
            self.title_label.config(text="Upcoming Reminders")
        elif filter_type == "Past":
            reminders = [r for r in reminders if r.get("date") < today_str]
            self.title_label.config(text="Past Reminders")
        elif filter_type == "Recurring":
            reminders = [r for r in reminders if r.get("recurrence_type")]
            self.title_label.config(text="Recurring Reminders")
        else: # "All"
            self.title_label.config(text="All Reminders")

        # Apply sort
        sort_by = self.sort_var.get()
        if sort_by == "Date":
            reminders.sort(key=lambda r: (r.get("date", ""), r.get("time", "")))
        elif sort_by == "Time":
            reminders.sort(key=lambda r: (r.get("time", ""), r.get("date", "")))
        elif sort_by == "Title":
            reminders.sort(key=lambda r: r.get("title", ""))

        # Update the tree
        for i in self.tree.get_children():
            self.tree.delete(i)

        for idx, reminder in enumerate(reminders):
            formatted_time_ampm = format_time_to_ampm(reminder.get('time', 'N/A'))
            recurrence_type = reminder.get('recurrence_type', 'None')
            if recurrence_type:
                recurrence_display = recurrence_type.capitalize()
            else:
                recurrence_display = "None"
            
            self.tree.insert("", tk.END, iid=reminder.get('id'), values=(
                idx + 1,
                reminder.get('title', 'N/A'),
                reminder.get('date', 'N/A'),
                formatted_time_ampm,
                recurrence_display
            ))

    def populate_reminders_list(self):
        """Populate the reminders list with current filter and sort settings."""
        # Delete past reminders before populating the list
        delete_past_reminders()
        self.apply_filters()

    def open_add_reminder_window(self):
        AddReminderWindow(self.root, self)
        
    def open_update_reminder_window(self):
        selected_item_iids = self.tree.selection()
        if not selected_item_iids:
            messagebox.showwarning("No Selection", "Please select a reminder to update.", parent=self.root)
            return
        if len(selected_item_iids) > 1:
            messagebox.showwarning("Multiple Selections", "Please select only one reminder.", parent=self.root)
            return
        selected_reminder_id = selected_item_iids[0]
        all_reminders = load_reminders()
        reminder_data_to_edit = next((r for r in all_reminders if r.get("id") == selected_reminder_id), None)
        if reminder_data_to_edit is None:
            messagebox.showerror("Error", "Could not find selected reminder. Please refresh.", parent=self.root)
            return
        EditReminderWindow(parent_root=self.root, reminder=reminder_data_to_edit, main_app_ref=self)
    
    def delete_selected_reminder(self):
        selected_item_iids = self.tree.selection()
        if not selected_item_iids:
            messagebox.showwarning("No Selection", "Please select a reminder to delete.", parent=self.root)
            return
        selected_iid = selected_item_iids[0]
        reminder_title_to_delete = ""
        all_reminders = load_reminders()
        for r in all_reminders:
            if r.get('id') == selected_iid:
                reminder_title_to_delete = r.get('title', 'this reminder')
                break
        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{reminder_title_to_delete}'?", parent=self.root)
        if confirm:
            updated_reminders = [r for r in all_reminders if r.get('id') != selected_iid]
            save_reminders(updated_reminders)
            self.populate_reminders_list()
            messagebox.showinfo("Deleted", "Reminder deleted successfully.", parent=self.root)

class AddReminderWindow:
    def __init__(self, parent_root, main_app_ref):
        self.parent = parent_root
        self.main_app = main_app_ref
        self.add_window = tk.Toplevel(self.parent)
        self.add_window.title("Add New Reminder")
        self.add_window.geometry("450x700")  # Increased height for new controls
        self.add_window.transient(self.parent)
        self.add_window.grab_set()
        app_icon_photo = getattr(self.main_app, 'app_icon_photo', None)
        if app_icon_photo: self.add_window.iconphoto(True, app_icon_photo)

        # --- SCROLLABLE FORM SETUP ---
        self.canvas = tk.Canvas(self.add_window, borderwidth=0, background="#f8f8f8") # Make canvas an instance variable
        form_frame = ttk.Frame(self.canvas, padding="15")
        vscrollbar = ttk.Scrollbar(self.add_window, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vscrollbar.set)
        vscrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0, 0), window=form_frame, anchor="nw")

        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        form_frame.bind("<Configure>", on_frame_configure)

        # Add mousewheel scrolling support
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        # Bind mousewheel to the canvas
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        # Optional: bind to the form_frame and its children if canvas doesn't always have focus
        form_frame.bind("<MouseWheel>", _on_mousewheel)
        # Add bindings for Linux/Mac if needed
        self.canvas.bind_all("<Button-4>", _on_mousewheel) # For Linux
        self.canvas.bind_all("<Button-5>", _on_mousewheel) # For Linux

        # Title
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.title_entry = ttk.Entry(form_frame, width=40)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)

        # Date
        ttk.Label(form_frame, text="Date:").grid(row=1, column=0, sticky="nw", padx=5, pady=(10,5))
        self.cal = Calendar(form_frame, selectmode='day', date_pattern='yyyy-mm-dd', font="Arial 9")
        self.cal.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        self.cal.selection_set(date.today())

        # Time with enhanced input
        ttk.Label(form_frame, text="Time:").grid(row=2, column=0, sticky="w", padx=5, pady=(10,5))
        time_input_frame = ttk.Frame(form_frame)
        time_input_frame.grid(row=2, column=1, columnspan=2, sticky="w", padx=5, pady=5)
        
        current_dt = datetime.now()
        self.hour_spinbox = ttk.Spinbox(time_input_frame, from_=1, to=12, width=3, 
                                      format="%02.0f", wrap=True,
                                      command=self.validate_time_input)
        self.hour_spinbox.pack(side=tk.LEFT)
        self.hour_spinbox.set(f"{int(current_dt.strftime('%I')):02}")
        
        ttk.Label(time_input_frame, text=":").pack(side=tk.LEFT, padx=2)
        
        self.minute_spinbox = ttk.Spinbox(time_input_frame, from_=0, to=59, width=3, 
                                        format="%02.0f", wrap=True,
                                        command=self.validate_time_input)
        self.minute_spinbox.pack(side=tk.LEFT)
        self.minute_spinbox.set(current_dt.strftime("%M"))
        
        self.ampm_var = tk.StringVar(value=current_dt.strftime("%p"))
        self.ampm_combobox = ttk.Combobox(time_input_frame, textvariable=self.ampm_var, 
                                         values=["AM", "PM"], width=3, state="readonly")
        self.ampm_combobox.pack(side=tk.LEFT, padx=(5,0))
        
        # Add quick time buttons
        quick_time_frame = ttk.Frame(time_input_frame)
        quick_time_frame.pack(side=tk.TOP, pady=(5,0))
        
        quick_times = ["Now", "Morning", "Noon", "Evening"]
        for time_label in quick_times:
            ttk.Button(quick_time_frame, text=time_label, width=8,
                      command=lambda t=time_label: self.set_quick_time(t)).pack(side=tk.LEFT, padx=2)

        # Enhanced Recurrence Frame
        ttk.Label(form_frame, text="Repeat:").grid(row=3, column=0, sticky="w", padx=5, pady=(10,5))
        recurrence_frame = ttk.Frame(form_frame)
        recurrence_frame.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        
        self.recurrence_var = tk.StringVar(value="None")
        self.recurrence_combobox = ttk.Combobox(recurrence_frame, textvariable=self.recurrence_var,
                                               values=list(RECURRENCE_TYPES.keys()), state="readonly")
        self.recurrence_combobox.pack(side=tk.LEFT, padx=(0,5))
        
        # Add recurrence info label
        self.recurrence_info = ttk.Label(recurrence_frame, text="", font=("Helvetica", 8))
        self.recurrence_info.pack(side=tk.LEFT)
        
        # Bind to update info when selection changes
        self.recurrence_combobox.bind('<<ComboboxSelected>>', self.update_recurrence_info)

        # End Condition Frame
        ttk.Label(form_frame, text="Ends:").grid(row=4, column=0, sticky="w", padx=5, pady=(10,5))
        end_condition_frame = ttk.Frame(form_frame)
        end_condition_frame.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        
        self.end_condition_var = tk.StringVar(value="Never")
        self.end_condition_combobox = ttk.Combobox(end_condition_frame, textvariable=self.end_condition_var,
                                                  values=list(END_CONDITION_TYPES.keys()), state="readonly")
        self.end_condition_combobox.pack(side=tk.LEFT, padx=(0,5))
        
        # Bind to show/hide end condition inputs
        self.end_condition_combobox.bind('<<ComboboxSelected>>', self.update_end_condition_inputs)
        
        # Frame for end condition specific inputs
        self.end_condition_inputs_frame = ttk.Frame(end_condition_frame)
        self.end_condition_inputs_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Occurrences input with default value for new reminder
        self.occurrences_var = tk.StringVar(value="1") # Default for new reminder is "1"
        self.occurrences_spinbox = ttk.Spinbox(self.end_condition_inputs_frame, from_=1, to=MAX_OCCURRENCES,
                                             textvariable=self.occurrences_var, width=5)
        # self.occurrences_spinbox.pack(...) is handled by update_end_condition_inputs

        # Create the "times" label once
        self.occurrences_label = ttk.Label(self.end_condition_inputs_frame, text="times")
        # self.occurrences_label.pack(...) is handled by update_end_condition_inputs
        
        # End date calendar
        self.end_date_cal = Calendar(self.end_condition_inputs_frame, selectmode='day', 
                                   date_pattern='yyyy-mm-dd', font="Arial 9")
        # self.end_date_cal.pack(...) is handled by update_end_condition_inputs when "On Date" is picked

        # Initially hide/show end condition inputs based on default "Never"
        self.update_end_condition_inputs()

        # Save button
        ttk.Button(form_frame, text="Save Reminder", command=self.save_new_reminder).grid(
            row=5, column=0, columnspan=3, pady=20, ipady=4)
        
        form_frame.columnconfigure(1, weight=1)
        self.title_entry.focus_set()

    def validate_time_input(self, *args):
        """Validate time input and ensure proper formatting."""
        try:
            hour = int(self.hour_spinbox.get())
            minute = int(self.minute_spinbox.get())
            
            # Ensure proper ranges
            if hour < 1: self.hour_spinbox.set("01")
            if hour > 12: self.hour_spinbox.set("12")
            if minute < 0: self.minute_spinbox.set("00")
            if minute > 59: self.minute_spinbox.set("59")
            
            # Format with leading zeros
            self.hour_spinbox.set(f"{int(self.hour_spinbox.get()):02}")
            self.minute_spinbox.set(f"{int(self.minute_spinbox.get()):02}")
        except ValueError:
            # If invalid input, reset to current time
            current_dt = datetime.now()
            self.hour_spinbox.set(f"{int(current_dt.strftime('%I')):02}")
            self.minute_spinbox.set(current_dt.strftime("%M"))
            self.ampm_var.set(current_dt.strftime("%p"))

    def set_quick_time(self, time_label):
        """Set time based on quick time selection."""
        current_dt = datetime.now()
        if time_label == "Now":
            self.hour_spinbox.set(f"{int(current_dt.strftime('%I')):02}")
            self.minute_spinbox.set(current_dt.strftime("%M"))
            self.ampm_var.set(current_dt.strftime("%p"))
        elif time_label == "Morning":
            self.hour_spinbox.set("09")
            self.minute_spinbox.set("00")
            self.ampm_var.set("AM")
        elif time_label == "Noon":
            self.hour_spinbox.set("12")
            self.minute_spinbox.set("00")
            self.ampm_var.set("PM")
        elif time_label == "Evening":
            self.hour_spinbox.set("06")
            self.minute_spinbox.set("00")
            self.ampm_var.set("PM")

    def update_recurrence_info(self, event=None):
        """Update the recurrence info label based on selection."""
        recurrence_type = self.recurrence_var.get()
        if recurrence_type == "None":
            self.recurrence_info.config(text="")
        elif recurrence_type == "Daily":
            self.recurrence_info.config(text="Repeats every day")
        elif recurrence_type == "Weekdays":
            self.recurrence_info.config(text="Repeats Monday to Friday")
        elif recurrence_type == "Weekly":
            self.recurrence_info.config(text="Repeats every week")
        elif recurrence_type == "Biweekly":
            self.recurrence_info.config(text="Repeats every two weeks")
        elif recurrence_type == "Monthly":
            self.recurrence_info.config(text="Repeats every month")
        elif recurrence_type == "Yearly":
            self.recurrence_info.config(text="Repeats every year")

    def update_end_condition_inputs(self, event=None):
        """Show/hide end condition specific inputs based on selection."""
        # Hide all inputs first
        self.occurrences_spinbox.pack_forget()
        self.occurrences_label.pack_forget()
        self.end_date_cal.pack_forget()
        
        # Show relevant input based on selection
        end_type = self.end_condition_var.get()
        if end_type == "After":
            self.occurrences_spinbox.pack(side=tk.LEFT, padx=(0,5))
            self.occurrences_label.pack(side=tk.LEFT)
        elif end_type == "On Date":
            self.end_date_cal.pack(side=tk.LEFT, padx=(5,0))
            # Ensure end date is after start date
            start_date = datetime.strptime(self.cal.get_date(), "%Y-%m-%d").date()
            self.end_date_cal.selection_set(start_date + timedelta(days=1))

    def save_new_reminder(self):
        title = self.title_entry.get().strip()
        selected_date_str = self.cal.get_date()
        hour_12_str = self.hour_spinbox.get().strip()
        minute_str = self.minute_spinbox.get().strip()
        ampm_val = self.ampm_var.get()
        recurrence_type = RECURRENCE_TYPES[self.recurrence_var.get()]
        end_condition_type = END_CONDITION_TYPES[self.end_condition_var.get()]

        if not title:
            messagebox.showerror("Input Error", "Title cannot be empty.", parent=self.add_window)
            return

        if not hour_12_str.isdigit() or not minute_str.isdigit():
            messagebox.showerror("Input Error", "Hour/Minute must be numeric.", parent=self.add_window)
            return

        hour_12_int, minute_int = int(hour_12_str), int(minute_str)
        if not (1 <= hour_12_int <= 12 and 0 <= minute_int <= 59):
            messagebox.showerror("Input Error", "Hour/Minute out of range.", parent=self.add_window)
            return

        try:
            time_obj_24h = datetime.strptime(f"{hour_12_int:02}:{minute_int:02} {ampm_val}", "%I:%M %p")
            time_str_24h_to_save = time_obj_24h.strftime("%H:%M")
        except ValueError as e:
            log_error(f"Time conversion error: {e}", exc_info=True)
            messagebox.showerror("Input Error", "Invalid time format.", parent=self.add_window)
            return

        # Validate end conditions
        if end_condition_type == "occurrences":
            try:
                occurrences = int(self.occurrences_var.get())
                if not (1 <= occurrences <= MAX_OCCURRENCES):
                    messagebox.showerror("Input Error", f"Number of occurrences must be between 1 and {MAX_OCCURRENCES}.", 
                                       parent=self.add_window)
                    return
            except ValueError:
                messagebox.showerror("Input Error", "Number of occurrences must be a valid number.", 
                                   parent=self.add_window)
                return
        elif end_condition_type == "date":
            end_date = datetime.strptime(self.end_date_cal.get_date(), "%Y-%m-%d").date()
            start_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if end_date <= start_date:
                messagebox.showerror("Input Error", "End date must be after start date.", 
                                   parent=self.add_window)
                return

        new_reminder = {
            "id": str(uuid.uuid4()),
            "title": title,
            "date": selected_date_str,
            "time": time_str_24h_to_save,
            "notified_individually": False,
            "recurrence_type": recurrence_type,
            "recurrence_end_type": end_condition_type,
            "recurrence_end_value": (
                int(self.occurrences_var.get()) if end_condition_type == "occurrences"
                else self.end_date_cal.get_date() if end_condition_type == "date"
                else None
            ),
            "recurrence_current_count": 0 if end_condition_type == "occurrences" else None,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        reminders = load_reminders()
        reminders.append(new_reminder)
        save_reminders(reminders)
        messagebox.showinfo("Success", "Reminder added!", parent=self.add_window)
        self.main_app.populate_reminders_list()
        self.add_window.destroy()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class EditReminderWindow:
    def __init__(self, parent_root, reminder, main_app_ref):
        self.parent = parent_root
        self.reminder = reminder
        self.main_app = main_app_ref
        self.edit_window = tk.Toplevel(self.parent)
        self.edit_window.title("Edit Reminder")
        self.edit_window.geometry("450x700")  # Increased height for new controls
        self.edit_window.transient(self.parent)
        self.edit_window.grab_set()
        app_icon_photo = getattr(self.main_app, 'app_icon_photo', None)
        if app_icon_photo: self.edit_window.iconphoto(True, app_icon_photo)

        # --- SCROLLABLE FORM SETUP ---
        self.canvas = tk.Canvas(self.edit_window, borderwidth=0, background="#f8f8f8") # Make canvas an instance variable
        form_frame = ttk.Frame(self.canvas, padding="15")
        vscrollbar = ttk.Scrollbar(self.edit_window, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vscrollbar.set)
        vscrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((0, 0), window=form_frame, anchor="nw")

        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        form_frame.bind("<Configure>", on_frame_configure)

        # Add mousewheel scrolling support
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        # Bind mousewheel to the canvas
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        # Optional: bind to the form_frame and its children if canvas doesn't always have focus
        form_frame.bind("<MouseWheel>", _on_mousewheel)
        # Add bindings for Linux/Mac if needed
        self.canvas.bind_all("<Button-4>", _on_mousewheel) # For Linux
        self.canvas.bind_all("<Button-5>", _on_mousewheel) # For Linux

        # Title
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.title_entry = ttk.Entry(form_frame, width=40)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        self.title_entry.insert(0, reminder["title"])

        # Date
        ttk.Label(form_frame, text="Date:").grid(row=1, column=0, sticky="nw", padx=5, pady=(10,5))
        self.cal = Calendar(form_frame, selectmode='day', date_pattern='yyyy-mm-dd', font="Arial 9")
        self.cal.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        self.cal.selection_set(reminder["date"])

        # Time with enhanced input
        ttk.Label(form_frame, text="Time:").grid(row=2, column=0, sticky="w", padx=5, pady=(10,5))
        time_input_frame = ttk.Frame(form_frame)
        time_input_frame.grid(row=2, column=1, columnspan=2, sticky="w", padx=5, pady=5)
        
        # Parse existing time
        time_obj = datetime.strptime(reminder["time"], "%H:%M")
        hour_12 = int(time_obj.strftime("%I"))
        minute = int(time_obj.strftime("%M"))
        ampm = time_obj.strftime("%p")
        
        self.hour_spinbox = ttk.Spinbox(time_input_frame, from_=1, to=12, width=3, 
                                      format="%02.0f", wrap=True,
                                      command=self.validate_time_input)
        self.hour_spinbox.pack(side=tk.LEFT)
        self.hour_spinbox.set(f"{hour_12:02}")
        
        ttk.Label(time_input_frame, text=":").pack(side=tk.LEFT, padx=2)
        
        self.minute_spinbox = ttk.Spinbox(time_input_frame, from_=0, to=59, width=3, 
                                        format="%02.0f", wrap=True,
                                        command=self.validate_time_input)
        self.minute_spinbox.pack(side=tk.LEFT)
        self.minute_spinbox.set(f"{minute:02}")
        
        self.ampm_var = tk.StringVar(value=ampm)
        self.ampm_combobox = ttk.Combobox(time_input_frame, textvariable=self.ampm_var, 
                                         values=["AM", "PM"], width=3, state="readonly")
        self.ampm_combobox.pack(side=tk.LEFT, padx=(5,0))
        
        # Add quick time buttons
        quick_time_frame = ttk.Frame(time_input_frame)
        quick_time_frame.pack(side=tk.TOP, pady=(5,0))
        
        quick_times = ["Now", "Morning", "Noon", "Evening"]
        for time_label in quick_times:
            ttk.Button(quick_time_frame, text=time_label, width=8,
                      command=lambda t=time_label: self.set_quick_time(t)).pack(side=tk.LEFT, padx=2)

        # Enhanced Recurrence Frame
        ttk.Label(form_frame, text="Repeat:").grid(row=3, column=0, sticky="w", padx=5, pady=(10,5))
        recurrence_frame = ttk.Frame(form_frame)
        recurrence_frame.grid(row=3, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        
        # Get current recurrence type
        current_recurrence = next((k for k, v in RECURRENCE_TYPES.items() if v == reminder.get("recurrence_type", "none")), "None")
        self.recurrence_var = tk.StringVar(value=current_recurrence)
        self.recurrence_combobox = ttk.Combobox(recurrence_frame, textvariable=self.recurrence_var,
                                               values=list(RECURRENCE_TYPES.keys()), state="readonly")
        self.recurrence_combobox.pack(side=tk.LEFT, padx=(0,5))
        
        # Add recurrence info label
        self.recurrence_info = ttk.Label(recurrence_frame, text="", font=("Helvetica", 8))
        self.recurrence_info.pack(side=tk.LEFT)
        
        # Bind to update info when selection changes
        self.recurrence_combobox.bind('<<ComboboxSelected>>', self.update_recurrence_info)
        self.update_recurrence_info()  # Initial update

        # End Condition Frame
        ttk.Label(form_frame, text="Ends:").grid(row=4, column=0, sticky="w", padx=5, pady=(10,5))
        end_condition_frame = ttk.Frame(form_frame)
        end_condition_frame.grid(row=4, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        
        # Get current end condition
        current_end_type = next((k for k, v in END_CONDITION_TYPES.items() 
                               if v == reminder.get("recurrence_end_type", "never")), "Never")
        self.end_condition_var = tk.StringVar(value=current_end_type)
        self.end_condition_combobox = ttk.Combobox(end_condition_frame, textvariable=self.end_condition_var,
                                                  values=list(END_CONDITION_TYPES.keys()), state="readonly")
        self.end_condition_combobox.pack(side=tk.LEFT, padx=(0,5))
        
        # Bind to show/hide end condition inputs
        self.end_condition_combobox.bind('<<ComboboxSelected>>', self.update_end_condition_inputs)
        
        # Frame for end condition specific inputs
        self.end_condition_inputs_frame = ttk.Frame(end_condition_frame)
        self.end_condition_inputs_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Occurrences input with proper default value
        occurrence_val_for_spinbox = "1"  # Default
        if reminder.get("recurrence_end_type") == "occurrences":
            stored_val = reminder.get("recurrence_end_value")
            if isinstance(stored_val, int) and stored_val >= 1:
                occurrence_val_for_spinbox = str(stored_val)
        self.occurrences_var = tk.StringVar(value=occurrence_val_for_spinbox)
        self.occurrences_spinbox = ttk.Spinbox(self.end_condition_inputs_frame, from_=1, to=MAX_OCCURRENCES,
                                             textvariable=self.occurrences_var, width=5)
        self.occurrences_spinbox.pack(side=tk.LEFT, padx=(0,5))
        
        # Create the "times" label once
        self.occurrences_label = ttk.Label(self.end_condition_inputs_frame, text="times")
        
        # End date calendar
        self.end_date_cal = Calendar(self.end_condition_inputs_frame, selectmode='day', 
                                   date_pattern='yyyy-mm-dd', font="Arial 9")
        self.end_date_cal.pack(side=tk.LEFT, padx=(5,0))
        
        # Set initial end date if exists
        if reminder.get("recurrence_end_type") == "date" and reminder.get("recurrence_end_value"):
            self.end_date_cal.selection_set(reminder["recurrence_end_value"])
        
        # Initially hide end condition inputs
        self.update_end_condition_inputs()

        # Save button
        ttk.Button(form_frame, text="Save Changes", command=self.save_updated_reminder).grid(
            row=5, column=0, columnspan=3, pady=20, ipady=4)
        
        form_frame.columnconfigure(1, weight=1)
        self.title_entry.focus_set()

    def validate_time_input(self, *args):
        """Validate time input and ensure proper formatting."""
        try:
            hour = int(self.hour_spinbox.get())
            minute = int(self.minute_spinbox.get())
            
            # Ensure proper ranges
            if hour < 1: self.hour_spinbox.set("01")
            if hour > 12: self.hour_spinbox.set("12")
            if minute < 0: self.minute_spinbox.set("00")
            if minute > 59: self.minute_spinbox.set("59")
            
            # Format with leading zeros
            self.hour_spinbox.set(f"{int(self.hour_spinbox.get()):02}")
            self.minute_spinbox.set(f"{int(self.minute_spinbox.get()):02}")
        except ValueError:
            # If invalid input, reset to current time
            current_dt = datetime.now()
            self.hour_spinbox.set(f"{int(current_dt.strftime('%I')):02}")
            self.minute_spinbox.set(current_dt.strftime("%M"))
            self.ampm_var.set(current_dt.strftime("%p"))

    def set_quick_time(self, time_label):
        """Set time based on quick time selection."""
        current_dt = datetime.now()
        if time_label == "Now":
            self.hour_spinbox.set(f"{int(current_dt.strftime('%I')):02}")
            self.minute_spinbox.set(current_dt.strftime("%M"))
            self.ampm_var.set(current_dt.strftime("%p"))
        elif time_label == "Morning":
            self.hour_spinbox.set("09")
            self.minute_spinbox.set("00")
            self.ampm_var.set("AM")
        elif time_label == "Noon":
            self.hour_spinbox.set("12")
            self.minute_spinbox.set("00")
            self.ampm_var.set("PM")
        elif time_label == "Evening":
            self.hour_spinbox.set("06")
            self.minute_spinbox.set("00")
            self.ampm_var.set("PM")

    def update_recurrence_info(self, event=None):
        """Update the recurrence info label based on selection."""
        recurrence_type = self.recurrence_var.get()
        if recurrence_type == "None":
            self.recurrence_info.config(text="")
        elif recurrence_type == "Daily":
            self.recurrence_info.config(text="Repeats every day")
        elif recurrence_type == "Weekdays":
            self.recurrence_info.config(text="Repeats Monday to Friday")
        elif recurrence_type == "Weekly":
            self.recurrence_info.config(text="Repeats every week")
        elif recurrence_type == "Biweekly":
            self.recurrence_info.config(text="Repeats every two weeks")
        elif recurrence_type == "Monthly":
            self.recurrence_info.config(text="Repeats every month")
        elif recurrence_type == "Yearly":
            self.recurrence_info.config(text="Repeats every year")

    def update_end_condition_inputs(self, event=None):
        """Show/hide end condition specific inputs based on selection."""
        # Hide all inputs first
        self.occurrences_spinbox.pack_forget()
        self.occurrences_label.pack_forget()
        self.end_date_cal.pack_forget()
        
        # Show relevant input based on selection
        end_type = self.end_condition_var.get()
        if end_type == "After":
            self.occurrences_spinbox.pack(side=tk.LEFT, padx=(0,5))
            self.occurrences_label.pack(side=tk.LEFT)
        elif end_type == "On Date":
            self.end_date_cal.pack(side=tk.LEFT, padx=(5,0))
            # Ensure end date is after start date
            start_date = datetime.strptime(self.cal.get_date(), "%Y-%m-%d").date()
            self.end_date_cal.selection_set(start_date + timedelta(days=1))

    def save_updated_reminder(self):
        title = self.title_entry.get().strip()
        selected_date_str = self.cal.get_date()
        hour_12_str = self.hour_spinbox.get().strip()
        minute_str = self.minute_spinbox.get().strip()
        ampm_val = self.ampm_var.get()
        recurrence_type = RECURRENCE_TYPES[self.recurrence_var.get()]
        end_condition_type = END_CONDITION_TYPES[self.end_condition_var.get()]

        if not title:
            messagebox.showerror("Input Error", "Title cannot be empty.", parent=self.edit_window)
            return
        
        if not hour_12_str.isdigit() or not minute_str.isdigit():
            messagebox.showerror("Input Error", "Hour/Minute must be numeric.", parent=self.edit_window)
            return

        hour_12_int, minute_int = int(hour_12_str), int(minute_str)
        if not (1 <= hour_12_int <= 12 and 0 <= minute_int <= 59):
            messagebox.showerror("Input Error", "Hour/Minute out of range.", parent=self.edit_window)
            return

        try:
            time_obj_24h = datetime.strptime(f"{hour_12_int:02}:{minute_int:02} {ampm_val}", "%I:%M %p")
            time_str_24h_to_save = time_obj_24h.strftime("%H:%M")
        except ValueError as e:
            log_error(f"Time conversion error: {e}", exc_info=True)
            messagebox.showerror("Input Error", "Invalid time format.", parent=self.edit_window)
            return

        # Validate end conditions
        if end_condition_type == "occurrences":
            try:
                occurrences = int(self.occurrences_var.get())
                if not (1 <= occurrences <= MAX_OCCURRENCES):
                    messagebox.showerror("Input Error", f"Number of occurrences must be between 1 and {MAX_OCCURRENCES}.", parent=self.edit_window)
                    return
            except ValueError:
                messagebox.showerror("Input Error", "Number of occurrences must be a valid number.", parent=self.edit_window)
                return
        elif end_condition_type == "date":
            end_date = datetime.strptime(self.end_date_cal.get_date(), "%Y-%m-%d").date()
            start_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            if end_date <= start_date:
                messagebox.showerror("Input Error", "End date must be after start date.", 
                                   parent=self.edit_window)
                return

        # Determine if recurrence parameters changed
        did_start_date_change = self.reminder["date"] != selected_date_str
        did_time_change = self.reminder["time"] != time_str_24h_to_save
        did_recurrence_rule_change = (
            self.reminder.get("recurrence_type") != recurrence_type or
            self.reminder.get("recurrence_end_type") != end_condition_type or
            self.reminder.get("recurrence_end_value") != (
                int(self.occurrences_var.get()) if end_condition_type == "occurrences"
                else self.end_date_cal.get_date() if end_condition_type == "date"
                else None
            )
        )

        # Handle recurrence count
        current_count_to_save = None
        if end_condition_type == "occurrences":
            if (self.reminder.get("recurrence_end_type") == "occurrences" and
                not (did_start_date_change or did_recurrence_rule_change)):
                # Preserve existing count if no fundamental changes
                current_count_to_save = self.reminder.get("recurrence_current_count", 0)
            else:
                # Reset count for new occurrences type or fundamental changes
                current_count_to_save = 0

        # Update reminder data
        self.reminder.update({
            "title": title,
            "date": selected_date_str,
            "time": time_str_24h_to_save,
            "recurrence_type": recurrence_type,
            "recurrence_end_type": end_condition_type,
            "recurrence_end_value": (
                int(self.occurrences_var.get()) if end_condition_type == "occurrences"
                else self.end_date_cal.get_date() if end_condition_type == "date"
                else None
            ),
            "recurrence_current_count": current_count_to_save
        })

        # Reset notification status if date or time changed
        if did_start_date_change or did_time_change:
            self.reminder["notified_individually"] = False
            log_debug(f"Resetting notification status for reminder {self.reminder.get('id')} due to date/time change.")

        # Save changes
        reminders = load_reminders()
        for i, r in enumerate(reminders):
            if r["id"] == self.reminder["id"]:
                reminders[i] = self.reminder
                break
        save_reminders(reminders)
        messagebox.showinfo("Success", "Reminder updated!", parent=self.edit_window)
        self.main_app.populate_reminders_list()
        self.edit_window.destroy()


# --- SYSTEM TRAY ICON SETUP ---
def setup_system_tray(): # Your version from the provided code
    global tray_icon_object
    try:
        pil_image = Image.open(LOGO_FILE)
        menu_items = (item('Show App', show_main_window_action, default=True),
                      item('Add Reminder', add_reminder_action_from_tray),
                      Menu.SEPARATOR,
                      item('Quit', quit_application_action))
        tray_icon_object = pystray.Icon(APP_NAME, pil_image, APP_NAME, menu_items)
        log_info("Starting tray icon thread...")
        tray_icon_object.run() # This blocks until tray_icon_object.stop() is called
        log_info("Tray icon thread finished.")
    except FileNotFoundError:
        log_error(f"Error: Tray icon image '{LOGO_FILE}' not found. Tray icon disabled.")
    except Exception as e:
        log_error(f"Error setting up system tray: {e}")

# --- MODIFIED MAIN EXECUTION ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        '--startup-mode',
        choices=['normal', 'autostart_with_daily_check', 'minimized_only', 'startup_check_only'],
        default='normal',
        help="Defines how the application starts."
    )
    
    args, unknown_args = parser.parse_known_args()
    effective_startup_mode = args.startup_mode

    if len(sys.argv) > 1 and sys.argv[1] == 'startup_check' and effective_startup_mode != 'startup_check_only':
        log_info("Legacy 'startup_check' positional argument detected. Overriding to 'startup_check_only' mode.")
        effective_startup_mode = 'startup_check_only'

    is_full_app_run = (effective_startup_mode not in ['startup_check_only'])
    if is_full_app_run:
        check_single_instance()

    try:
        if effective_startup_mode == 'startup_check_only':
            log_info("Running in 'startup_check_only' mode (utility popup and exit)...")
            temp_utility_root = tk.Tk()
            temp_utility_root.withdraw()
            
            app_config_util = load_app_config()
            last_check_util = app_config_util.get("last_daily_popup_date")
            today_str_util = date.today().strftime("%Y-%m-%d")

            if last_check_util != today_str_util:
                log_info(f"'startup_check_only' mode: Performing daily reminder summary for {today_str_util}.")
                todays_reminders_list_util = get_all_todays_reminders()
                if todays_reminders_list_util:
                    display_reminders_popup(todays_reminders_list_util, f"Reminders for Today ({today_str_util})", temp_utility_root)
                app_config_util["last_daily_popup_date"] = today_str_util
                save_app_config(app_config_util)
                log_info("'startup_check_only' mode: Check complete.")
            else:
                log_info(f"'startup_check_only' mode: Daily summary already shown for {today_str_util} or no reminders for today.")
            
            temp_utility_root.destroy()
            sys.exit(0)

        log_info(f"{APP_NAME} starting in full application mode: {effective_startup_mode}")

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

        main_window_root = tk.Tk()
        tk_root_window = main_window_root

        show_main_window_initially = True
        
        if effective_startup_mode == 'autostart_with_daily_check':
            app_config = load_app_config()
            last_daily_popup_date = app_config.get("last_daily_popup_date")
            today_str = date.today().strftime("%Y-%m-%d")
            if last_daily_popup_date != today_str:
                log_info(f"Mode 'autostart_with_daily_check': Performing daily startup reminder summary for {today_str}.")
                todays_reminders_list = get_all_todays_reminders()
                if todays_reminders_list:
                    display_reminders_popup(todays_reminders_list, f"Reminders for Today ({today_str})", parent_window=tk_root_window)
                app_config["last_daily_popup_date"] = today_str
                save_app_config(app_config)
                log_info("Daily startup reminder summary complete.")
            else:
                log_info(f"Mode 'autostart_with_daily_check': Daily summary already shown for {today_str} or no reminders for today.")
            show_main_window_initially = False

        elif effective_startup_mode == 'minimized_only':
            log_info("Mode 'minimized_only': Starting minimized to tray.")
            show_main_window_initially = False

        main_gui_visible = show_main_window_initially
        app = ReminderApp(main_window_root)

        if not show_main_window_initially:
            main_window_root.withdraw()
            main_gui_visible = False
            log_info(f"{APP_NAME} UI started and minimized to tray.")
        else:
            log_info(f"{APP_NAME} UI started with main window visible.")

        tray_thread = threading.Thread(target=setup_system_tray, daemon=True)
        tray_thread.start()

        log_info("Main GUI and Threads initialized. Entering Tkinter mainloop.")
        main_window_root.mainloop()

    except SystemExit:
        log_info("Application exited via sys.exit().")
        pass
    except Exception as e:
        log_error(f"An unhandled error occurred in main: {e}", exc_info=True)
        try:
            error_parent = tk_root_window if 'tk_root_window' in globals() and tk_root_window and tk_root_window.winfo_exists() else None
            if not error_parent:
                temp_error_root = tk.Tk()
                temp_error_root.withdraw()
                error_parent = temp_error_root
            
            messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}\nThe application might need to close.", parent=error_parent)
            
            if not ('tk_root_window' in globals() and tk_root_window and tk_root_window.winfo_exists()):
                temp_error_root.destroy()
        except Exception as e_msgbox:
            log_error(f"Could not display error in messagebox: {e_msgbox}")
    finally:
        log_info("Application is exiting. Cleaning up...")
        if 'scheduler_thread' in locals() and scheduler_thread.is_alive() and not scheduler_stop_event.is_set():
            log_info("Stopping scheduler thread...")
            scheduler_stop_event.set()
            scheduler_thread.join(timeout=3)
            if scheduler_thread.is_alive():
                log_warning("Scheduler thread did not stop in time.")
        log_info(f"{APP_NAME} finished.")