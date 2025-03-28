import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Path to store usage data
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
USAGE_FILE = os.path.join(DATA_DIR, "usage_limits.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Default daily limits (can be overridden by environment variables)
DEFAULT_SEARCH_LIMIT = 50
DEFAULT_MEDIA_LIMIT = 10

def get_daily_limits() -> Dict[str, int]:
    """Get the daily usage limits from environment variables or defaults."""
    return {
        "search": int(os.getenv("DAILY_SEARCH_LIMIT", DEFAULT_SEARCH_LIMIT)),
        "media": int(os.getenv("DAILY_MEDIA_LIMIT", DEFAULT_MEDIA_LIMIT))
    }

def _initialize_usage_file():
    """Initialize the usage file if it doesn't exist."""
    if not os.path.exists(USAGE_FILE):
        today = datetime.now().strftime("%Y-%m-%d")
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "date": today,
                "search_count": 0,
                "media_count": 0
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"Created new usage limits file at {USAGE_FILE}")

def _reset_usage_if_new_day():
    """Reset usage counters if it's a new day."""
    try:
        # Ensure the file exists
        _initialize_usage_file()
        
        # Check if we need to reset for a new day
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        today = datetime.now().strftime("%Y-%m-%d")
        if data["date"] != today:
            # It's a new day, reset the counters
            data["date"] = today
            data["search_count"] = 0
            data["media_count"] = 0
            
            with open(USAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Reset usage limits for new day: {today}")
            
    except Exception as e:
        logger.error(f"Error resetting usage limits: {e}")

def _update_usage_count(usage_type: str, increment: int = 1) -> Dict[str, Any]:
    """
    Update the usage count for a specific type.
    
    Args:
        usage_type: Type of usage ('search' or 'media')
        increment: Amount to increment (default: 1)
        
    Returns:
        Updated usage data
    """
    try:
        # Ensure the file exists and reset if it's a new day
        _reset_usage_if_new_day()
        
        # Read current data
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Update count
        count_key = f"{usage_type}_count"
        if count_key in data:
            data[count_key] += increment
        else:
            data[count_key] = increment
        
        # Write updated data
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return data
    except Exception as e:
        logger.error(f"Error updating {usage_type} usage count: {e}")
        # Return a default value to avoid breaking the application
        return {"date": datetime.now().strftime("%Y-%m-%d"), f"{usage_type}_count": 0}

def can_use_search() -> bool:
    """Check if the search limit has not been reached for today."""
    try:
        # Ensure the file exists and reset if it's a new day
        _reset_usage_if_new_day()
        
        # Read current data
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Get limit from environment or default
        limit = get_daily_limits()["search"]
        
        # Check if we're under the limit
        return data.get("search_count", 0) < limit
    except Exception as e:
        logger.error(f"Error checking search usage limit: {e}")
        # Default to allowing search if there's an error
        return True

def can_perform_search() -> bool:
    """Alias for can_use_search() to maintain backward compatibility."""
    return can_use_search()

def can_process_media() -> bool:
    """Check if the media processing limit has not been reached for today."""
    try:
        # Ensure the file exists and reset if it's a new day
        _reset_usage_if_new_day()
        
        # Read current data
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Get limit from environment or default
        limit = get_daily_limits()["media"]
        
        # Check if we're under the limit
        return data.get("media_count", 0) < limit
    except Exception as e:
        logger.error(f"Error checking media usage limit: {e}")
        # Default to allowing media processing if there's an error
        return True

def increment_search_usage() -> int:
    """
    Increment the search usage count and return the new count.
    
    Returns:
        Current search count after incrementing
    """
    data = _update_usage_count("search")
    return data.get("search_count", 0)

def increment_media_usage() -> int:
    """
    Increment the media processing usage count and return the new count.
    
    Returns:
        Current media count after incrementing
    """
    data = _update_usage_count("media")
    return data.get("media_count", 0)

def get_remaining_limits() -> Dict[str, int]:
    """
    Get the remaining usage limits for all features.
    
    Returns:
        Dictionary with remaining limits for each feature
    """
    try:
        # Ensure the file exists and reset if it's a new day
        _reset_usage_if_new_day()
        
        # Read current data
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Get limits from environment or defaults
        limits = get_daily_limits()
        
        # Calculate remaining limits
        remaining = {
            "search": limits["search"] - data.get("search_count", 0),
            "media": limits["media"] - data.get("media_count", 0)
        }
        
        return remaining
    except Exception as e:
        logger.error(f"Error getting remaining limits: {e}")
        # Default remaining limits if there's an error
        return {
            "search": 10,
            "media": 10
        } 