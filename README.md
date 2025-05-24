# Personal Reminder Application

A robust desktop reminder application built with Python and Tkinter, featuring a modern UI and comprehensive reminder management capabilities.

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