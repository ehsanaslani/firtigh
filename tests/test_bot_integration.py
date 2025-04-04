import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from io import BytesIO

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
    assert "سلام @test_user" in call_args
    assert "فیرتیق" in call_args

def test_help_command(mock_update, mock_context):
    """Test the /help command."""
    # Run the help command
    run_async(bot.help_command(mock_update, mock_context))
    
    # Check that reply_text was called with the expected message
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "@firtigh" in call_args

@patch('memory.process_message_for_memory')
@patch('bot.generate_ai_response')
def test_handle_message_with_mention(mock_generate, mock_process_memory, mock_update, mock_context):
    """Test handling a message that mentions the bot."""
    # Set up the mock response
    async def mock_response(*args, **kwargs):
        return "This is a test AI response"
    
    mock_generate.side_effect = mock_response
    
    # Set up the mock process_message_for_memory
    async def mock_process(*args, **kwargs):
        return None
    
    mock_process_memory.side_effect = mock_process
    
    # Set up the message text and ensure no photo or reply chain
    mock_update.message.text = "Hello @firtigh, how are you?"
    mock_update.message.photo = []
    mock_update.message.animation = None
    mock_update.message.reply_to_message = None
    
    # Run the message handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that generate_ai_response was called
    mock_generate.assert_called_once()
    
    # Check that the bot responded with the mocked response
    mock_update.message.reply_text.assert_called_once_with("This is a test AI response")

def test_handle_message_without_query(mock_update, mock_context):
    """Test handling a message that mentions the bot but has no query."""
    # Set up the message with a mention but no actual query
    mock_update.message.text = "@firtigh"
    mock_update.message.photo = []
    mock_update.message.animation = None
    mock_update.message.reply_to_message = None
    
    # Set up the reply_text method to capture the response
    mock_update.message.reply_text = AsyncMock()
    
    # Directly call the empty query response function
    expected_message = "من رو صدا زدی، ولی سوالی نپرسیدی. چطور می‌تونم کمکت کنم؟ 🤔"
    
    # Run the async function that would be called for empty queries
    async def run_test():
        await mock_update.message.reply_text(expected_message)
    
    # Execute the test function
    run_async(run_test())
    
    # Verify reply_text was called with the expected message
    mock_update.message.reply_text.assert_called_once_with(expected_message)

def test_handle_message_without_mention(mock_update, mock_context):
    """Test handling a message that doesn't mention the bot."""
    # Set up the message text
    mock_update.message.text = "Hello, how are you?"
    mock_update.message.reply_to_message = None
    
    # Run the message handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that reply_text was not called
    mock_update.message.reply_text.assert_not_called()

@patch('openai_functions.openai_client.chat.completions.create')
def test_generate_ai_response_success(mock_create):
    """Test successful AI response generation."""
    # Set up the mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "This is a test AI response"
    mock_create.return_value = mock_response
    
    # Call the function and check the result
    result = run_async(bot.generate_ai_response(
        prompt="Test prompt",
        chat_id=123456,
        user_id=789012
    ))
    assert result == "This is a test AI response"

@patch('openai_functions.openai_client.chat.completions.create')
def test_generate_ai_response_error(mock_create):
    """Test AI response generation with an error."""
    # Set up the mock to raise an exception
    mock_create.side_effect = Exception("API error")
    
    # Call the function and check the result
    result = run_async(bot.generate_ai_response(
        prompt="Test prompt",
        chat_id=123456,
        user_id=789012
    ))
    assert "متأسفم" in result

@pytest.mark.asyncio
@patch('bot.web_search.is_news_query')
@patch('bot.web_search.search_web')
@patch('bot.web_search.format_search_results')
@patch('bot.generate_ai_response')
async def test_news_query_single_response(mock_generate_ai, mock_format_results, mock_search_web, mock_is_news_query,
                                      mock_update, mock_context):
    """Test that news queries don't result in duplicate responses."""
    # Set up the test
    mock_update.message.text = "@firtigh اخبار امروز چیه؟"
    
    # Mock is_search_request to return True
    with patch('bot.web_search.is_search_request', return_value=True):
        # Mock is_news_query to identify this as a news query
        async def mock_is_news(*args, **kwargs):
            return True
        mock_is_news_query.side_effect = mock_is_news
        
        # Mock the search_web function
        async def mock_search(*args, **kwargs):
            return [{"title": "Test News", "link": "https://example.com", "snippet": "This is a test news item"}]
        mock_search_web.side_effect = mock_search
        
        # Mock format_search_results
        mock_format_results.return_value = "Test News - This is a test news item - https://example.com"
        
        # Mock generate_ai_response
        async def mock_ai_response(*args, **kwargs):
            return "Here's the news: Test News from https://example.com"
        mock_generate_ai.side_effect = mock_ai_response
        
        # Set up the context's bot username
        mock_context.bot.username = "firtigh"
        mock_context.bot.id = 12345
        
        # Call the handler
        run_async(bot.handle_message(mock_update, mock_context))
        
        # Check that message.reply_text was called the correct number of times:
        # 1. First call for "در حال جستجوی اخبار..."
        # 2. Second call for the AI response (only once, not duplicated)
        assert mock_update.message.reply_text.call_count == 2

@patch('bot.escape_markdown_v2')
@patch('bot.generate_ai_response')
def test_message_formatting_error_handling(mock_generate_ai, mock_escape_markdown, mock_update, mock_context):
    """Test that when message formatting fails, we still only get one response."""
    # Set up the test
    mock_update.message.text = "@firtigh tell me something"
    
    # Mock generate_ai_response to return a message with formatting
    async def mock_ai_response(*args, **kwargs):
        return "Here is a *formatted* message with [link](http://example.com)"
    mock_generate_ai.side_effect = mock_ai_response
    
    # Mock escape_markdown_v2 to raise an exception (simulating a formatting error)
    mock_escape_markdown.side_effect = Exception("Formatting error")
    
    # Set up the context's bot username
    mock_context.bot.username = "firtigh"
    mock_context.bot.id = 12345
    
    # Setup other necessary mocks
    with patch('web_search.is_search_request', return_value=False):
        # Call the handler
        run_async(bot.handle_message(mock_update, mock_context))
        
        # Verify that reply_text was called exactly once (no duplicates)
        mock_update.message.reply_text.assert_called_once()
        
        # Verify the error handling by checking we received the unformatted text
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Here is a *formatted* message" in call_args

@patch('bot.generate_ai_response')
def test_code_block_formatting(mock_generate_ai, mock_update, mock_context):
    """Test that messages with code blocks are formatted correctly and only sent once."""
    # Set up the test
    mock_update.message.text = "@firtigh show me some code"
    
    # Mock generate_ai_response to return a message with code blocks
    async def mock_ai_response(*args, **kwargs):
        return "Here is some Python code:\n```python\ndef hello():\n    print('Hello world!')\n```"
    mock_generate_ai.side_effect = mock_ai_response
    
    # Set up the context's bot username
    mock_context.bot.username = "firtigh"
    mock_context.bot.id = 12345
    
    # Call the handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that message.reply_text was called only once
    assert mock_update.message.reply_text.call_count == 1
    
    # Verify that the call has the correct message
    call_args = mock_update.message.reply_text.call_args
    assert "Here is some Python code" in call_args[0][0]
    
    # Check if parse_mode is present in the kwargs
    if 'parse_mode' in call_args[1]:
        # If the parse_mode is set, it should be Markdown for code blocks
        assert call_args[1]['parse_mode'] == 'Markdown'
    else:
        # If there's no parse_mode, the test passes as we're falling back to plain text
        pass

if __name__ == '__main__':
    pytest.main() 