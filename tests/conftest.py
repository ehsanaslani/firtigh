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
    update.message = message
    
    # Mock chat
    chat = MagicMock(spec=Chat)
    update.message.chat = chat
    
    return update

@pytest.fixture
def mock_context():
    """Create a mock Telegram Context object."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    return context 