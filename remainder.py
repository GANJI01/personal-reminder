import json
from datetime import date, datetime, time # Ensure time is imported from datetime
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
        application_path = os.path.dirname(sys.executable)
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

INDIVIDUAL_NOTIFICATION_CHECK_INTERVAL_SECONDS = 1 # As per your setting
NOTIFICATION_WINDOW_MINUTES = 0 # As per your setting (affects check_and_notify_due_reminders old logic, new logic is different)


# --- SINGLE INSTANCE LOCK ---
def check_single_instance():
    # This check should ideally only prevent multiple *full app instances*.
    # The `startup_check` might be okay to run even if the main app is running,
    # or we ensure it's very quick and cleans up its own (if it used a lock).
    # For now, this global lock will prevent any second launch if lock exists.
    if os.path.exists(LOCK_FILE):
        # Check if the process ID in the lock file is still running (more robust)
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read())
            # Simple check if process exists (platform dependent, this is a basic try)
            # On Windows, os.kill(pid, 0) with signal 0 can check existence.
            # On POSIX, same. But permissions can be an issue.
            # For simplicity, we'll stick to file existence, but this can be improved.
            # If process with pid is not running, old lock file should be removed.
            # For now, if file exists, assume another instance is active.
            print(f"Lock file '{LOCK_FILE}' exists. Another instance might be running or exited uncleanly.")
            messagebox.showwarning(APP_NAME, "Another instance of the application appears to be running.\nIf not, please delete the 'app.lock' file.")
            sys.exit(0) # Exit if lock file exists
        except Exception as e:
            print(f"Error checking lock file PID: {e}. Assuming another instance or stale lock.")
            # Fallback to simple existence check if PID reading fails
            messagebox.showwarning(APP_NAME, "Could not verify lock file. Another instance might be running.")
            sys.exit(0)


    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(cleanup_lock_file) # Ensure cleanup on normal exit

def cleanup_lock_file():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            print("Lock file cleaned up.")
        except Exception as e:
            print(f"Error cleaning up lock file: {e}")

# --- GLOBAL VARIABLES --- (Your existing ones)
tk_root_window = None
scheduler_stop_event = threading.Event()
app_instance_ref = None
tray_icon_object = None
main_gui_visible = True

# --- DATA HANDLING FUNCTIONS --- (Your existing ones)
def load_reminders():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f:
            content = f.read()
            if not content.strip(): return []
            reminders = json.loads(content)
            if not isinstance(reminders, list): return []
            reminders.sort(key=lambda r: (str(r.get("date", "")), str(r.get("time", ""))))
            return reminders
    except Exception as e:
        print(f"Error loading reminders: {e}")
        messagebox.showerror("Load Error", f"Could not load reminders from {DATA_FILE}.\nError: {e}")
        return []

def save_reminders(reminders):
    try:
        reminders.sort(key=lambda r: (str(r.get("date", "")), str(r.get("time", ""))))
        with open(DATA_FILE, 'w') as f:
            json.dump(reminders, f, indent=4)
    except Exception as e:
        print(f"Error saving reminders: {e}")
        messagebox.showerror("Save Error", f"Could not save reminders to {DATA_FILE}.\nError: {e}")

def load_app_config():
    if not os.path.exists(CONFIG_FILE): return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
            if not content.strip(): return {}
            return json.loads(content)
    except Exception as e:
        print(f"Error loading app config: {e}")
        return {}

def save_app_config(config_data):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error saving app config: {e}")

# --- TIME FORMATTING --- (Your existing one)
def format_time_to_ampm(time_str_24h):
    if not time_str_24h: return "N/A"
    try:
        t_obj = datetime.strptime(time_str_24h, "%H:%M").time()
        return t_obj.strftime("%I:%M %p")
    except ValueError:
        return time_str_24h

# --- NOTIFICATION & SCHEDULER --- (Your existing, with your check_and_notify_due_reminders logic)
def show_individual_reminder_popup_thread_safe(title, reminder_time_24h):
    if tk_root_window:
        tk_root_window.after(0, lambda t=title, rt=reminder_time_24h: actual_show_individual_popup(t, rt))

def actual_show_individual_popup(reminder_title, reminder_time_24h):
    try:
        popup = tk.Toplevel(tk_root_window)
        popup.title("Reminder Due!")
        popup.attributes('-topmost', True)
        app_icon_photo = getattr(app_instance_ref, 'app_icon_photo', None) # Use a clearly named attribute
        if app_icon_photo:
             popup.iconphoto(True, app_icon_photo)
        
        formatted_time_ampm = format_time_to_ampm(reminder_time_24h)
        label_text = f"Reminder: {reminder_title}\nTime: {formatted_time_ampm}"
        
        label = ttk.Label(popup, text=label_text, padding="20", wraplength=300, justify=tk.CENTER)
        label.pack(pady=10, padx=10)
        ttk.Button(popup, text="OK", command=popup.destroy).pack(pady=10)
        popup.lift(); popup.focus_force()
    except Exception as e: print(f"Error in actual_show_individual_popup: {e}")

def mark_reminder_as_notified(reminder_id):
    reminders = load_reminders()
    for r in reminders:
        if r.get("id") == reminder_id: r["notified_individually"] = True; break
    save_reminders(reminders)

def check_and_notify_due_reminders(): # Your version of this logic
    reminders = load_reminders()
    today_str = date.today().strftime("%Y-%m-%d")
    now_dt = datetime.now()
    for r in reminders:
        if r.get("notified_individually", False): continue
        if r.get("date") == today_str and r.get("time"):
            try:
                r_dt = datetime.strptime(f"{today_str} {r['time']}", "%Y-%m-%d %H:%M")
                diff_seconds = (now_dt - r_dt).total_seconds()
                if 0 <= diff_seconds < 10 : # Your 10-second window
                    show_individual_reminder_popup_thread_safe(r.get("title"), r.get("time"))
                    mark_reminder_as_notified(r.get("id"))
            except ValueError: pass

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
                continue
            updated_reminders.append(reminder)
        except ValueError:
            # If date is invalid, keep the reminder
            updated_reminders.append(reminder)
    
    if deleted_count > 0:
        save_reminders(updated_reminders)
        print(f"Deleted {deleted_count} past reminders.")

def run_scheduler():
    print("Scheduler thread started.")
    schedule.every(INDIVIDUAL_NOTIFICATION_CHECK_INTERVAL_SECONDS).seconds.do(check_and_notify_due_reminders)
    # Add daily cleanup of past reminders at midnight
    schedule.every().day.at("00:00").do(delete_past_reminders)
    while not scheduler_stop_event.is_set():
        schedule.run_pending(); py_time.sleep(1)
    print("Scheduler thread stopped.")

# --- GUI HELPER & LOGIC FUNCTIONS --- (Your existing display_reminders_popup)
def display_reminders_popup(reminders_list, title="Today's Upcoming Reminders", parent_window=None):
    temp_root_for_display = None
    if not parent_window or not parent_window.winfo_exists():
        print("display_reminders_popup: No valid parent_window, creating temporary root.")
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
    print("Quit action initiated.")
    scheduler_stop_event.set()
    if tray_icon_object: tray_icon_object.stop()
    if tk_root_window: tk_root_window.after(0, tk_root_window.quit)

def on_main_window_close_button():
    global tk_root_window, main_gui_visible
    if tk_root_window: tk_root_window.withdraw(); main_gui_visible = False
    print("App hidden to system tray.")

# --- GUI APPLICATION CLASSES ---
class ReminderApp:
    def __init__(self, root):
        global app_instance_ref; app_instance_ref = self # Assign global reference
        self.root = root
        self.root.title(APP_NAME)
        self.root.protocol("WM_DELETE_WINDOW", on_main_window_close_button)
        self.app_icon_photo = None # Store PhotoImage here to prevent garbage collection

        try:
            img = Image.open(LOGO_FILE)
            self.app_icon_photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, self.app_icon_photo)
        except Exception as e:
            print(f"Warn: App logo '{LOGO_FILE}' not found/loadable: {e}")
            self.app_icon_photo = None
        
        # --- Your UI structure from the provided code ---
        style = ttk.Style()
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'))

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=10, sticky=tk.EW) # Sticky EW

        ttk.Button(button_frame, text="Add", command=self.open_add_reminder_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Update", command=self.open_update_reminder_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete", command=self.delete_selected_reminder).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.populate_reminders_list).pack(side=tk.LEFT, padx=5)
        
        # Centering the title label using grid
        self.title_label = ttk.Label(main_frame, text="All Reminders", font=("Helvetica", 16, "bold"), anchor="center")
        self.title_label.grid(row=1, column=0, columnspan=2, pady=(5,0), sticky=tk.EW)


        self.tree = ttk.Treeview(main_frame, columns=("#", "Title", "Date", "Time"), show="headings") # Added "#"
        self.tree.heading("#", text="#", anchor="center") # Added "#"
        self.tree.column("#", width=40, minwidth=30, stretch=tk.NO, anchor="center") # Added "#"

        self.tree.heading("Title", text="Reminder Name")
        self.tree.column("Title", width=300, minwidth=150)
        self.tree.heading("Date", text="Date", anchor="center")
        self.tree.column("Date", width=100, minwidth=80, anchor="center")
        self.tree.heading("Time", text="Time", anchor="center")
        self.tree.column("Time", width=100, minwidth=80, anchor="center")
        self.tree.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S)) # Changed row

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky=(tk.N, tk.S)) # Changed row, made column 1
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1) # Treeview column
        main_frame.columnconfigure(1, weight=0) # Scrollbar column
        main_frame.rowconfigure(2, weight=1)    # Treeview row (changed from 1 to 2)

        self.populate_reminders_list()
        # self.setup_system_tray() # Moved to __main__ to avoid issues with multiple tray icons on re-show
        
        # Only show this pop-up if not started hidden (i.e., user launched normally)
        # And perhaps only if no other instance is just showing the startup_check pop-up.
        # For simplicity, let's tie it to main_gui_visible being True initially.
        if main_gui_visible: # This global is set in __main__
             self.show_app_init_reminders_popup()


    def show_app_init_reminders_popup(self): # Renamed from show_startup_reminders for clarity
        reminders, title_prefix = get_upcoming_todays_reminders() # Now returns a tuple
        if reminders:
            display_reminders_popup(reminders, f"{title_prefix} Upcoming Reminders", self.root)

    def populate_reminders_list(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        all_reminders = load_reminders()
        if not all_reminders: return
        for idx, reminder in enumerate(all_reminders):
            formatted_time_ampm = format_time_to_ampm(reminder.get('time', 'N/A'))
            self.tree.insert("", tk.END, iid=reminder.get('id'), values=(
                idx + 1, # For the '#' column
                reminder.get('title', 'N/A'),
                reminder.get('date', 'N/A'),
                formatted_time_ampm
            ))

    def open_add_reminder_window(self): AddReminderWindow(self.root, self)
        
    def open_update_reminder_window(self):
        # print("DEBUG: NOW INSIDE THE CORRECT open_update_reminder_window METHOD!")
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
        EditReminderWindow(parent_root=self.root, main_app_ref=self, reminder_to_edit=reminder_data_to_edit)
    
    def delete_selected_reminder(self): # Your existing, seems okay
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

class AddReminderWindow: # Your existing, seems okay with AM/PM
    def __init__(self, parent_root, main_app_ref):
        self.parent = parent_root
        self.main_app = main_app_ref
        self.add_window = tk.Toplevel(self.parent)
        self.add_window.title("Add New Reminder")
        self.add_window.geometry("450x550")
        self.add_window.transient(self.parent)
        self.add_window.grab_set()
        app_icon_photo = getattr(self.main_app, 'app_icon_photo', None)
        if app_icon_photo: self.add_window.iconphoto(True, app_icon_photo)

        form_frame = ttk.Frame(self.add_window, padding="15")
        form_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.title_entry = ttk.Entry(form_frame, width=40)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        ttk.Label(form_frame, text="Date:").grid(row=1, column=0, sticky="nw", padx=5, pady=(10,5))
        self.cal = Calendar(form_frame, selectmode='day', date_pattern='yyyy-mm-dd', font="Arial 9")
        self.cal.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        self.cal.selection_set(date.today())
        ttk.Label(form_frame, text="Time:").grid(row=2, column=0, sticky="w", padx=5, pady=(10,5))
        time_input_frame = ttk.Frame(form_frame)
        time_input_frame.grid(row=2, column=1, columnspan=2, sticky="w", padx=5, pady=5)
        current_dt = datetime.now()
        self.hour_spinbox = ttk.Spinbox(time_input_frame, from_=1, to=12, width=3, format="%02.0f", wrap=True)
        self.hour_spinbox.pack(side=tk.LEFT); self.hour_spinbox.set(f"{int(current_dt.strftime('%I')):02}")
        ttk.Label(time_input_frame, text=":").pack(side=tk.LEFT, padx=2)
        self.minute_spinbox = ttk.Spinbox(time_input_frame, from_=0, to=59, width=3, format="%02.0f", wrap=True)
        self.minute_spinbox.pack(side=tk.LEFT); self.minute_spinbox.set(current_dt.strftime("%M"))
        self.ampm_var = tk.StringVar(value=current_dt.strftime("%p"))
        self.ampm_combobox = ttk.Combobox(time_input_frame, textvariable=self.ampm_var, values=["AM", "PM"], width=3, state="readonly")
        self.ampm_combobox.pack(side=tk.LEFT, padx=(5,0))
        ttk.Button(form_frame, text="Save Reminder", command=self.save_new_reminder).grid(row=3, column=0, columnspan=3, pady=20,ipady=4)
        form_frame.columnconfigure(1, weight=1); self.title_entry.focus_set()

    def save_new_reminder(self): # Your existing save logic for new reminders
        title = self.title_entry.get().strip()
        selected_date_str = self.cal.get_date()
        hour_12_str, minute_str, ampm_val = self.hour_spinbox.get().strip(), self.minute_spinbox.get().strip(), self.ampm_var.get()
        if not title: messagebox.showerror("Input Error", "Title cannot be empty.", parent=self.add_window); return
        if not hour_12_str.isdigit() or not minute_str.isdigit(): messagebox.showerror("Input Error", "Hour/Minute invalid.", parent=self.add_window); return
        hour_12_int, minute_int = int(hour_12_str), int(minute_str)
        if not (1 <= hour_12_int <= 12 and 0 <= minute_int <= 59): messagebox.showerror("Input Error", "Hour/Minute out of range.", parent=self.add_window); return
        try:
            time_obj_24h = datetime.strptime(f"{hour_12_int:02}:{minute_int:02} {ampm_val}", "%I:%M %p")
            time_str_24h_to_save = time_obj_24h.strftime("%H:%M")
        except ValueError: messagebox.showerror("Input Error", "Invalid time format.", parent=self.add_window); return
        new_reminder = {"id": str(uuid.uuid4()), "title": title, "date": selected_date_str, "time": time_str_24h_to_save, "notified_individually": False}
        reminders = load_reminders(); reminders.append(new_reminder); save_reminders(reminders)
        messagebox.showinfo("Success", "Reminder added!", parent=self.add_window)
        self.main_app.populate_reminders_list(); self.add_window.destroy()

class EditReminderWindow: # Your existing, with placeholder save
    def __init__(self, parent_root, main_app_ref, reminder_to_edit):
        self.parent = parent_root; self.main_app = main_app_ref; self.reminder_to_edit = reminder_to_edit
        self.edit_window = tk.Toplevel(self.parent); self.edit_window.title("Edit Reminder")
        self.edit_window.geometry("450x550"); self.edit_window.transient(self.parent); self.edit_window.grab_set()
        app_icon_photo = getattr(self.main_app, 'app_icon_photo', None)
        if app_icon_photo: self.edit_window.iconphoto(True, app_icon_photo)

        form_frame = ttk.Frame(self.edit_window, padding="15"); form_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.title_entry = ttk.Entry(form_frame, width=40)
        self.title_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        self.title_entry.insert(0, self.reminder_to_edit.get("title", ""))
        ttk.Label(form_frame, text="Date:").grid(row=1, column=0, sticky="nw", padx=5, pady=(10,5))
        self.cal = Calendar(form_frame, selectmode='day', date_pattern='yyyy-mm-dd', font="Arial 9")
        self.cal.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        try: self.cal.selection_set(datetime.strptime(self.reminder_to_edit.get("date"), "%Y-%m-%d").date())
        except: self.cal.selection_set(date.today())
        ttk.Label(form_frame, text="Time:").grid(row=2, column=0, sticky="w", padx=5, pady=(10,5))
        time_input_frame = ttk.Frame(form_frame)
        time_input_frame.grid(row=2, column=1, columnspan=2, sticky="w", padx=5, pady=5)
        try:
            time_obj = datetime.strptime(self.reminder_to_edit.get("time", "12:00"), "%H:%M")
            h, m, ampm = time_obj.strftime("%I"), time_obj.strftime("%M"), time_obj.strftime("%p")
        except: h, m, ampm = datetime.now().strftime("%I"), datetime.now().strftime("%M"), datetime.now().strftime("%p")
        self.hour_spinbox = ttk.Spinbox(time_input_frame, from_=1, to=12, width=3, format="%02.0f", wrap=True)
        self.hour_spinbox.pack(side=tk.LEFT); self.hour_spinbox.set(h)
        ttk.Label(time_input_frame, text=":").pack(side=tk.LEFT, padx=2)
        self.minute_spinbox = ttk.Spinbox(time_input_frame, from_=0, to=59, width=3, format="%02.0f", wrap=True)
        self.minute_spinbox.pack(side=tk.LEFT); self.minute_spinbox.set(m)
        self.ampm_var = tk.StringVar(value=ampm)
        self.ampm_combobox = ttk.Combobox(time_input_frame, textvariable=self.ampm_var, values=["AM", "PM"], width=3, state="readonly")
        self.ampm_combobox.pack(side=tk.LEFT, padx=(5,0))
        self.save_button = ttk.Button(form_frame, text="Save Changes", command=self.save_updated_reminder) # Command updated
        self.save_button.grid(row=3, column=0, columnspan=3, pady=20, ipady=4)
        form_frame.columnconfigure(1, weight=1); self.title_entry.focus_set()

    # VVVV FULLY IMPLEMENTED SAVE LOGIC VVVV
    def save_updated_reminder(self):
        original_id = self.reminder_to_edit.get('id')
        new_title = self.title_entry.get().strip()
        new_selected_date_str = self.cal.get_date()
        new_hour_12_str = self.hour_spinbox.get().strip()
        new_minute_str = self.minute_spinbox.get().strip()
        new_ampm_val = self.ampm_var.get()

        if not new_title:
            messagebox.showerror("Input Error", "Title cannot be empty.", parent=self.edit_window)
            return
        
        # Validate time components (similar to AddReminderWindow)
        if not new_hour_12_str.isdigit() or not new_minute_str.isdigit():
            messagebox.showerror("Input Error", "Hour and Minute must be numeric digits.", parent=self.edit_window)
            return
        try:
            new_hour_12_int = int(new_hour_12_str)
            new_minute_int = int(new_minute_str)
        except ValueError: # Should be caught by isdigit, but for safety
            messagebox.showerror("Input Error", "Hour and Minute must be valid numbers.", parent=self.edit_window)
            return
        if not (1 <= new_hour_12_int <= 12):
            messagebox.showerror("Input Error", "Hour must be between 1 and 12.", parent=self.edit_window)
            self.hour_spinbox.focus_set(); return
        if not (0 <= new_minute_int <= 59):
            messagebox.showerror("Input Error", "Minute must be between 0 and 59.", parent=self.edit_window)
            self.minute_spinbox.focus_set(); return

        # Convert new time to 24-hour format for saving
        try:
            new_time_12h_input_str = f"{new_hour_12_int:02}:{new_minute_int:02} {new_ampm_val}"
            new_time_obj_24h = datetime.strptime(new_time_12h_input_str, "%I:%M %p")
            new_time_str_24h_to_save = new_time_obj_24h.strftime("%H:%M")
        except ValueError:
            messagebox.showerror("Input Error", f"Invalid time format: {new_time_12h_input_str}", parent=self.edit_window)
            return

        all_reminders = load_reminders()
        found_and_updated = False
        for reminder in all_reminders:
            if reminder.get("id") == original_id:
                # Check if date or time has changed to reset notification flag
                if (reminder.get("date") != new_selected_date_str or
                    reminder.get("time") != new_time_str_24h_to_save):
                    reminder["notified_individually"] = False
                
                reminder["title"] = new_title
                reminder["date"] = new_selected_date_str
                reminder["time"] = new_time_str_24h_to_save
                found_and_updated = True
                break
        
        if found_and_updated:
            save_reminders(all_reminders)
            messagebox.showinfo("Success", "Reminder updated successfully!", parent=self.parent) # Parent is main window
            self.main_app.populate_reminders_list()
            self.edit_window.destroy()
        else:
            # This should ideally not happen if the selection logic is correct
            messagebox.showerror("Error", "Could not find the original reminder to update. It may have been deleted.", parent=self.edit_window)


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
        print("Starting tray icon thread...")
        tray_icon_object.run() # This blocks until tray_icon_object.stop() is called
        print("Tray icon thread finished.")
    except FileNotFoundError:
        print(f"Error: Tray icon image '{LOGO_FILE}' not found. Tray icon disabled.")
    except Exception as e:
        print(f"Error setting up system tray: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Single instance check should be selective if startup_check is meant to be quick
    # For now, if any argument is passed (like startup_check or start_minimized), skip lock
    is_utility_run = len(sys.argv) > 1 
    if not is_utility_run:
        check_single_instance() # Only check for full normal launch

    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'startup_check':
            print("Running startup_check...")
            temp_startup_root = tk.Tk()
            temp_startup_root.withdraw()
            today_str = date.today().strftime("%Y-%m-%d")
            app_config = load_app_config()
            last_check_date = app_config.get("last_startup_check_date")
            if last_check_date != today_str:
                print(f"Performing daily reminder summary for {today_str}.")
                todays_reminders_list = get_all_todays_reminders() # Uses the simple "actual today" version
                display_reminders_popup(todays_reminders_list, f"Reminders for Today ({today_str})", temp_startup_root)
                app_config["last_startup_check_date"] = today_str
                save_app_config(app_config)
                print("Startup check complete.")
            else:
                print(f"Daily summary already shown for {today_str}.")
            temp_startup_root.destroy()
            sys.exit(0)

        # --- Full Application Mode ---
        SHOULD_START_HIDDEN = False
        if len(sys.argv) > 1 and sys.argv[1] == 'start_minimized':
            SHOULD_START_HIDDEN = True
            print(f"{APP_NAME} starting minimized to tray.")
        else:
            print(f"{APP_NAME} starting in full mode.")

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True); scheduler_thread.start()
        
        main_window_root = tk.Tk()
        tk_root_window = main_window_root
        
        # Crucial: main_gui_visible needs to be set BEFORE ReminderApp is initialized
        # if ReminderApp.__init__ depends on it (e.g., for showing its own startup popup)
        main_gui_visible = not SHOULD_START_HIDDEN 
        
        app = ReminderApp(main_window_root)
        
        if SHOULD_START_HIDDEN:
            main_window_root.withdraw()
            # main_gui_visible is already False

        # Start tray icon in a thread (must be after tk.Tk() is called for main app)
        tray_thread = threading.Thread(target=setup_system_tray, daemon=True)
        tray_thread.start()
        
        print("Main GUI and Threads initialized. Entering Tkinter mainloop.")
        main_window_root.mainloop()

    except SystemExit: # Allow sys.exit() to pass through for startup_check and lock fail
        pass
    except Exception as e:
        print(f"An unhandled error occurred: {e}")
        messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}\nThe application might need to close.")
    finally:
        print("Application is exiting. Cleaning up...")
        if not is_utility_run: # Only cleanup lock if it was a full app run
            cleanup_lock_file()
        
        if 'scheduler_thread' in locals() and scheduler_thread.is_alive() and not scheduler_stop_event.is_set():
            scheduler_stop_event.set()
            scheduler_thread.join(timeout=2)
        
        # Tray icon stopping is handled by quit_application_action or program termination for daemon thread
        print(f"{APP_NAME} finished.")