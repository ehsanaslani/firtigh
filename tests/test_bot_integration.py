import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot

# Helper function to run async tests
async def async_return(result):
    return result

# Run async function in a synchronous context
def run_async(coroutine):
    """Helper to run async functions in tests."""
    # Create a new event loop for each test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

def test_start_command(mock_update, mock_context):
    """Test the /start command."""
    # Run the start command
    run_async(bot.start(mock_update, mock_context))
    
    # Check that reply_html was called with the expected message
    mock_update.message.reply_html.assert_called_once()
    call_args = mock_update.message.reply_html.call_args[0][0]
    assert "Hi @test_user" in call_args
    assert "I'm Firtigh" in call_args

def test_help_command(mock_update, mock_context):
    """Test the /help command."""
    # Run the help command
    run_async(bot.help_command(mock_update, mock_context))
    
    # Check that reply_text was called with the expected message
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "@@firtigh" in call_args

@patch('bot.generate_ai_response')
def test_handle_message_with_mention(mock_generate, mock_update, mock_context):
    """Test handling a message that mentions the bot."""
    # Set up the mock response
    async def mock_response(*args, **kwargs):
        return "This is a test AI response"
    
    mock_generate.side_effect = mock_response
    
    # Set up the message text
    mock_update.message.text = "Hello @@firtigh, how are you?"
    
    # Run the message handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that generate_ai_response was called with the correct prompt
    mock_generate.assert_called_once_with("Hello , how are you?")
    
    # Check that reply_text was called with the expected response
    mock_update.message.reply_text.assert_called_once_with("This is a test AI response")

@patch('bot.generate_ai_response')
def test_handle_message_without_query(mock_generate, mock_update, mock_context):
    """Test handling a message that mentions the bot but has no query."""
    # Set up the message text
    mock_update.message.text = "@@firtigh"
    
    # Run the message handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that generate_ai_response was not called
    mock_generate.assert_not_called()
    
    # Check that reply_text was called with the expected message
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "You mentioned me" in call_args

def test_handle_message_without_mention(mock_update, mock_context):
    """Test handling a message that doesn't mention the bot."""
    # Set up the message text
    mock_update.message.text = "Hello, how are you?"
    
    # Run the message handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that reply_text was not called
    mock_update.message.reply_text.assert_not_called()

@patch('openai.ChatCompletion.create')
def test_generate_ai_response_success(mock_create):
    """Test successful AI response generation."""
    # Set up the mock response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "This is a test AI response"
    mock_create.return_value = mock_response
    
    # Call the function and check the result
    result = run_async(bot.generate_ai_response("Test prompt"))
    assert result == "This is a test AI response"
    
    # Check that the OpenAI API was called with the expected parameters
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["model"] == "gpt-3.5-turbo"
    assert call_kwargs["messages"][1]["content"] == "Test prompt"

@patch('openai.ChatCompletion.create')
def test_generate_ai_response_error(mock_create):
    """Test AI response generation with an error."""
    # Set up the mock to raise an exception
    mock_create.side_effect = Exception("API error")
    
    # Call the function and check the result
    result = run_async(bot.generate_ai_response("Test prompt"))
    assert "Sorry" in result

if __name__ == '__main__':
    pytest.main() 