"""
Unit tests for the Telegram bot using the unittest framework.
This provides an alternative to the pytest-based tests.
"""
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot

class TestBot(unittest.TestCase):
    """Test cases for the Telegram bot."""
    
    def setUp(self):
        """Set up test fixtures."""
        from telegram import Update, User, Message, Chat
        from telegram.ext import ContextTypes
        
        self.update = MagicMock(spec=Update)
        self.context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Mock user
        self.user = MagicMock(spec=User)
        self.user.mention_html.return_value = "@test_user"
        
        # Mock message
        self.message = MagicMock(spec=Message)
        self.message.reply_text = AsyncMock()
        self.message.reply_html = AsyncMock()
        
        # Set up update with user and message
        self.update.effective_user = self.user
        self.update.message = self.message
        
        # Set up chat
        self.chat = MagicMock(spec=Chat)
        self.update.message.chat = self.chat
    
    def run_async(self, coroutine):
        """Helper to run async functions in tests."""
        # Create a new event loop for each test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    def test_start_command(self):
        """Test the /start command."""
        # Run the start command
        self.run_async(bot.start(self.update, self.context))
        
        # Check that reply_html was called with the expected message
        self.message.reply_html.assert_called_once()
        call_args = self.message.reply_html.call_args[0][0]
        self.assertIn("Hi @test_user", call_args)
        self.assertIn("I'm Firtigh", call_args)
    
    def test_help_command(self):
        """Test the /help command."""
        # Run the help command
        self.run_async(bot.help_command(self.update, self.context))
        
        # Check that reply_text was called with the expected message
        self.message.reply_text.assert_called_once()
        call_args = self.message.reply_text.call_args[0][0]
        self.assertIn("@@firtigh", call_args)
    
    @patch('bot.generate_ai_response')
    def test_handle_message_with_mention(self, mock_generate):
        """Test handling a message that mentions the bot."""
        # Set up the mock response
        async def mock_response(*args, **kwargs):
            return "This is a test AI response"
        
        mock_generate.side_effect = mock_response
        
        # Set up the message text
        self.message.text = "Hello @@firtigh, how are you?"
        
        # Run the message handler
        self.run_async(bot.handle_message(self.update, self.context))
        
        # Check that generate_ai_response was called with the correct prompt
        mock_generate.assert_called_once_with("Hello , how are you?")
        
        # Check that reply_text was called with the expected response
        self.message.reply_text.assert_called_once_with("This is a test AI response")
    
    @patch('bot.generate_ai_response')
    def test_handle_message_without_query(self, mock_generate):
        """Test handling a message that mentions the bot but has no query."""
        # Set up the message text
        self.message.text = "@@firtigh"
        
        # Run the message handler
        self.run_async(bot.handle_message(self.update, self.context))
        
        # Check that generate_ai_response was not called
        mock_generate.assert_not_called()
        
        # Check that reply_text was called with the expected message
        self.message.reply_text.assert_called_once()
        call_args = self.message.reply_text.call_args[0][0]
        self.assertIn("You mentioned me", call_args)
    
    def test_handle_message_without_mention(self):
        """Test handling a message that doesn't mention the bot."""
        # Set up the message text
        self.message.text = "Hello, how are you?"
        
        # Run the message handler
        self.run_async(bot.handle_message(self.update, self.context))
        
        # Check that reply_text was not called
        self.message.reply_text.assert_not_called()
    
    @patch('openai.ChatCompletion.create')
    def test_generate_ai_response_success(self, mock_create):
        """Test successful AI response generation."""
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is a test AI response"
        mock_create.return_value = mock_response
        
        # Call the function and check the result
        result = self.run_async(bot.generate_ai_response("Test prompt"))
        self.assertEqual(result, "This is a test AI response")
        
        # Check that the OpenAI API was called with the expected parameters
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-3.5-turbo")
        self.assertEqual(call_kwargs["messages"][1]["content"], "Test prompt")
    
    @patch('openai.ChatCompletion.create')
    def test_generate_ai_response_error(self, mock_create):
        """Test AI response generation with an error."""
        # Set up the mock to raise an exception
        mock_create.side_effect = Exception("API error")
        
        # Call the function and check the result
        result = self.run_async(bot.generate_ai_response("Test prompt"))
        self.assertIn("Sorry", result)

if __name__ == '__main__':
    unittest.main() 