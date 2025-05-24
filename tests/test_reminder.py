import unittest
from datetime import date, datetime, time
import json
import os
import sys
import tempfile

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from remainder import (
    load_reminders,
    save_reminders,
    format_time_to_ampm,
    delete_past_reminders
)

class TestReminderFunctions(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.TemporaryDirectory()
        self.original_data_file = os.environ.get('DATA_FILE')
        os.environ['DATA_FILE'] = os.path.join(self.test_dir.name, 'test_reminders.json')

    def tearDown(self):
        # Clean up the temporary directory
        self.test_dir.cleanup()
        if self.original_data_file:
            os.environ['DATA_FILE'] = self.original_data_file

    def test_load_save_reminders(self):
        # Test data
        test_reminders = [
            {
                "id": "1",
                "title": "Test Reminder 1",
                "date": "2024-03-20",
                "time": "10:00",
                "notified_individually": False
            },
            {
                "id": "2",
                "title": "Test Reminder 2",
                "date": "2024-03-21",
                "time": "15:30",
                "notified_individually": True
            }
        ]

        # Test saving reminders
        save_reminders(test_reminders)
        
        # Test loading reminders
        loaded_reminders = load_reminders()
        
        # Verify the loaded data matches the saved data
        self.assertEqual(len(loaded_reminders), len(test_reminders))
        for saved, loaded in zip(test_reminders, loaded_reminders):
            self.assertEqual(saved["id"], loaded["id"])
            self.assertEqual(saved["title"], loaded["title"])
            self.assertEqual(saved["date"], loaded["date"])
            self.assertEqual(saved["time"], loaded["time"])
            self.assertEqual(saved["notified_individually"], loaded["notified_individually"])

    def test_format_time_to_ampm(self):
        # Test cases
        test_cases = [
            ("10:00", "10:00 AM"),
            ("15:30", "03:30 PM"),
            ("00:00", "12:00 AM"),
            ("12:00", "12:00 PM"),
            ("", "N/A"),
            ("invalid", "invalid")
        ]

        for input_time, expected_output in test_cases:
            with self.subTest(input_time=input_time):
                result = format_time_to_ampm(input_time)
                self.assertEqual(result, expected_output)

    def test_delete_past_reminders(self):
        # Create test data with past and future reminders
        today = date.today()
        yesterday = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - 
                    datetime.timedelta(days=1)).date()
        tomorrow = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + 
                   datetime.timedelta(days=1)).date()

        test_reminders = [
            {
                "id": "1",
                "title": "Past Reminder",
                "date": yesterday.strftime("%Y-%m-%d"),
                "time": "10:00",
                "notified_individually": False
            },
            {
                "id": "2",
                "title": "Today's Reminder",
                "date": today.strftime("%Y-%m-%d"),
                "time": "15:30",
                "notified_individually": False
            },
            {
                "id": "3",
                "title": "Future Reminder",
                "date": tomorrow.strftime("%Y-%m-%d"),
                "time": "20:00",
                "notified_individually": False
            }
        ]

        # Save test data
        save_reminders(test_reminders)

        # Run the delete function
        delete_past_reminders()

        # Load and verify results
        remaining_reminders = load_reminders()
        
        # Should only have today's and future reminders
        self.assertEqual(len(remaining_reminders), 2)
        for reminder in remaining_reminders:
            self.assertGreaterEqual(
                datetime.strptime(reminder["date"], "%Y-%m-%d").date(),
                today
            )

if __name__ == '__main__':
    unittest.main() 