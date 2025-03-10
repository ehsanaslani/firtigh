import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

from openai_functions import (
    get_openai_function_definitions,
    process_function_calls,
    search_web,
    extract_content_from_url,
    get_chat_history
)

@pytest.mark.asyncio
async def test_search_web_function():
    """Test the search_web function"""
    with patch('web_search.search_web', new_callable=AsyncMock) as mock_search:
        # Mock the search results
        mock_search.return_value = [
            {"title": "Test Result 1", "snippet": "This is a test result", "link": "https://example.com/1"},
            {"title": "Test Result 2", "snippet": "Another test result", "link": "https://example.com/2"}
        ]
        
        # Call the function
        result = await search_web("test query", is_news=False)
        
        # Check if the original function was called with the right parameters
        mock_search.assert_called_once_with("test query")
        
        # Verify the result structure
        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Test Result 1"

@pytest.mark.asyncio
async def test_extract_content_from_url_function():
    """Test the extract_content_from_url function"""
    with patch('web_extractor.extract_content_from_url', new_callable=AsyncMock) as mock_extract:
        # Mock the extraction result
        mock_extract.return_value = "Extracted content from the URL"
        
        # Call the function
        result = await extract_content_from_url("https://example.com")
        
        # Check if the original function was called with the right parameters
        mock_extract.assert_called_once_with("https://example.com")
        
        # Verify the result
        assert "content" in result
        assert result["content"] == "Extracted content from the URL"

@pytest.mark.asyncio
async def test_get_chat_history_function():
    """Test the get_chat_history function"""
    with patch('summarizer.generate_chat_summary', new_callable=AsyncMock) as mock_summary:
        # Mock the summary result
        mock_summary.return_value = "Summary of chat history for the last 3 days"
        
        # Call the function
        result = await get_chat_history(days=3, chat_id=12345)
        
        # Check if the original function was called with the right parameters
        mock_summary.assert_called_once_with(3, 12345)
        
        # Verify the result
        assert "summary" in result
        assert result["summary"] == "Summary of chat history for the last 3 days"

@pytest.mark.asyncio
async def test_process_function_calls_search():
    """Test processing function calls for search"""
    # Create a mock message with function call
    message = MagicMock()
    message.function_call.name = "search_web"
    message.function_call.arguments = json.dumps({
        "query": "test search",
        "is_news": False
    })
    
    with patch('openai_functions.search_web', new_callable=AsyncMock) as mock_search:
        # Mock the search function
        mock_search.return_value = {"results": [{"title": "Test", "url": "https://test.com"}]}
        
        # Call process_function_calls
        result = await process_function_calls(message, 12345, 67890)
        
        # Verify that search_web was called with the right arguments
        mock_search.assert_called_once_with("test search", is_news=False)
        
        # Check that the result contains the expected data
        assert result["name"] == "search_web"
        assert result["content"]["results"][0]["title"] == "Test"

def test_get_openai_function_definitions():
    """Test that function definitions are correctly formatted"""
    functions = get_openai_function_definitions()
    
    # Check that we have the expected functions
    function_names = [f["name"] for f in functions]
    assert "search_web" in function_names
    assert "extract_content_from_url" in function_names
    assert "get_chat_history" in function_names
    
    # Check schema of one function
    search_func = next(f for f in functions if f["name"] == "search_web")
    assert "description" in search_func
    assert "parameters" in search_func
    assert "properties" in search_func["parameters"]
    assert "query" in search_func["parameters"]["properties"] 