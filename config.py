import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_DEFAULT = os.environ.get("OPENAI_MODEL_DEFAULT", "gpt-4o-mini")
OPENAI_MODEL_VISION = os.environ.get("OPENAI_MODEL_VISION", "gpt-4o")
OPENAI_MODEL_SUMMARY = os.environ.get("OPENAI_MODEL_SUMMARY", "gpt-4o")
OPENAI_MODEL_ANALYSIS = os.environ.get("OPENAI_MODEL_ANALYSIS", "gpt-4o-mini")
OPENAI_MODEL_TRANSLATION = os.environ.get("OPENAI_MODEL_TRANSLATION", "gpt-4o-mini")

# Telegram configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")  # User ID who can access admin commands

# Google Search configuration
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")

# Usage limits
DAILY_SEARCH_LIMIT = int(os.environ.get("DAILY_SEARCH_LIMIT", 50))
DAILY_MEDIA_LIMIT = int(os.environ.get("DAILY_MEDIA_LIMIT", 10))

# OpenWeather API configuration
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

# Feature flags
SERIOUS_MODE_THRESHOLD = 0.7  # Threshold for detecting serious queries
GROUP_MEMORY_ENABLED = True    # Whether to use group memory functionality
USER_PROFILE_ENABLED = True    # Whether to track user profiles 