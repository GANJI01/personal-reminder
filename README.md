# Personal Reminder Application

This is a simple personal reminder application built with Python and Tkinter, designed to run in the background and notify you of upcoming reminders via a system tray icon.

## Setup Guide

To get the Personal Reminder application up and running on your laptop, follow these steps:

### Step 1: Install Python

This application requires Python to run.

*   Download the latest version of Python from the official website: [https://www.python.org/downloads/](https://www.python.org/downloads/)
*   **Important:** During the installation process, make sure to check the option that says "Add Python to PATH" (or a similar option). This is crucial for running Python commands from your terminal.

### Step 2: Get the Application Code

You need to get the application's source code from the GitHub repository.

*   **Option A (Using Git - Recommended):** If you have Git installed on your system, you can clone the repository using your terminal (Command Prompt or PowerShell):

    ```bash
    git clone <URL_of_your_GitHub_repo>
    ```

    Replace `<URL_of_your_GitHub_repo>` with the actual URL of this repository on GitHub. You can find the URL by clicking the "Code" button on the GitHub page.

*   **Option B (Downloading ZIP):** Go to the repository page on GitHub in your web browser. Click the green "Code" button and select "Download ZIP". Once the ZIP file is downloaded, extract its contents to a folder on your computer.

*   After obtaining the code, open your terminal and navigate to the application's root directory (the folder containing files like `remainder.py`, `install_autostart.py`, etc.) using the `cd` command. For example:

    ```bash
    cd /path/to/the/downloaded/folder
    ```

### Step 3: Install Application Dependencies

The application uses several external Python libraries. These are listed in the `requirements.txt` file.

*   With your terminal in the application's root directory, run the following command to install all the required libraries:

    ```bash
    pip install -r requirements.txt
    ```

### Step 4: Build the Executable (Recommended for Daily Use)

Building a standalone executable makes it easier to run the application and ensures it uses the correct icon.

*   Make sure you have PyInstaller installed (it's included in `requirements.txt`, so Step 3 should cover this).
*   In your terminal, from the application's root directory, run the PyInstaller command:

    ```bash
    pyinstaller PersonalReminder.spec
    ```

*   This will create a new folder named `dist` inside your application's root directory. Inside the `dist` folder, you will find the executable file: `PersonalReminder.exe`.

### Step 5: Set up Autostart (For Windows)

To have the application start automatically every time you log in to your Windows account, you need to run the installation script.

*   **Important:** This step requires administrator privileges to modify the Windows Registry.
*   Open your terminal (Command Prompt or PowerShell) **as administrator**. To do this, search for your terminal in the Start Menu, right-click on it, and select "Run as administrator". Confirm the User Account Control (UAC) prompt if it appears.
*   In the administrator terminal, navigate to the application's root directory using the `cd` command.
*   Run the autostart script:

    ```bash
    python install_autostart.py
    ```

*   You should see a message in the terminal confirming that "Personal Reminder will now start automatically with Windows."

### Step 6: Run the Application and Access via System Tray

*   After completing Step 5, the compiled application (`dist/PersonalReminder.exe`) is configured to start automatically the next time you log in.
*   You can also test it immediately by double-clicking `PersonalReminder.exe` inside the `dist` folder.
*   The application runs silently in the background and is accessible via its icon (an hourglass) in the **system tray** (the notification area near the clock on your taskbar).
*   Double-click or right-click the system tray icon to open the main application window, add new reminders, or close the application.

---

**Important Notes:**

*   **Data File:** Your reminder data is stored in a file named `reminders.json` located in the application's root directory (the same folder as `remainder.py` and `PersonalReminder.spec`) when you use the compiled executable from the `dist` folder.
*   **Lock File:** The application uses an `app.lock` file to prevent multiple instances from running. If you ever get an error message about a lock file when manually trying to run the application, you can safely delete the `app.lock` file found in the same directory as the executable you are trying to run (usually `dist/app.lock`). The application is designed to handle this.
*   **Uninstall Autostart:** To remove the application from Windows autostart, you would need to manually delete the "PersonalReminder" entry from the `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run` registry key using the Registry Editor (`regedit`).

---

Feel free to add or modify reminders using the application interface.

## Features

### Core Functionality
- Create, edit, and delete reminders
- Set custom dates and times for reminders
- Enhanced time input with 12/24 hour format support
- Quick time presets (Now, Morning, Noon, Evening)
- System tray integration for background operation
- Startup check for daily reminders

### Recurring Reminders
- Multiple recurrence types:
  - Daily
  - Weekdays (Monday to Friday)
  - Weekly
  - Biweekly
  - Monthly
  - Yearly
- End conditions for recurring reminders:
  - Never (indefinite)
  - After X occurrences
  - On specific date

### User Interface
- Modern Tkinter-based GUI
- Sortable and filterable reminder list
- Multiple view options (All, Today, Upcoming, Past, Recurring)
- System tray icon with quick actions
- Notification popups for due reminders

### Additional Features
- Snooze functionality for reminders
- Automatic cleanup of past reminders
- Comprehensive logging system
- Single instance enforcement
- Configurable startup behavior

## Requirements

- Python 3.7 or higher
- Required packages (see requirements.txt):
  - tkinter
  - tkcalendar
  - Pillow
  - schedule
  - pystray
  - python-dateutil

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/personal-reminder.git
cd personal-reminder
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python remainder.py
```

## Usage

### Basic Operations
- **Add Reminder**: Click "Add" button or use system tray menu
- **Edit Reminder**: Select a reminder and click "Update"
- **Delete Reminder**: Select a reminder and click "Delete"
- **Refresh List**: Click "Refresh" to update the reminder list

### Recurring Reminders
1. Click "Add" to create a new reminder
2. Set the date and time
3. Select a recurrence type from the "Repeat" dropdown
4. Choose an end condition if needed
5. Click "Save Reminder"

### System Tray
- Right-click the system tray icon for quick actions
- Choose "Show App" to open the main window
- Select "Add Reminder" for quick reminder creation
- Use "Quit" to exit the application

## Configuration

The application stores its configuration in `app_config.json` and reminders in `reminders.json`. These files are automatically created in the application directory.

## Logging

Logs are stored in `app.log` with rotation enabled (1MB per file, 5 backups). The log includes:
- Application startup/shutdown
- Reminder operations
- Error conditions
- System tray operations
- File operations
- Configuration changes

## Development

### Project Structure
- `remainder.py`: Main application file
- `requirements.txt`: Python package dependencies
- `README.md`: This documentation file
- `logo.png`: Application icon

### Building
To create a standalone executable:
```bash
pyinstaller --onefile --windowed --icon=logo.png remainder.py
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Tkinter for the GUI framework
- All the open-source libraries used in this project
- Contributors and users of the application 