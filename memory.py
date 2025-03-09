import os
import json
import logging
import time
import datetime
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import openai
import anthropic

# Configure logging
logger = logging.getLogger(__name__)

# Path to store memory data
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MEMORY_FILE = os.path.join(DATA_DIR, "group_memory.json")
USER_PROFILES_FILE = os.path.join(DATA_DIR, "user_profiles.json")
NAME_CORRECTIONS_FILE = os.path.join(DATA_DIR, "name_corrections.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Constants
MAX_MEMORY_ITEMS_PER_GROUP = 100  # Increased from 30 to 100
MAX_PROFILE_CHARACTERISTICS = 20  # Increased from 10 to 20
MEMORY_REFRESH_DAYS = 30  # How long before a memory item is considered "old"
MODEL_FOR_ANALYSIS = "claude-3-5-haiku-20240307"

# Initialize the Anthropic client
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
        
    # Initialize name corrections
    if not os.path.exists(NAME_CORRECTIONS_FILE):
        with open(NAME_CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({"corrections": {}}, f, ensure_ascii=False, indent=2)
        logger.info(f"Created new name corrections file at {NAME_CORRECTIONS_FILE}")

async def analyze_message_for_memory(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a message to extract key information and determine memorability.
    
    Args:
        message_data: Dictionary containing message data
        
    Returns:
        Dictionary with memory metadata
    """
    message_text = message_data.get("text", "")
    if not message_text or len(message_text) < 5:
        return {
            "is_memorable": False,
            "reason": "Message too short"
        }
    
    # Prepare prompt for analysis
    prompt = f"""
    Analyze this message for memorability and extract key information.
    
    Message: "{message_text}"
    
    Instructions:
    1. Determine if this message contains information worth remembering
    2. Extract key topics discussed
    3. Extract key points or claims
    4. Determine overall sentiment (positive, negative, neutral)
    5. Extract any personal information about the sender
    
    Respond with a JSON object in this format:
    {{
        "is_memorable": boolean, // true if worth remembering
        "reason": string, // brief reason why memorable or not
        "topics": list of strings, // key topics (max 3)
        "key_points": list of strings, // important points (max 3)
        "sentiment": string, // "positive", "negative", or "neutral"
        "sender_traits": list of strings // personality traits or facts about sender (max 3)
    }}
    """
    
    # Use Claude for analysis with v0.21.2 API
    response = claude_client.completion(
        prompt=prompt,
        model=MODEL_FOR_ANALYSIS,
        max_tokens_to_sample=400,
        temperature=0.1  # Low temperature for consistent output
    )
    
    # Get the response content
    result_text = response.completion.strip()
    
    # Handle potential errors in JSON parsing
    try:
        # Find and extract just the JSON part
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = result_text[start_idx:end_idx]
            analysis = json.loads(json_str)
        else:
            # If no JSON markers found, try to parse the whole response
            analysis = json.loads(result_text)
        
        # Add additional metadata
        analysis["message_id"] = message_data.get("message_id")
        analysis["message_text"] = message_text
        analysis["timestamp"] = message_data.get("date", time.time())
        analysis["sender_id"] = message_data.get("sender_id")
        analysis["sender_name"] = message_data.get("sender_name", "Unknown")
        
        return analysis
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing memory analysis: {e}")
        # Return a simple analysis to avoid blocking the message processing
        return {
            "is_memorable": len(message_text) > 50,  # Consider longer messages potentially memorable
            "reason": "Automatic analysis (parsing error)",
            "topics": [],
            "key_points": [message_text[:100] + "..."] if len(message_text) > 100 else [message_text],
            "sentiment": "neutral",
            "sender_traits": [],
            "message_id": message_data.get("message_id"),
            "message_text": message_text,
            "timestamp": message_data.get("date", time.time()),
            "sender_id": message_data.get("sender_id"),
            "sender_name": message_data.get("sender_name", "Unknown")
        }
    except Exception as e:
        logger.error(f"Unexpected error in memory analysis: {e}")
        return {
            "is_memorable": False,
            "reason": "Analysis error",
            "message_id": message_data.get("message_id"),
            "message_text": message_text,
            "timestamp": message_data.get("date", time.time()),
            "sender_id": message_data.get("sender_id"),
            "sender_name": message_data.get("sender_name", "Unknown")
        }

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
        # Lower the threshold to remember more items, not just the ones marked as memorable
        is_somewhat_interesting = (
            memory_item.get("is_memorable", False) or
            (len(memory_item.get("key_points", [])) > 0) or
            (memory_item.get("sentiment") in ["very positive", "very negative"])
        )
        
        if is_somewhat_interesting or (len(memory_data["groups"][str(chat_id)]) < 20):
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

async def update_user_profile(user_id: int, username: str, traits: List[str], topics: List[str], 
                             sentiment: str, interests: List[str] = None, tone: str = None,
                             language_quality: str = None):
    """
    Update a user's profile with new information.
    
    Args:
        user_id: The user's Telegram ID
        username: The user's username or first name
        traits: List of traits exhibited in the message
        topics: List of topics the user discussed
        sentiment: The message sentiment
        interests: List of interests inferred from the message
        tone: The tone of the message
        language_quality: Assessment of language use
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
                "interests": {},
                "tone_counts": {},
                "language_quality_counts": {},
                "last_updated": time.time(),
                "first_seen": time.time(),
                "message_count": 0
            }
        else:
            # Update username in case it changed
            profile_data["users"][str(user_id)]["username"] = username
        
        # Increment message count
        profile_data["users"][str(user_id)]["message_count"] = profile_data["users"][str(user_id)].get("message_count", 0) + 1
        
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
        
        # Update interests
        if interests:
            for interest in interests:
                if interest:
                    interest = interest.lower()
                    if interest in profile_data["users"][str(user_id)].get("interests", {}):
                        profile_data["users"][str(user_id)]["interests"][interest] += 1
                    else:
                        if "interests" not in profile_data["users"][str(user_id)]:
                            profile_data["users"][str(user_id)]["interests"] = {}
                        profile_data["users"][str(user_id)]["interests"][interest] = 1
        
        # Update tone counts
        if tone:
            tone = tone.lower()
            if "tone_counts" not in profile_data["users"][str(user_id)]:
                profile_data["users"][str(user_id)]["tone_counts"] = {}
            
            if tone in profile_data["users"][str(user_id)]["tone_counts"]:
                profile_data["users"][str(user_id)]["tone_counts"][tone] += 1
            else:
                profile_data["users"][str(user_id)]["tone_counts"][tone] = 1
        
        # Update language quality counts
        if language_quality:
            lang_quality = language_quality.lower()
            if "language_quality_counts" not in profile_data["users"][str(user_id)]:
                profile_data["users"][str(user_id)]["language_quality_counts"] = {}
            
            if lang_quality in profile_data["users"][str(user_id)]["language_quality_counts"]:
                profile_data["users"][str(user_id)]["language_quality_counts"][lang_quality] += 1
            else:
                profile_data["users"][str(user_id)]["language_quality_counts"][lang_quality] = 1
        
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
        
        # Prune interests to keep only the most frequent
        if "interests" in profile_data["users"][str(user_id)]:
            profile_data["users"][str(user_id)]["interests"] = dict(
                sorted(profile_data["users"][str(user_id)]["interests"].items(), 
                       key=lambda item: item[1], reverse=True)[:MAX_PROFILE_CHARACTERISTICS]
            )
        
        # Write updated data
        with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Updated profile for user {username} (ID: {user_id})")
    
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")

def store_name_correction(username: str, correct_persian_name: str):
    """
    Store a corrected name mapping for future use.
    
    Args:
        username: The original username or English name
        correct_persian_name: The corrected Persian name
    """
    try:
        initialize_memory()
        
        # Read existing corrections data
        with open(NAME_CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            corrections_data = json.load(f)
        
        # Store the correction
        corrections_data["corrections"][username.lower()] = correct_persian_name
        
        # Write updated data
        with open(NAME_CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(corrections_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Stored name correction: {username} -> {correct_persian_name}")
    
    except Exception as e:
        logger.error(f"Error storing name correction: {e}")

def get_persian_name(username: str) -> str:
    """
    Get the corrected Persian name for a username if available.
    
    Args:
        username: The original username or English name
        
    Returns:
        The corrected Persian name if available, or the original username
    """
    try:
        if not os.path.exists(NAME_CORRECTIONS_FILE):
            return username
            
        # Read corrections data
        with open(NAME_CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            corrections_data = json.load(f)
        
        # Look up correction
        return corrections_data["corrections"].get(username.lower(), username)
    
    except Exception as e:
        logger.error(f"Error retrieving name correction: {e}")
        return username

def get_group_memory(chat_id: int, limit: int = 30) -> List[Dict[str, Any]]:
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
        if str(chat_id) not in memory_data["groups"]:
            return []
            
        group_memory = memory_data["groups"][str(chat_id)]
        
        # Sort by timestamp (newest first) and limit
        group_memory.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return group_memory[:limit]
    
    except Exception as e:
        logger.error(f"Error retrieving group memory: {e}")
        return []

def get_user_profile(user_id: int) -> Dict[str, Any]:
    """
    Get the profile for a specific user.
    
    Args:
        user_id: The user's Telegram ID
    
    Returns:
        User profile dictionary
    """
    try:
        if not os.path.exists(USER_PROFILES_FILE):
            return {}
            
        # Read profile data
        with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        
        # Get user profile
        if str(user_id) not in profile_data["users"]:
            return {}
            
        return profile_data["users"][str(user_id)]
    
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        return {}

def format_memory_for_context(memory_items: List[Dict[str, Any]]) -> str:
    """
    Format memory items for inclusion in the AI prompt context.
    
    Args:
        memory_items: List of memory items
    
    Returns:
        Formatted string of memory items
    """
    if not memory_items:
        return ""
    
    # Build list of memory points grouped by topic
    memory_by_topic = defaultdict(list)
    
    for item in memory_items:
        # Extract key information
        topics = item.get("topics", [])
        key_points = item.get("key_points", [])
        message_text = item.get("message_text", "")
        
        # Get sender info
        sender_name = item.get("sender_name", "")
        if sender_name:
            # Try to get Persian version of the name
            sender_name = get_persian_name(sender_name)
        
        # Skip if no useful information
        if not (topics or key_points):
            continue
        
        # Add to topics
        for topic in topics:
            if topic and key_points:
                memory_by_topic[topic].extend([f"{point} (از {sender_name})" for point in key_points])
            elif topic and message_text:
                memory_by_topic[topic].append(f"«{message_text[:100]}...» (از {sender_name})")
    
    # Format the memory
    if memory_by_topic:
        memory_text = "حافظه گروه (موضوعات مهم و نکات کلیدی):\n"
        
        for topic, points in memory_by_topic.items():
            memory_text += f"\nموضوع: {topic}\n"
            unique_points = list(set(points))[:5]  # Limit to 5 unique points per topic
            for point in unique_points:
                memory_text += f"- {point}\n"
        
        return memory_text
    
    return ""

def format_user_profile_for_context(profile: Dict[str, Any]) -> str:
    """
    Format a user profile for inclusion in the AI prompt context.
    
    Args:
        profile: User profile dictionary
    
    Returns:
        Formatted string of the user profile
    """
    if not profile:
        return ""
    
    # Extract key information
    username = profile.get("username", "")
    
    # Try to get Persian version of the username
    persian_name = get_persian_name(username) if username else ""
    
    traits = profile.get("traits", {})
    topics = profile.get("topics_of_interest", {})
    sentiment_counts = profile.get("sentiment_counts", {})
    interests = profile.get("interests", {})
    tone_counts = profile.get("tone_counts", {})
    language_quality = profile.get("language_quality_counts", {})
    message_count = profile.get("message_count", 0)
    
    # Calculate overall sentiment
    overall_sentiment = "خنثی"
    if sentiment_counts:
        pos = sentiment_counts.get("positive", 0)
        neg = sentiment_counts.get("negative", 0)
        neu = sentiment_counts.get("neutral", 0)
        
        if pos > neg and pos > neu:
            overall_sentiment = "مثبت"
        elif neg > pos and neg > neu:
            overall_sentiment = "منفی"
    
    # Get dominant tone
    dominant_tone = "معمولی"
    if tone_counts:
        max_tone = max(tone_counts.items(), key=lambda x: x[1], default=("معمولی", 0))
        dominant_tone = max_tone[0]
    
    # Get dominant language quality
    dominant_lang = "استاندارد"
    if language_quality:
        max_lang = max(language_quality.items(), key=lambda x: x[1], default=("استاندارد", 0))
        dominant_lang = max_lang[0]
    
    # Format traits
    traits_text = ""
    if traits:
        top_traits = sorted(traits.items(), key=lambda x: x[1], reverse=True)[:5]
        traits_text = ", ".join([f"{trait}" for trait, _ in top_traits])
    
    # Format topics
    topics_text = ""
    if topics:
        top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:5]
        topics_text = ", ".join([f"{topic}" for topic, _ in top_topics])
    
    # Format interests
    interests_text = ""
    if interests:
        top_interests = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:5]
        interests_text = ", ".join([f"{interest}" for interest, _ in top_interests])
    
    # Build profile text
    profile_text = f"پروفایل کاربر {persian_name or username}:\n"
    
    if traits_text:
        profile_text += f"- ویژگی‌های شخصیتی: {traits_text}\n"
    
    if topics_text:
        profile_text += f"- موضوعات مورد بحث: {topics_text}\n"
    
    if interests_text:
        profile_text += f"- علایق: {interests_text}\n"
    
    profile_text += f"- لحن معمول: {dominant_tone}\n"
    profile_text += f"- سبک نگارش: {dominant_lang}\n"
    profile_text += f"- نگرش کلی: {overall_sentiment}\n"
    profile_text += f"- تعداد پیام‌ها: {message_count}\n"
    
    if persian_name and persian_name != username:
        profile_text += f"- نام فارسی: {persian_name}\n"
    
    return profile_text

async def process_message_for_memory(message_data: Dict[str, Any]):
    """
    Process a message for memory and user profile updates.
    
    Args:
        message_data: Dictionary containing message information
    """
    try:
        # Analyze message
        memory_item = await analyze_message_for_memory(message_data)
        
        if not memory_item:
            return
        
        # Get chat and user IDs
        chat_id = message_data.get("chat_id")
        user_id = message_data.get("sender_id")
        
        if not chat_id or not user_id:
            return
        
        # Update group memory
        await update_group_memory(chat_id, memory_item)
        
        # Update user profile
        if "sender_name" in message_data:
            await update_user_profile(
                user_id, 
                message_data["sender_name"],
                memory_item.get("sender_traits", []),
                memory_item.get("topics", []),
                memory_item.get("sentiment", "neutral"),
                memory_item.get("interests", []),
                memory_item.get("tone", None),
                memory_item.get("language_quality", None)
            )
    
    except Exception as e:
        logger.error(f"Error processing message for memory: {e}")

def analyze_for_name_correction(message_text: str) -> Optional[Dict[str, str]]:
    """
    Analyze message for name corrections.
    
    Args:
        message_text: The message text to analyze
    
    Returns:
        Dictionary with original and corrected names if a correction is found
    """
    try:
        # Simple pattern matching for common correction phrases
        correction_patterns = [
            r"(?:اسم|نام) من (\S+) (?:هست|است)، نه (\S+)",  # "My name is X, not Y"
            r"من رو (\S+) صدا کن، نه (\S+)",  # "Call me X, not Y"
            r"(\S+) درسته، نه (\S+)",  # "X is correct, not Y"
            r"اسمم (\S+) (?:هست|است) نه (\S+)",  # "My name is X not Y"
        ]
        
        for pattern in correction_patterns:
            import re
            matches = re.search(pattern, message_text)
            if matches:
                correct_name = matches.group(1)
                wrong_name = matches.group(2)
                return {"correct": correct_name, "wrong": wrong_name}
                
        return None
    
    except Exception as e:
        logger.error(f"Error analyzing for name correction: {e}")
        return None 