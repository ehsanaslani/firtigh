import os
import json
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import usage_limits

class TestUsageLimits(unittest.TestCase):
    """Test cases for the usage limits functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = usage_limits.DATA_DIR
        self.original_usage_file = usage_limits.USAGE_FILE
        
        # Patch the data directory and file paths
        usage_limits.DATA_DIR = self.temp_dir.name
        usage_limits.USAGE_FILE = os.path.join(self.temp_dir.name, "usage_limits.json")
    
    def tearDown(self):
        """Clean up after tests."""
        # Restore original paths
        usage_limits.DATA_DIR = self.original_data_dir
        usage_limits.USAGE_FILE = self.original_usage_file
        
        # Clean up temporary directory
        self.temp_dir.cleanup()
    
    def test_initialize_usage_file(self):
        """Test that the usage file is initialized correctly."""
        usage_limits._initialize_usage_file()
        
        # Check that the file exists
        self.assertTrue(os.path.exists(usage_limits.USAGE_FILE))
        
        # Check that the file contains valid JSON with the expected structure
        with open(usage_limits.USAGE_FILE, "r") as f:
            data = json.load(f)
        
        self.assertIn("date", data)
        self.assertIn("search_count", data)
        self.assertIn("media_count", data)
        
        # Check that the counters are initialized to 0
        self.assertEqual(data["search_count"], 0)
        self.assertEqual(data["media_count"], 0)
    
    def test_reset_usage_if_new_day(self):
        """Test that usage counters are reset on a new day."""
        # Set up a file with yesterday's date
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        with open(usage_limits.USAGE_FILE, "w") as f:
            json.dump({
                "date": yesterday,
                "search_count": 10,
                "media_count": 5
            }, f)
        
        # Call the reset function
        usage_limits._reset_usage_if_new_day()
        
        # Check that the file was updated with today's date and reset counters
        with open(usage_limits.USAGE_FILE, "r") as f:
            data = json.load(f)
        
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(data["date"], today)
        self.assertEqual(data["search_count"], 0)
        self.assertEqual(data["media_count"], 0)
    
    def test_update_usage_count(self):
        """Test updating usage counts."""
        # Initialize the file
        usage_limits._initialize_usage_file()
        
        # Update search count
        data = usage_limits._update_usage_count("search")
        self.assertEqual(data["search_count"], 1)
        
        # Update again
        data = usage_limits._update_usage_count("search")
        self.assertEqual(data["search_count"], 2)
        
        # Update media count
        data = usage_limits._update_usage_count("media")
        self.assertEqual(data["media_count"], 1)
    
    def test_can_use_search(self):
        """Test the search limit checking."""
        # Initialize the file
        usage_limits._initialize_usage_file()
        
        # Should be able to search initially
        self.assertTrue(usage_limits.can_use_search())
        
        # Set search count to limit-1
        limit = usage_limits.get_daily_limits()["search"]
        with open(usage_limits.USAGE_FILE, "w") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "search_count": limit - 1,
                "media_count": 0
            }, f)
        
        # Should still be able to search
        self.assertTrue(usage_limits.can_use_search())
        
        # Set search count to limit
        with open(usage_limits.USAGE_FILE, "w") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "search_count": limit,
                "media_count": 0
            }, f)
        
        # Should not be able to search
        self.assertFalse(usage_limits.can_use_search())
    
    def test_can_process_media(self):
        """Test the media processing limit checking."""
        # Initialize the file
        usage_limits._initialize_usage_file()
        
        # Should be able to process media initially
        self.assertTrue(usage_limits.can_process_media())
        
        # Set media count to limit-1
        limit = usage_limits.get_daily_limits()["media"]
        with open(usage_limits.USAGE_FILE, "w") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "search_count": 0,
                "media_count": limit - 1
            }, f)
        
        # Should still be able to process media
        self.assertTrue(usage_limits.can_process_media())
        
        # Set media count to limit
        with open(usage_limits.USAGE_FILE, "w") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "search_count": 0,
                "media_count": limit
            }, f)
        
        # Should not be able to process media
        self.assertFalse(usage_limits.can_process_media())
    
    def test_get_remaining_limits(self):
        """Test getting remaining usage limits."""
        # Create a test usage file with some usage
        with open(usage_limits.USAGE_FILE, "w") as f:
            json.dump({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "search_count": 10,
                "media_count": 5
            }, f)
        
        # Set higher limits for testing
        with patch.dict('os.environ', {'DAILY_SEARCH_LIMIT': '50', 'DAILY_MEDIA_LIMIT': '20'}):
            # Get remaining limits
            limits = usage_limits.get_remaining_limits()
            
            # Check if the limits are as expected
            self.assertEqual(limits["search"], 40)  # 50 - 10
            self.assertEqual(limits["media"], 15)   # 20 - 5

if __name__ == "__main__":
    unittest.main() 