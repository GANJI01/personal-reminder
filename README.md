# Personal Reminder Application

A desktop application for managing personal reminders with a system tray interface and automatic notifications.

## Features

- Create, edit, and delete reminders
- Automatic notifications for due reminders
- System tray integration for background operation
- Automatic cleanup of past reminders
- Beautiful and intuitive user interface
- Support for AM/PM time format
- Calendar-based date selection
- Startup reminder summary
- Persistent storage of reminders

## Requirements

- Python 3.x
- Required Python packages:
  - tkinter
  - tkcalendar
  - PIL (Pillow)
  - schedule
  - pystray

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

### Main Features

- **Add Reminder**: Click the "Add" button to create a new reminder
- **Edit Reminder**: Select a reminder and click "Update" to modify it
- **Delete Reminder**: Select a reminder and click "Delete" to remove it
- **System Tray**: The application minimizes to system tray when closed
- **Automatic Cleanup**: Past reminders are automatically deleted at midnight

### System Tray Options

- Show App
- Add Reminder
- Quit

## Development

The application is built using:
- Tkinter for the GUI
- Schedule for task scheduling
- Pystray for system tray integration
- JSON for data storage

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Acknowledgments

- Thanks to all contributors who have helped improve this application
- Special thanks to the Python community for the amazing libraries 