import os
import json
import logging
import time
import datetime
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import openai

# Configure logging
logger = logging.getLogger(__name__)

# Path to store memory data
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "group_memory.json")
USER_PROFILES_FILE = os.path.join(DATA_DIR, "user_profiles.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Constants
MAX_MEMORY_ITEMS_PER_GROUP = 30  # Maximum number of memory items per group
MAX_PROFILE_CHARACTERISTICS = 10  # Maximum number of traits/topics per user profile
MEMORY_REFRESH_DAYS = 30  # How long before a memory item is considered "old"
MODEL_FOR_ANALYSIS = "gpt-3.5-turbo"  # Cheaper model for analysis

def initialize_memory():
    """Initialize the memory files if they don't exist."""
    # Initialize group memory
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": {}}, f, ensure_ascii=False, indent=2)
        logger.info(f"Created new group memory file at {MEMORY_FILE}")
    
    # Initialize user profiles
    if not os.path.exists(USER_PROFILES_FILE):
        with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, ensure_ascii=False, indent=2)
        logger.info(f"Created new user profiles file at {USER_PROFILES_FILE}")

async def analyze_message_for_memory(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a message to extract potential memory items.
    
    Args:
        message_data: Dictionary containing message information
    
    Returns:
        Dictionary with extracted topics, sentiment, and other information
    """
    try:
        text = message_data.get("text", "")
        
        # Skip empty or very short messages
        if not text or len(text) < 10:
            return {}
        
        # Prepare the prompt for analysis
        prompt = f"""
        Analyze the following message for important information that should be remembered:
        
        MESSAGE: {text}
        
        Provide a JSON response with these fields:
        1. topics: List of up to 3 main topics/subjects discussed
        2. sentiment: Overall emotional tone (positive, negative, neutral)
        3. key_points: List of up to 3 factual statements that would be valuable to remember
        4. user_traits: List of traits the user exhibits in this message
        5. is_memorable: Boolean indicating if this message contains information worth remembering long-term
        """
        
        # Use a cheaper model for analysis
        response = openai.ChatCompletion.create(
            model=MODEL_FOR_ANALYSIS,
            messages=[
                {"role": "system", "content": "You are an AI that extracts key information from messages for memory purposes. Respond ONLY with the requested JSON format."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.1  # Low temperature for consistent output
        )
        
        # Get the response content
        result_text = response.choices[0].message.content.strip()
        
        # Handle potential errors in JSON parsing
        try:
            # Find and extract just the JSON part
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_text = result_text[start_idx:end_idx]
                result = json.loads(json_text)
            else:
                # Fallback if no JSON braces found
                result = {
                    "topics": [],
                    "sentiment": "neutral",
                    "key_points": [],
                    "user_traits": [],
                    "is_memorable": False
                }
            
            # Add metadata
            result["timestamp"] = time.time()
            result["message_id"] = message_data.get("message_id")
            result["message_text"] = text[:200]  # Store truncated version
            
            return result
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse analysis result as JSON: {result_text}")
            # Return a basic result
            return {
                "topics": [],
                "sentiment": "neutral",
                "key_points": [],
                "user_traits": [],
                "is_memorable": False,
                "timestamp": time.time(),
                "message_id": message_data.get("message_id"),
                "message_text": text[:200]
            }
            
    except Exception as e:
        logger.error(f"Error analyzing message for memory: {e}")
        return {}

async def update_group_memory(chat_id: int, memory_item: Dict[str, Any]):
    """
    Add a new memory item to the group's collective memory.
    
    Args:
        chat_id: The ID of the chat/group
        memory_item: The memory item to add
    """
    try:
        initialize_memory()
        
        # Read existing memory data
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory_data = json.load(f)
        
        # Initialize group memory if it doesn't exist
        if str(chat_id) not in memory_data["groups"]:
            memory_data["groups"][str(chat_id)] = []
        
        # Add new memory item
        if memory_item.get("is_memorable", False):
            memory_data["groups"][str(chat_id)].append(memory_item)
            
            # Sort by timestamp (newest first)
            memory_data["groups"][str(chat_id)].sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            # Limit to maximum number of memory items
            if len(memory_data["groups"][str(chat_id)]) > MAX_MEMORY_ITEMS_PER_GROUP:
                memory_data["groups"][str(chat_id)] = memory_data["groups"][str(chat_id)][:MAX_MEMORY_ITEMS_PER_GROUP]
        
            # Write updated data
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Added new memory item for group {chat_id}")
    
    except Exception as e:
        logger.error(f"Error updating group memory: {e}")

async def update_user_profile(user_id: int, username: str, traits: List[str], topics: List[str], sentiment: str):
    """
    Update a user's profile with new information.
    
    Args:
        user_id: The user's Telegram ID
        username: The user's username or first name
        traits: List of traits exhibited in the message
        topics: List of topics the user discussed
        sentiment: The message sentiment
    """
    try:
        initialize_memory()
        
        # Read existing profile data
        with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        
        # Initialize user profile if it doesn't exist
        if str(user_id) not in profile_data["users"]:
            profile_data["users"][str(user_id)] = {
                "username": username,
                "traits": {},
                "topics_of_interest": {},
                "sentiment_counts": {"positive": 0, "negative": 0, "neutral": 0},
                "last_updated": time.time()
            }
        else:
            # Update username in case it changed
            profile_data["users"][str(user_id)]["username"] = username
        
        # Update traits with frequency count
        for trait in traits:
            if trait:  # Skip empty traits
                trait = trait.lower()
                if trait in profile_data["users"][str(user_id)]["traits"]:
                    profile_data["users"][str(user_id)]["traits"][trait] += 1
                else:
                    profile_data["users"][str(user_id)]["traits"][trait] = 1
        
        # Update topics with frequency count
        for topic in topics:
            if topic:  # Skip empty topics
                topic = topic.lower()
                if topic in profile_data["users"][str(user_id)]["topics_of_interest"]:
                    profile_data["users"][str(user_id)]["topics_of_interest"][topic] += 1
                else:
                    profile_data["users"][str(user_id)]["topics_of_interest"][topic] = 1
        
        # Update sentiment counts
        if sentiment in ["positive", "negative", "neutral"]:
            profile_data["users"][str(user_id)]["sentiment_counts"][sentiment] += 1
        
        # Update last_updated timestamp
        profile_data["users"][str(user_id)]["last_updated"] = time.time()
        
        # Prune traits and topics to keep only the most frequent
        profile_data["users"][str(user_id)]["traits"] = dict(
            sorted(profile_data["users"][str(user_id)]["traits"].items(), 
                   key=lambda item: item[1], reverse=True)[:MAX_PROFILE_CHARACTERISTICS]
        )
        
        profile_data["users"][str(user_id)]["topics_of_interest"] = dict(
            sorted(profile_data["users"][str(user_id)]["topics_of_interest"].items(), 
                   key=lambda item: item[1], reverse=True)[:MAX_PROFILE_CHARACTERISTICS]
        )
        
        # Write updated data
        with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Updated profile for user {username} (ID: {user_id})")
    
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")

def get_group_memory(chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the memory items for a specific group.
    
    Args:
        chat_id: The ID of the chat/group
        limit: Maximum number of memory items to return
    
    Returns:
        List of memory items
    """
    try:
        if not os.path.exists(MEMORY_FILE):
            return []
        
        # Read memory data
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory_data = json.load(f)
        
        # Get group memory
        group_memory = memory_data["groups"].get(str(chat_id), [])
        
        # Return limited number of items
        return group_memory[:limit]
    
    except Exception as e:
        logger.error(f"Error retrieving group memory: {e}")
        return []

def get_user_profile(user_id: int) -> Dict[str, Any]:
    """
    Get a user's profile information.
    
    Args:
        user_id: The user's Telegram ID
    
    Returns:
        Dictionary with user profile information
    """
    try:
        if not os.path.exists(USER_PROFILES_FILE):
            return {}
        
        # Read profile data
        with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        
        # Get user profile
        return profile_data["users"].get(str(user_id), {})
    
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        return {}

def format_memory_for_context(memory_items: List[Dict[str, Any]]) -> str:
    """
    Format memory items into a string for inclusion in AI context.
    
    Args:
        memory_items: List of memory items
    
    Returns:
        Formatted string of memories
    """
    if not memory_items:
        return ""
    
    memory_lines = ["اطلاعات پیشین در مورد این گروه:"]
    
    for item in memory_items:
        # Format timestamp
        timestamp_str = datetime.datetime.fromtimestamp(
            item.get("timestamp", 0)
        ).strftime("%Y-%m-%d")
        
        # Format key points if available
        key_points = item.get("key_points", [])
        if key_points:
            points_text = " | ".join(key_points)
            memory_lines.append(f"- {timestamp_str}: {points_text}")
    
    return "\n".join(memory_lines)

def format_user_profile_for_context(profile: Dict[str, Any]) -> str:
    """
    Format user profile into a string for inclusion in AI context.
    
    Args:
        profile: User profile dictionary
    
    Returns:
        Formatted string of user profile
    """
    if not profile:
        return ""
    
    # Extract username
    username = profile.get("username", "کاربر ناشناس")
    
    # Extract top traits
    traits = list(profile.get("traits", {}).keys())
    
    # Extract top topics of interest
    topics = list(profile.get("topics_of_interest", {}).keys())
    
    # Calculate dominant sentiment
    sentiment_counts = profile.get("sentiment_counts", {"positive": 0, "negative": 0, "neutral": 0})
    dominant_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])[0]
    
    # Map sentiment to Persian
    sentiment_persian = {
        "positive": "مثبت",
        "negative": "منفی",
        "neutral": "خنثی"
    }.get(dominant_sentiment, "خنثی")
    
    # Format the profile information
    profile_lines = [f"اطلاعات کاربر {username}:"]
    
    if traits:
        traits_text = "، ".join(traits[:5])  # Limit to top 5 traits
        profile_lines.append(f"- ویژگی‌ها: {traits_text}")
    
    if topics:
        topics_text = "، ".join(topics[:5])  # Limit to top 5 topics
        profile_lines.append(f"- علایق: {topics_text}")
    
    profile_lines.append(f"- لحن معمول: {sentiment_persian}")
    
    return "\n".join(profile_lines)

async def process_message_for_memory(message_data: Dict[str, Any]):
    """
    Process a message to update memory and user profiles.
    
    Args:
        message_data: Dictionary containing message information
    """
    try:
        # Skip processing if missing essential fields
        if not all(k in message_data for k in ["chat_id", "sender_id", "text"]):
            return
        
        # Extract necessary data
        chat_id = message_data["chat_id"]
        user_id = message_data["sender_id"]
        username = message_data.get("sender_name", "کاربر")
        
        # Analyze the message
        analysis = await analyze_message_for_memory(message_data)
        
        if analysis:
            # Update group memory if the message is memorable
            await update_group_memory(chat_id, analysis)
            
            # Update user profile with traits, topics, and sentiment
            await update_user_profile(
                user_id, 
                username, 
                analysis.get("user_traits", []),
                analysis.get("topics", []),
                analysis.get("sentiment", "neutral")
            )
            
    except Exception as e:
        logger.error(f"Error processing message for memory: {e}") 