"""
Pytest configuration file with common fixtures.
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the bot module
import bot

@pytest.fixture
def mock_update():
    """Create a mock Telegram Update object."""
    update = MagicMock(spec=Update)
    
    # Mock user
    user = MagicMock(spec=User)
    user.mention_html.return_value = "@test_user"
    update.effective_user = user
    
    # Mock message
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    message.reply_html = AsyncMock()
    message.text = ""
    message.photo = []
    message.animation = None
    message.reply_to_message = None
    update.message = message
    
    # Mock from_user for the message
    from_user = MagicMock(spec=User)
    from_user.username = "test_user"
    from_user.first_name = "Test"
    from_user.last_name = "User"
    update.message.from_user = from_user
    
    # Mock chat
    chat = MagicMock(spec=Chat)
    chat.id = 123456789  # Sample chat ID
    update.message.chat = chat
    
    return update

@pytest.fixture
def mock_context():
    """Create a mock Telegram Context object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    
    # Set up bot property
    bot_mock = MagicMock()
    bot_mock.id = 987654321  # Sample bot ID
    context.bot = bot_mock
    
    # Create bot.get_me function
    async def mock_get_me():
        user = MagicMock(spec=User)
        user.id = 987654321
        user.username = "firtigh"
        return user
    
    context.bot.get_me = mock_get_me
    
    return context 