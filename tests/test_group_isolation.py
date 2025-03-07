import os
import sys
import json
import tempfile
import shutil
import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import modules
import memory
import database

class TestGroupIsolation(unittest.TestCase):
    """Test that history and memory are isolated between different groups."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for test data
        self.temp_memory_dir = tempfile.mkdtemp()
        self.temp_db_dir = tempfile.mkdtemp()
        
        # Store original paths
        self.original_memory_dir = memory.DATA_DIR
        self.original_memory_file = memory.MEMORY_FILE
        self.original_user_profiles_file = memory.USER_PROFILES_FILE
        
        self.original_db_dir = database.DATA_DIR
        self.original_messages_file = database.MESSAGES_FILE
        
        # Set up test paths
        memory.DATA_DIR = self.temp_memory_dir
        memory.MEMORY_FILE = os.path.join(self.temp_memory_dir, "group_memory.json")
        memory.USER_PROFILES_FILE = os.path.join(self.temp_memory_dir, "user_profiles.json")
        
        database.DATA_DIR = self.temp_db_dir
        database.MESSAGES_FILE = os.path.join(self.temp_db_dir, "message_history.json")
        
        # Initialize the memory and database
        memory.initialize_memory()
        database.initialize_database()
        
        # Current timestamp for tests
        self.current_timestamp = time.time()
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original paths
        memory.DATA_DIR = self.original_memory_dir
        memory.MEMORY_FILE = self.original_memory_file
        memory.USER_PROFILES_FILE = self.original_user_profiles_file
        
        database.DATA_DIR = self.original_db_dir
        database.MESSAGES_FILE = self.original_messages_file
        
        # Clean up temporary directories
        shutil.rmtree(self.temp_memory_dir)
        shutil.rmtree(self.temp_db_dir)
    
    def run_async(self, coro):
        """Helper to run async functions in tests."""
        # Create a new event loop for each test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    @patch('memory.analyze_message_for_memory')
    def test_memory_isolation_between_groups(self, mock_analyze):
        """Test that memory items are isolated between different groups."""
        # Set up mock response for message analysis
        mock_analyze.side_effect = lambda msg: {
            "topics": ["topic1", "topic2"],
            "sentiment": "positive",
            "key_points": ["key point 1", "key point 2"],
            "user_traits": ["trait1", "trait2"],
            "is_memorable": True,
            "timestamp": self.current_timestamp,
            "message_id": msg.get("message_id", 0),
            "message_text": msg.get("text", "")
        }
        
        # Create test message data for two different groups
        group1_message = {
            "chat_id": 111,
            "sender_id": 999,
            "sender_name": "User Group 1",
            "message_id": 1,
            "text": "This is a message in Group 1"
        }
        
        group2_message = {
            "chat_id": 222,
            "sender_id": 999,  # Same user, different group
            "sender_name": "User Group 2",
            "message_id": 2,
            "text": "This is a message in Group 2"
        }
        
        # Process messages for both groups
        self.run_async(memory.process_message_for_memory(group1_message))
        self.run_async(memory.process_message_for_memory(group2_message))
        
        # Get memory for group 1
        group1_memory = memory.get_group_memory(111)
        
        # Get memory for group 2
        group2_memory = memory.get_group_memory(222)
        
        # Verify that the memories are different
        self.assertEqual(len(group1_memory), 1, "Group 1 should have exactly one memory item")
        self.assertEqual(len(group2_memory), 1, "Group 2 should have exactly one memory item")
        
        # Check content to ensure it's the right message
        self.assertEqual(group1_memory[0]["message_id"], 1, "Group 1 memory should contain message 1")
        self.assertEqual(group2_memory[0]["message_id"], 2, "Group 2 memory should contain message 2")
        
        # Verify that group 1 memory doesn't contain group 2's message text
        self.assertNotIn("Group 2", group1_memory[0]["message_text"])
        
        # Verify that group 2 memory doesn't contain group 1's message text
        self.assertNotIn("Group 1", group2_memory[0]["message_text"])
        
        # Check the actual memory file to ensure groups are stored separately
        with open(memory.MEMORY_FILE, "r", encoding="utf-8") as f:
            memory_data = json.load(f)
        
        self.assertIn("111", memory_data["groups"])
        self.assertIn("222", memory_data["groups"])
        self.assertEqual(len(memory_data["groups"]["111"]), 1)
        self.assertEqual(len(memory_data["groups"]["222"]), 1)
    
    def test_database_isolation_between_groups(self):
        """Test that message history is isolated between different groups."""
        # Create test message data for two different groups
        group1_message = {
            "message_id": 1,
            "chat_id": 111,
            "sender_id": 999,
            "sender_name": "User Group 1",
            "text": "This is a message in Group 1",
            "date": self.current_timestamp,  # Use current timestamp
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        group2_message = {
            "message_id": 2,
            "chat_id": 222,
            "sender_id": 999,  # Same user, different group
            "sender_name": "User Group 2",
            "text": "This is a message in Group 2",
            "date": self.current_timestamp,  # Use current timestamp
            "has_photo": False,
            "has_animation": False,
            "has_sticker": False,
            "has_document": False
        }
        
        # Save messages for both groups
        database.save_message(group1_message)
        database.save_message(group2_message)
        
        # Get messages for group 1
        group1_messages = database.get_messages(days=1, chat_id=111)
        
        # Get messages for group 2
        group2_messages = database.get_messages(days=1, chat_id=222)
        
        # Verify that the messages are correctly filtered by chat_id
        self.assertEqual(len(group1_messages), 1, "Group 1 should have exactly one message")
        self.assertEqual(len(group2_messages), 1, "Group 2 should have exactly one message")
        
        # Check content to ensure it's the right message
        self.assertEqual(group1_messages[0]["message_id"], 1, "Group 1 should contain message 1")
        self.assertEqual(group2_messages[0]["message_id"], 2, "Group 2 should contain message 2")
        
        # Verify that group 1 doesn't contain group 2's message text
        self.assertNotIn("Group 2", group1_messages[0]["text"])
        
        # Verify that group 2 doesn't contain group 1's message text
        self.assertNotIn("Group 1", group2_messages[0]["text"])
        
        # Check formatted history
        group1_formatted = database.get_formatted_message_history(days=1, chat_id=111)
        group2_formatted = database.get_formatted_message_history(days=1, chat_id=222)
        
        # Verify the formatted history contains the correct messages
        self.assertIn("Group 1", group1_formatted)
        self.assertNotIn("Group 2", group1_formatted)
        self.assertIn("Group 2", group2_formatted)
        self.assertNotIn("Group 1", group2_formatted)
    
    @patch('memory.analyze_message_for_memory')
    def test_combined_isolation(self, mock_analyze):
        """Test complete isolation with a more complex scenario."""
        # Set up mock response for message analysis
        mock_analyze.side_effect = lambda msg: {
            "topics": ["topic1", "topic2"],
            "sentiment": "positive",
            "key_points": ["key point 1", "key point 2"],
            "user_traits": ["trait1", "trait2"],
            "is_memorable": True,
            "timestamp": self.current_timestamp,
            "message_id": msg.get("message_id", 0),
            "message_text": msg.get("text", "")
        }
        
        # Create multiple messages for three different groups
        groups = {
            111: ["Message 1 in Group A", "Message 2 in Group A", "Message 3 in Group A"],
            222: ["Message 1 in Group B", "Message 2 in Group B"],
            333: ["Message 1 in Group C"]
        }
        
        message_id = 1
        for chat_id, messages in groups.items():
            for text in messages:
                # Create message data
                msg_data = {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "sender_id": 999,
                    "sender_name": f"User in Group {chat_id}",
                    "text": text,
                    "date": self.current_timestamp,  # Use current timestamp
                    "has_photo": False,
                    "has_animation": False,
                    "has_sticker": False,
                    "has_document": False
                }
                
                # Save to database
                database.save_message(msg_data)
                
                # Process for memory
                self.run_async(memory.process_message_for_memory(msg_data))
                
                message_id += 1
        
        # Check database isolation
        for chat_id, messages in groups.items():
            db_messages = database.get_messages(days=1, chat_id=chat_id)
            self.assertEqual(len(db_messages), len(messages), 
                            f"Group {chat_id} should have {len(messages)} messages")
            
            # Check that messages from other groups are not included
            for msg in db_messages:
                for other_chat_id, other_messages in groups.items():
                    if other_chat_id != chat_id:
                        for other_text in other_messages:
                            self.assertNotIn(other_text, msg["text"], 
                                            f"Message from group {other_chat_id} found in group {chat_id}")
        
        # Check memory isolation
        for chat_id, messages in groups.items():
            group_memory = memory.get_group_memory(chat_id)
            self.assertEqual(len(group_memory), len(messages), 
                            f"Group {chat_id} should have {len(messages)} memory items")
            
            # Check that memory items from other groups are not included
            for mem in group_memory:
                for other_chat_id, other_messages in groups.items():
                    if other_chat_id != chat_id:
                        for other_text in other_messages:
                            self.assertNotIn(other_text, mem["message_text"], 
                                            f"Memory from group {other_chat_id} found in group {chat_id}")
        
        # Verify memory formatted for context
        for chat_id in groups.keys():
            group_memory = memory.get_group_memory(chat_id)
            formatted = memory.format_memory_for_context(group_memory)
            
            # The formatted memory contains key points, not original text
            self.assertIn("key point 1", formatted, f"Formatted memory for group {chat_id} missing key points")
            self.assertIn("key point 2", formatted, f"Formatted memory for group {chat_id} missing key points")
            
            # Count occurrences of key points - should match the number of messages
            point_occurrences = formatted.count("key point 1")
            self.assertEqual(point_occurrences, len(groups[chat_id]), 
                            f"Group {chat_id} should have {len(groups[chat_id])} key point entries")

if __name__ == "__main__":
    unittest.main() 