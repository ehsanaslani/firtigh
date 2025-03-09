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

# Google Search configuration
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")

# Usage limits
DAILY_SEARCH_LIMIT = int(os.environ.get("DAILY_SEARCH_LIMIT", 50))
DAILY_MEDIA_LIMIT = int(os.environ.get("DAILY_MEDIA_LIMIT", 10))
DAILY_IMAGE_GEN_LIMIT = int(os.environ.get("DAILY_IMAGE_GEN_LIMIT", 3)) 