import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import image_generator

# Mark the class for asyncio tests
class TestImageGenerator:
    """Tests for the image generator module."""
    
    def test_is_image_generation_request(self):
        """Test detection of image generation requests."""
        # Positive cases
        assert image_generator.is_image_generation_request("تصویر بساز از یک گربه")
        assert image_generator.is_image_generation_request("عکس بساز از کوه دماوند")
        assert image_generator.is_image_generation_request("نقاشی کن یک جنگل")
        assert image_generator.is_image_generation_request("generate image of a cat")
        assert image_generator.is_image_generation_request("create a picture of mountains")
        
        # Negative cases
        assert not image_generator.is_image_generation_request("قیمت دلار چنده؟")
        assert not image_generator.is_image_generation_request("آب و هوای تهران")
        assert not image_generator.is_image_generation_request("what's the weather like?")
    
    def test_extract_image_prompt(self):
        """Test extraction of image prompts from messages."""
        # Persian prompts
        assert image_generator.extract_image_prompt("تصویر بساز از یک گربه").strip() == "یک گربه"
        assert image_generator.extract_image_prompt("عکس بساز از کوه دماوند").strip() == "کوه دماوند"
        assert image_generator.extract_image_prompt("نقاشی کن یک جنگل").strip() == "یک جنگل"
        
        # English prompts
        assert image_generator.extract_image_prompt("generate image of a cat").strip() == "of a cat"
        assert image_generator.extract_image_prompt("create a picture of mountains").strip() == "of mountains"
        
        # No prompt
        assert image_generator.extract_image_prompt("تصویر بساز").strip() == ""
        assert image_generator.extract_image_prompt("عکس").strip() == "عکس"
    
    @pytest.mark.asyncio
    async def test_generate_image_success(self):
        """Test successful image generation."""
        with patch('openai.Image.create') as mock_image_create:
            with patch('openai.ChatCompletion.create') as mock_chat_completion:
                # Configure the mocks
                mock_chat_completion.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content="Translated prompt"))]
                )
                
                mock_image_create.return_value = {
                    'data': [{'url': 'https://example.com/image.jpg'}]
                }
                
                # Call the function with English prompt (no translation needed)
                result, error = await image_generator.generate_image("a cat")
                
                # Verify the result
                assert error is None
                assert result == "https://example.com/image.jpg"
                mock_image_create.assert_called_once()
                
                # The translation function shouldn't be called for English
                mock_chat_completion.assert_not_called()
                
                # Reset mocks
                mock_image_create.reset_mock()
                mock_chat_completion.reset_mock()
                
                # Call the function with Persian prompt (translation needed)
                result, error = await image_generator.generate_image("گربه سیاه")
                
                # Verify the result
                assert error is None
                assert result == "https://example.com/image.jpg"
                mock_image_create.assert_called_once()
                
                # The translation function should be called for Persian
                mock_chat_completion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_image_failure(self):
        """Test image generation with an error."""
        with patch('openai.Image.create') as mock_image_create:
            # Configure the mock to raise an exception
            mock_image_create.side_effect = Exception("API error")
            
            # Call the function
            result, error = await image_generator.generate_image("a cat")
            
            # Verify the result
            assert result is None
            assert "خطای غیرمنتظره" in error
            mock_image_create.assert_called_once() 