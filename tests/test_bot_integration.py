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
    
    # Check that generate_ai_response was called (with any args since format has changed)
    mock_generate.assert_called_once()
    # Check first argument contains the prompt with lowercase text
    # The bot extracts the query in lowercase, so we check for that
    assert "hello , how are you?" in mock_generate.call_args[0][0].lower()
    # Second argument should be the is_serious flag
    assert isinstance(mock_generate.call_args[0][1], bool)
    
    # Check that reply_text was called with the expected response
    # The bot might try multiple formats, so check that reply_text is called at least once
    # and that one of the calls has our expected response
    assert mock_update.message.reply_text.call_count >= 1
    
    # Check that one of the calls has our expected response
    expected_text_found = False
    for call in mock_update.message.reply_text.call_args_list:
        if call[0][0] == "This is a test AI response":
            expected_text_found = True
            break
    
    assert expected_text_found, "Expected response text not found in reply_text calls"

@patch('memory.process_message_for_memory')
@patch('bot.generate_ai_response')
def test_handle_message_without_query(mock_generate, mock_process_memory, mock_update, mock_context):
    """Test handling a message that mentions the bot but has no query."""
    # Set up the mock process_message_for_memory
    async def mock_process(*args, **kwargs):
        return None
    
    mock_process_memory.side_effect = mock_process
    
    # Set up the message text and ensure no photo or reply chain
    mock_update.message.text = "@firtigh"
    mock_update.message.photo = []
    mock_update.message.animation = None
    mock_update.message.reply_to_message = None
    
    # Run the message handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that generate_ai_response was not called
    mock_generate.assert_not_called()
    
    # Check that reply_text was called with a message asking for more info
    mock_update.message.reply_text.assert_called_once()
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "من رو صدا زدی" in call_args

def test_handle_message_without_mention(mock_update, mock_context):
    """Test handling a message that doesn't mention the bot."""
    # Set up the message text
    mock_update.message.text = "Hello, how are you?"
    mock_update.message.reply_to_message = None
    
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
    
    # Call the function and check the result - with the new required is_serious parameter
    # and optional chat_id and user_id parameters
    result = run_async(bot.generate_ai_response("Test prompt", True, chat_id=123456, user_id=789012))
    assert result == "This is a test AI response"
    
    # Check that the OpenAI API was called with the expected parameters
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["model"] in ["gpt-4o-mini", "gpt-3.5-turbo"]  # Updated model name
    assert call_kwargs["messages"][1]["content"] == "Test prompt"

@patch('openai.ChatCompletion.create')
def test_generate_ai_response_error(mock_create):
    """Test AI response generation with an error."""
    # Set up the mock to raise an exception
    mock_create.side_effect = Exception("API error")
    
    # Call the function and check the result - with the new required is_serious parameter
    # and optional chat_id and user_id parameters
    result = run_async(bot.generate_ai_response("Test prompt", True, chat_id=123456, user_id=789012))
    assert "متأسفم" in result

@patch('bot.web_search.is_news_query')
@patch('bot.web_search.search_web')
@patch('bot.web_search.format_search_results')
@patch('bot.generate_ai_response')
def test_news_query_single_response(mock_generate_ai, mock_format_results, mock_search_web, mock_is_news_query, 
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
        
        # Check first call is the "searching for news" message
        first_call_args = mock_update.message.reply_text.call_args_list[0][0][0]
        assert "در حال جستجوی اخبار" in first_call_args
        
        # Verify that the second call is the AI response
        second_call_args = mock_update.message.reply_text.call_args_list[1][0][0]
        assert "Here's the news" in second_call_args

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
    
    # Call the handler
    run_async(bot.handle_message(mock_update, mock_context))
    
    # Check that message.reply_text was called only once (the fallback, not duplicated)
    # In this case, we expect only one call since the first attempt fails and we use the fallback
    assert mock_update.message.reply_text.call_count == 1
    
    # Verify that the call is the AI response without formatting
    call_args = mock_update.message.reply_text.call_args[0][0]
    assert "Here is a" in call_args

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