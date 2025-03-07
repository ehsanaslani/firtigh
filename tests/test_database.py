import os
import json
import unittest
import tempfile
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database

class TestDatabase(unittest.TestCase):
    """Test cases for the database module."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = database.DATA_DIR
        self.original_messages_file = database.MESSAGES_FILE
        
        # Patch the data directory and file paths
        database.DATA_DIR = self.temp_dir.name
        database.MESSAGES_FILE = os.path.join(self.temp_dir.name, "message_history.json")
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original paths
        database.DATA_DIR = self.original_data_dir
        database.MESSAGES_FILE = self.original_messages_file
        
        # Clean up temporary directory
        self.temp_dir.cleanup()
    
    def test_initialize_database(self):
        """Test database initialization."""
        database.initialize_database()
        
        # Check if the file was created
        self.assertTrue(os.path.exists(database.MESSAGES_FILE))
        
        # Check the structure of the created file
        with open(database.MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertIn("messages", data)
        self.assertEqual(data["messages"], [])
    
    def test_save_message(self):
        """Test saving a message to the database."""
        # Initialize database
        database.initialize_database()
        
        # Create a test message
        test_message = {
            "message_id": 123,
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "Test User",
            "text": "Hello, world!",
            "date": 1234567890,
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Save the message
        result = database.save_message(test_message)
        
        # Check the result
        self.assertTrue(result)
        
        # Check that the message was saved
        with open(database.MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["message_id"], 123)
        self.assertEqual(data["messages"][0]["text"], "Hello, world!")
    
    def test_message_limit(self):
        """Test that the message history is limited to 1000 messages."""
        # Initialize database
        database.initialize_database()
        
        # Create base message template
        base_message = {
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "Test User",
            "text": "Test message",
            "date": 1234567890,
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Add 1200 messages (exceeding the 1000 limit)
        for i in range(1200):
            message = base_message.copy()
            message["message_id"] = i
            message["text"] = f"Test message {i}"
            database.save_message(message)
        
        # Check that only the last 1000 messages are kept
        with open(database.MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertEqual(len(data["messages"]), 1000)
        
        # Verify that the messages are the last 1000 (IDs 200-1199)
        message_ids = [msg["message_id"] for msg in data["messages"]]
        self.assertEqual(min(message_ids), 200)
        self.assertEqual(max(message_ids), 1199)
    
    def test_get_messages(self):
        """Test retrieving messages from the database."""
        # Initialize database
        database.initialize_database()
        
        # Create test messages with different dates
        import time
        current_time = time.time()
        
        # Message from 5 days ago
        old_message = {
            "message_id": 1,
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "Test User",
            "text": "Old message",
            "date": current_time - (5 * 24 * 60 * 60),
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Message from 2 days ago
        recent_message = {
            "message_id": 2,
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "Test User",
            "text": "Recent message",
            "date": current_time - (2 * 24 * 60 * 60),
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Message from today
        current_message = {
            "message_id": 3,
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "Test User",
            "text": "Current message",
            "date": current_time,
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Save the messages
        database.save_message(old_message)
        database.save_message(recent_message)
        database.save_message(current_message)
        
        # Test retrieving messages from the last 3 days
        messages = database.get_messages(days=3)
        
        # Should include recent and current messages, but not old message
        self.assertEqual(len(messages), 2)
        message_texts = [msg["text"] for msg in messages]
        self.assertIn("Recent message", message_texts)
        self.assertIn("Current message", message_texts)
        self.assertNotIn("Old message", message_texts)
        
        # Test retrieving messages from a specific chat
        messages = database.get_messages(days=7, chat_id=456)
        self.assertEqual(len(messages), 3)  # All messages have chat_id 456
        
        # Test retrieving messages from a non-existent chat
        messages = database.get_messages(days=7, chat_id=999)
        self.assertEqual(len(messages), 0)  # No messages with chat_id 999
    
    def test_format_message_for_summary(self):
        """Test formatting a message for summarization."""
        # Create a test message
        test_message = {
            "message_id": 123,
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "Test User",
            "text": "Hello, world!",
            "date": 1234567890,
            "has_photo": True,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Format the message
        formatted = database.format_message_for_summary(test_message)
        
        # Check the formatted string
        self.assertIn("Test User", formatted)
        self.assertIn("Hello, world!", formatted)
        self.assertIn("[IMAGE]", formatted)  # Should include image indicator
    
    def test_get_formatted_message_history(self):
        """Test getting formatted message history."""
        # Initialize database
        database.initialize_database()
        
        # Create test messages
        message1 = {
            "message_id": 1,
            "chat_id": 456,
            "sender_id": 789,
            "sender_name": "User1",
            "text": "First message",
            "date": 1234567890,
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        message2 = {
            "message_id": 2,
            "chat_id": 456,
            "sender_id": 790,
            "sender_name": "User2",
            "text": "Second message",
            "date": 1234567891,
            "has_photo": True,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Save the messages
        database.save_message(message1)
        database.save_message(message2)
        
        # Set messages to appear as if they're from today to pass the date filter
        import time
        current_time = time.time()
        with open(database.MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for msg in data["messages"]:
            msg["date"] = current_time
        with open(database.MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        # Get formatted history
        history = database.get_formatted_message_history()
        
        # Check the history
        self.assertIn("User1", history)
        self.assertIn("First message", history)
        self.assertIn("User2", history)
        self.assertIn("Second message", history)
        self.assertIn("[IMAGE]", history)
        
        # Test with no messages
        with patch("database.get_messages", return_value=[]):
            history = database.get_formatted_message_history()
            self.assertIn("No messages found", history)

if __name__ == "__main__":
    unittest.main() 