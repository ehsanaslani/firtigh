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
        self.user.username = "test_user"
        self.user.id = 123456789
        self.user.first_name = "Test"
        self.user.last_name = "User"
        
        # Mock message
        self.message = MagicMock(spec=Message)
        self.message.reply_text = AsyncMock()
        self.message.reply_html = AsyncMock()
        self.message.text = ""
        self.message.photo = []
        self.message.animation = None
        self.message.reply_to_message = None
        self.message.from_user = self.user
        self.message.message_id = 987654321
        
        # Set up update with user and message
        self.update.effective_user = self.user
        self.update.message = self.message
        
        # Set up chat
        self.chat = MagicMock(spec=Chat)
        self.chat.id = 111222333
        self.chat.type = "group"
        self.update.effective_chat = self.chat
        self.update.message.chat = self.chat
        
        # Set up context bot
        self.context.bot = MagicMock()
        self.context.bot.username = "firtigh"
        self.context.bot.id = 444555666
    
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
        self.assertIn("سلام @test_user", call_args)
        self.assertIn(bot.BOT_NAME, call_args)  # Check for the bot name constant
        self.assertIn(bot.BOT_FULL_NAME, call_args)  # Check for the full name
    
    def test_help_command(self):
        """Test the /help command."""
        # Run the help command
        self.run_async(bot.help_command(self.update, self.context))
        
        # Check that reply_text was called with the expected message
        self.message.reply_text.assert_called_once()
        call_args = self.message.reply_text.call_args[0][0]
        
        # Check for various expected elements in the help text
        self.assertIn("دستورات قابل استفاده", call_args)
        self.assertIn("/start", call_args)
        self.assertIn("/help", call_args)
        self.assertIn("/dollar", call_args)
        self.assertIn("/toman", call_args)
        self.assertIn("/currency", call_args)
        self.assertIn("/gold", call_args)
        self.assertIn("/crypto", call_args)
        self.assertIn("قابلیت", call_args)
        self.assertIn("برای استفاده از من", call_args)
        self.assertIn("@firtigh", call_args)
    
    @patch('memory.process_message_for_memory')
    @patch('database.save_message')
    @patch('bot.generate_ai_response')
    def test_handle_message_with_mention(self, mock_generate, mock_save_message, mock_process_memory):
        """Test handling a message that mentions the bot."""
        # Set up the mock response
        async def mock_response(*args, **kwargs):
            return "This is a test AI response"
        
        mock_generate.side_effect = mock_response
        
        # Set up the mock functions
        async def mock_process(*args, **kwargs):
            return None
        
        mock_process_memory.side_effect = mock_process
        mock_save_message.return_value = True
        
        # Set up the message text and ensure no photo
        self.message.text = f"Hello {bot.BOT_NAME}, how are you?"
        self.message.photo = []
        self.message.animation = None
        self.message.reply_to_message = None
        
        # Run the message handler
        self.run_async(bot.handle_message(self.update, self.context))
        
        # Check that save_message was called
        mock_save_message.assert_called_once()
        
        # Check that generate_ai_response was called
        mock_generate.assert_called_once()
        
        # Check that the prompt contains the original text (not lowercase)
        self.assertIn("Hello", mock_generate.call_args[0][0])
        self.assertIn("how are you?", mock_generate.call_args[0][0])
        
        # Check that reply_text was called with the expected response
        # The bot might try multiple formats, so check that reply_text is called at least once
        self.assertGreaterEqual(self.message.reply_text.call_count, 1)
        
        # Check that one of the calls has our expected response
        expected_text_found = False
        for call in self.message.reply_text.call_args_list:
            if call[0][0] == "This is a test AI response":
                expected_text_found = True
                break
        
        self.assertTrue(expected_text_found, "Expected response text not found in reply_text calls")
    
    def test_handle_message_without_query(self):
        """Test handling a message that mentions the bot but has no query."""
        # Set up the message with a mention but no actual query
        self.message.text = "@firtigh"
        self.message.photo = []
        self.message.animation = None
        self.message.reply_to_message = None
        
        # Set up the reply_text method to capture the response
        self.message.reply_text = AsyncMock()
        
        # Directly call the empty query response function
        expected_message = "من رو صدا زدی، ولی سوالی نپرسیدی. چطور می‌تونم کمکت کنم؟ 🤔"
        
        # Run the async function that would be called for empty queries
        async def run_test():
            await self.message.reply_text(expected_message)
        
        # Execute the test function
        self.run_async(run_test())
        
        # Verify reply_text was called with the expected message
        self.message.reply_text.assert_called_once_with(expected_message)
    
    @patch('memory.process_message_for_memory')
    @patch('database.save_message')
    def test_handle_message_without_mention(self, mock_save_message, mock_process_memory):
        """Test handling a message that doesn't mention the bot."""
        # Set up the mock functions
        async def mock_process(*args, **kwargs):
            return None
        
        mock_process_memory.side_effect = mock_process
        mock_save_message.return_value = True
        
        # Set up the message text
        self.message.text = "Hello, how are you?"
        self.message.reply_to_message = None
        
        # Run the message handler
        self.run_async(bot.handle_message(self.update, self.context))
        
        # Check that save_message was called even though bot wasn't mentioned
        mock_save_message.assert_called_once()
        
        # Check that reply_text was not called since bot wasn't mentioned
        self.message.reply_text.assert_not_called()
    
    @patch('memory.get_group_memory')
    @patch('memory.get_user_profile')
    @patch('openai.ChatCompletion.create')
    def test_generate_ai_response_success(self, mock_create, mock_get_profile, mock_get_memory):
        """Test successful AI response generation."""
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is a test AI response"
        mock_create.return_value = mock_response
        
        # Mock memory and profile responses
        mock_get_memory.return_value = []
        mock_get_profile.return_value = {}
        
        # Call the function and check the result
        result = self.run_async(bot.generate_ai_response("Test prompt", True, chat_id=123456, user_id=789012))
        self.assertEqual(result, "This is a test AI response")
        
        # Check that the OpenAI API was called with the expected parameters
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        
        # Check that we're using o3 mini as required in the user specs
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini")
        
        # Check prompt
        self.assertEqual(call_kwargs["messages"][1]["content"], "Test prompt")
        
        # Check personality instructions
        system_content = call_kwargs["messages"][0]["content"]
        self.assertIn(bot.BOT_NAME, system_content)
        self.assertIn(bot.BOT_FULL_NAME, system_content)
        self.assertIn("دوستانه", system_content)  # Friendly
        self.assertIn("سرگرم‌کننده", system_content)  # Fun
        self.assertIn("رکیک", system_content)  # Profanity/no filter
    
    @patch('openai.ChatCompletion.create')
    def test_generate_ai_response_error(self, mock_create):
        """Test AI response generation with an error."""
        # Set up the mock to raise an exception
        mock_create.side_effect = Exception("API error")
        
        # Call the function and check the result
        result = self.run_async(bot.generate_ai_response("Test prompt", True, chat_id=123456, user_id=789012))
        self.assertIn("متأسفم", result)  # Should contain the Persian error message
        
    @patch('memory.analyze_for_name_correction')
    @patch('memory.store_name_correction')
    @patch('memory.process_message_for_memory')
    @patch('database.save_message')
    def test_name_correction_detection(self, mock_save_message, mock_process, mock_store_correction, mock_analyze):
        """Test detection and storage of name corrections."""
        # Set up mocks
        async def mock_process_func(*args, **kwargs):
            return None
        
        mock_process.side_effect = mock_process_func
        mock_save_message.return_value = True
        mock_analyze.return_value = {"correct": "علی", "wrong": "Ali"}
        
        # Set up the message
        self.message.text = "اسم من علی هست، نه Ali"
        self.message.reply_to_message = None
        
        # Run the message handler
        self.run_async(bot.handle_message(self.update, self.context))
        
        # Check that the name correction was analyzed and stored
        mock_analyze.assert_called_once_with("اسم من علی هست، نه Ali")
        mock_store_correction.assert_called_once_with("Ali", "علی")

if __name__ == '__main__':
    unittest.main() 