import os
import json
import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Path to store message history
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MESSAGES_FILE = os.path.join(DATA_DIR, "message_history.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def initialize_database():
    """Initialize the database file if it doesn't exist."""
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump({"messages": []}, f, ensure_ascii=False)
        logger.info(f"Created new message history file at {MESSAGES_FILE}")

def save_message(message_data: Dict[str, Any]) -> bool:
    """
    Save a message to the database.
    
    Args:
        message_data: Dictionary containing message information
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        initialize_database()
        
        # Read existing data
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Add new message
        data["messages"].append(message_data)
        
        # Limit to the most recent 1000 messages
        if len(data["messages"]) > 1000:
            data["messages"] = data["messages"][-1000:]
            logger.info("Trimmed message history to 1000 most recent messages")
        
        # Write updated data
        with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Error saving message to database: {e}")
        return False

def get_messages(days: int = 3, chat_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieve messages from the past specified number of days.
    
    Args:
        days: Number of days to look back
        chat_id: If provided, only get messages from this chat
    
    Returns:
        List of message dictionaries
    """
    try:
        if not os.path.exists(MESSAGES_FILE):
            return []
        
        # Calculate cutoff date
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
        
        # Read data
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Filter messages by date and chat_id if provided
        filtered_messages = []
        for msg in data["messages"]:
            if msg.get("date", 0) >= cutoff_date:
                if chat_id is None or msg.get("chat_id") == chat_id:
                    filtered_messages.append(msg)
        
        return filtered_messages
    except Exception as e:
        logger.error(f"Error retrieving messages from database: {e}")
        return []

def format_message_for_summary(message: Dict[str, Any]) -> str:
    """Format a message dictionary into a string for summarization."""
    # Get basic message info
    sender = message.get("sender_name", "Unknown")
    date_str = datetime.datetime.fromtimestamp(message.get("date", 0)).strftime("%Y-%m-%d %H:%M")
    text = message.get("text", "")
    
    # Handle different message types
    if message.get("has_photo"):
        text += " [IMAGE]"
    if message.get("has_animation"):
        text += " [GIF]"
    if message.get("has_sticker"):
        text += f" [STICKER: {message.get('sticker_emoji', '')}]"
    if message.get("has_document"):
        text += f" [FILE: {message.get('document_name', '')}]"
    
    return f"{date_str} - {sender}: {text}"

def get_formatted_message_history(days: int = 3, chat_id: Optional[int] = None) -> str:
    """
    Get a formatted string of message history for summarization.
    
    Args:
        days: Number of days to look back
        chat_id: If provided, only get messages from this chat
    
    Returns:
        Formatted string of message history
    """
    messages = get_messages(days, chat_id)
    
    if not messages:
        return "No messages found in the specified time period."
    
    # Format messages
    formatted_messages = [format_message_for_summary(msg) for msg in messages]
    
    # Return as string
    return "\n".join(formatted_messages) 