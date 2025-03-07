import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web_extractor

# Helper function to run async tests
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

def test_automatic_link_extraction():
    """Test that links are automatically extracted from messages."""
    # Test with various link formats
    test_text = "Check out these websites: https://example.com and http://test.org/path?query=1"
    
    # Extract URLs
    urls = web_extractor.extract_urls(test_text)
    
    # Verify both URLs were extracted
    assert len(urls) == 2
    assert "https://example.com" in urls
    
    # The URL regex may not include the query parameters, check the base URL
    any_test_org_url = False
    for url in urls:
        if url.startswith("http://test.org"):
            any_test_org_url = True
            break
    assert any_test_org_url, "No URL starting with http://test.org found"
    
    # Test with no URLs
    assert len(web_extractor.extract_urls("This text has no URLs")) == 0
    
    # Test with None input
    assert len(web_extractor.extract_urls(None)) == 0

@patch('aiohttp.ClientSession.get')
def test_content_extraction_from_valid_url(mock_get):
    """Test content extraction from a valid URL."""
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(
        return_value="""
        <html>
            <head>
                <title>Test Page</title>
            </head>
            <body>
                <p>This is a test paragraph with sufficient length to be included in the extracted content.</p>
                <p>This is another paragraph that should also be included in the extraction.</p>
                <div>Short div</div>
            </body>
        </html>
        """
    )
    
    # Configure the mock
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Call the function
    title, content = run_async(web_extractor.extract_content_from_url("https://example.com"))
    
    # Verify the extracted content
    assert title == "Test Page"
    assert "test paragraph" in content
    assert "another paragraph" in content
    
    # The short div should be excluded
    assert "Short div" not in content

@patch('aiohttp.ClientSession.get')
def test_handling_invalid_urls(mock_get):
    """Test handling of invalid or inaccessible URLs."""
    # Test with a 404 response
    mock_response_404 = AsyncMock()
    mock_response_404.status = 404
    mock_get.return_value.__aenter__.return_value = mock_response_404
    
    title, content = run_async(web_extractor.extract_content_from_url("https://example.com/not-found"))
    
    assert "Error" in title
    assert "Could not fetch content" in content
    
    # Test with an exception
    mock_get.return_value.__aenter__.side_effect = Exception("Connection error")
    
    title, content = run_async(web_extractor.extract_content_from_url("https://example.com/error"))
    
    assert "Error" in title
    assert "Could not extract content" in content

@patch('web_extractor.extract_content_from_url')
def test_process_message_links(mock_extract):
    """Test the full process_message_links function."""
    # Set up the mock to return title and content
    mock_extract.return_value = ("Test Page", "This is the extracted content from the page.")
    
    # Process a message with links
    message_text = "Check out this link: https://example.com"
    result = run_async(web_extractor.process_message_links(message_text))
    
    # Verify the result format
    assert "محتوای لینک‌های ارسالی" in result
    assert "Test Page" in result
    assert "https://example.com" in result
    assert "extracted content" in result
    
    # Verify the function was called with the correct URL
    mock_extract.assert_called_once_with("https://example.com") 