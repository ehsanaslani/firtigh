import os
import sys
import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import time

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import memory module
import memory

# Helper function to run async tests
def run_async(coroutine):
    """Helper to run async functions in tests."""
    # Create a new event loop for each test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

# Create a temporary directory for test data
@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data files."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Set memory's DATA_DIR to our temp directory
    original_data_dir = memory.DATA_DIR
    memory.DATA_DIR = temp_dir
    memory.MEMORY_FILE = os.path.join(temp_dir, "group_memory.json")
    memory.USER_PROFILES_FILE = os.path.join(temp_dir, "user_profiles.json")
    
    # Yield the temp directory
    yield temp_dir
    
    # Clean up and restore original data directory
    shutil.rmtree(temp_dir)
    memory.DATA_DIR = original_data_dir
    memory.MEMORY_FILE = os.path.join(original_data_dir, "group_memory.json")
    memory.USER_PROFILES_FILE = os.path.join(original_data_dir, "user_profiles.json")

def test_initialize_memory(temp_data_dir):
    """Test the initialize_memory function."""
    # Call the function
    memory.initialize_memory()
    
    # Check that the files were created
    assert os.path.exists(memory.MEMORY_FILE)
    assert os.path.exists(memory.USER_PROFILES_FILE)
    
    # Check that the files have the correct structure
    with open(memory.MEMORY_FILE, "r", encoding="utf-8") as f:
        memory_data = json.load(f)
        assert "groups" in memory_data
        assert isinstance(memory_data["groups"], dict)
    
    with open(memory.USER_PROFILES_FILE, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
        assert "users" in profile_data
        assert isinstance(profile_data["users"], dict)

@patch('openai.ChatCompletion.create')
def test_analyze_message_for_memory(mock_create, temp_data_dir):
    """Test the analyze_message_for_memory function."""
    # Set up mock response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "topics": ["tech", "AI"],
        "sentiment": "positive",
        "key_points": ["AI is improving", "Memory is useful"],
        "user_traits": ["tech-savvy", "curious"],
        "is_memorable": True
    })
    mock_create.return_value = mock_response
    
    # Test message data
    message_data = {
        "message_id": 123,
        "text": "I think AI memory systems are getting really good these days."
    }
    
    # Call the function
    result = run_async(memory.analyze_message_for_memory(message_data))
    
    # Check the result
    assert "topics" in result
    assert "sentiment" in result
    assert "key_points" in result
    assert "user_traits" in result
    assert "is_memorable" in result
    assert result["message_id"] == 123
    assert "message_text" in result
    assert "timestamp" in result

@patch('memory.analyze_message_for_memory')
def test_process_message_for_memory(mock_analyze, temp_data_dir):
    """Test the process_message_for_memory function."""
    # Set up mock response
    mock_analyze.return_value = {
        "topics": ["tech", "AI"],
        "sentiment": "positive",
        "key_points": ["AI is improving", "Memory is useful"],
        "user_traits": ["tech-savvy", "curious"],
        "is_memorable": True,
        "timestamp": time.time(),
        "message_id": 123,
        "message_text": "Test message"
    }
    
    # Initialize memory
    memory.initialize_memory()
    
    # Test message data
    message_data = {
        "chat_id": 123456,
        "sender_id": 789012,
        "sender_name": "test_user",
        "message_id": 123,
        "text": "Test message"
    }
    
    # Call the function
    run_async(memory.process_message_for_memory(message_data))
    
    # Verify that the analyze function was called
    mock_analyze.assert_called_once()

def test_update_and_get_group_memory(temp_data_dir):
    """Test the update_group_memory and get_group_memory functions."""
    # Initialize memory
    memory.initialize_memory()
    
    # Test memory item
    memory_item = {
        "topics": ["test"],
        "sentiment": "neutral",
        "key_points": ["This is a test"],
        "user_traits": ["tester"],
        "is_memorable": True,
        "timestamp": time.time(),
        "message_id": 123,
        "message_text": "Test message"
    }
    
    # Call update_group_memory
    run_async(memory.update_group_memory(123456, memory_item))
    
    # Get the memory and verify
    memories = memory.get_group_memory(123456)
    assert len(memories) == 1
    assert memories[0]["topics"] == ["test"]
    assert memories[0]["message_id"] == 123

def test_update_and_get_user_profile(temp_data_dir):
    """Test the update_user_profile and get_user_profile functions."""
    # Initialize memory
    memory.initialize_memory()
    
    # Call update_user_profile
    run_async(memory.update_user_profile(
        user_id=789012,
        username="test_user",
        traits=["friendly", "helpful"],
        topics=["tech", "AI"],
        sentiment="positive"
    ))
    
    # Get the profile and verify
    profile = memory.get_user_profile(789012)
    assert profile["username"] == "test_user"
    assert "friendly" in profile["traits"]
    assert "tech" in profile["topics_of_interest"]
    assert profile["sentiment_counts"]["positive"] == 1

def test_format_memory_for_context(temp_data_dir):
    """Test the format_memory_for_context function."""
    # Test memory items
    memory_items = [
        {
            "topics": ["tech"],
            "key_points": ["AI memory is useful"],
            "timestamp": time.time(),
            "message_id": 123
        },
        {
            "topics": ["weather"],
            "key_points": ["It's sunny today"],
            "timestamp": time.time() - 86400,  # 1 day ago
            "message_id": 124
        }
    ]
    
    # Format and verify
    formatted = memory.format_memory_for_context(memory_items)
    assert "اطلاعات پیشین در مورد این گروه" in formatted
    assert "AI memory is useful" in formatted
    assert "It's sunny today" in formatted

def test_format_user_profile_for_context(temp_data_dir):
    """Test the format_user_profile_for_context function."""
    # Test user profile
    profile = {
        "username": "test_user",
        "traits": {"friendly": 3, "helpful": 2},
        "topics_of_interest": {"tech": 5, "AI": 3},
        "sentiment_counts": {"positive": 7, "negative": 1, "neutral": 2}
    }
    
    # Format and verify
    formatted = memory.format_user_profile_for_context(profile)
    assert "اطلاعات کاربر test_user" in formatted
    assert "ویژگی‌ها: friendly، helpful" in formatted
    assert "علایق: tech، AI" in formatted
    assert "لحن معمول: مثبت" in formatted 