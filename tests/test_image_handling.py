import os
import sys
import pytest
import base64
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot

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

@patch('bot.download_telegram_file')
def test_message_with_image(mock_download, mock_update, mock_context):
    """Test that images are properly detected and stored."""
    # Set up a mock image in the message
    mock_photo = MagicMock()
    mock_photo.file_id = "test_file_id"
    mock_update.message.photo = [mock_photo]  # Telegram sends multiple sizes, we use the list format
    
    # Set up the download mock to return base64 data
    mock_download.return_value = "base64_image_data"
    
    # Call the extract_media_info function
    media_type, media_description, media_data = run_async(
        bot.extract_media_info(mock_update.message, mock_context)
    )
    
    # Verify the function correctly identified and processed the image
    assert media_type == "photo"
    assert media_description == "[تصویر]"
    assert media_data == "base64_image_data"
    mock_download.assert_called_once_with("test_file_id", mock_context)

@patch('bot.download_telegram_file')
def test_context_includes_image_references(mock_download, mock_update, mock_context):
    """Test that the context sent to the AI includes image information."""
    # Set up a reply chain with images
    replied_to_message = MagicMock()
    replied_to_message.text = "Test reply message"
    replied_to_message.photo = [MagicMock()]
    replied_to_message.photo[0].file_id = "reply_image_id"
    replied_to_message.animation = None
    replied_to_message.sticker = None
    replied_to_message.document = None
    
    # Important: Mock doesn't have reply_to_message by default
    replied_to_message.reply_to_message = None
    
    # Set up the from_user for the replied message
    replied_to_message.from_user = MagicMock()
    replied_to_message.from_user.username = "test_replier"
    
    # Set up the current message
    mock_update.message.reply_to_message = replied_to_message
    
    # Set up the download mock to return base64 data
    mock_download.return_value = "test_image_data"
    
    # Call the get_conversation_context function
    context_text, media_data_list = run_async(
        bot.get_conversation_context(mock_update, mock_context)
    )
    
    # Verify the context includes the image
    assert "[تصویر]" in context_text
    assert "test_replier" in context_text
    
    # Verify the media data list includes at least one image with our test data
    assert len(media_data_list) > 0
    
    # Find our specific image in the list
    found_image = False
    for item in media_data_list:
        if (item["type"] == "photo" and 
            item["data"] == "test_image_data" and 
            "@test_replier" in item["sender"]):
            found_image = True
            break
    
    assert found_image, "Image with expected data not found in media_data_list" 