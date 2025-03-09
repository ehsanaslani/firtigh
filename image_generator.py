import os
import logging
import openai
import anthropic
from anthropic import HUMAN_PROMPT, AI_PROMPT
import requests
import tempfile
import re
from io import BytesIO
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# Initialize the Anthropic client
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def is_image_generation_request(text: str) -> bool:
    """
    Detect if a message is requesting image generation.
    
    Args:
        text (str): The message text to analyze
        
    Returns:
        bool: True if it's an image generation request, False otherwise
    """
    if not text:
        return False
    
    # Keywords that indicate image generation requests in Persian and English
    image_gen_keywords = [
        "تصویر بساز", "عکس بساز", "یک تصویر بساز", "یک عکس بساز", 
        "تصویری بساز", "عکسی بساز", "نقاشی کن", "نقاشی بکش",
        "طراحی کن", "بکش", "رسم کن", "تصویرسازی کن",
        "generate image", "create image", "make image", "draw",
        "generate a picture", "create a picture", "make a picture",
        "create an image of", "generate an image of", "draw a picture of",
        "بساز از", "تصویر بساز از", "عکس بساز از"
    ]
    
    # Check if any of the keywords are present in the text
    for keyword in image_gen_keywords:
        if keyword in text.lower():
            return True
    
    return False

def extract_image_prompt(text: str) -> str:
    """
    Extract the image prompt from the message.
    
    Args:
        text (str): The message text
        
    Returns:
        str: The extracted image prompt
    """
    # Keywords that indicate image generation requests in Persian and English
    keywords = [
        "تصویر بساز", "عکس بساز", "یک تصویر بساز", "یک عکس بساز", 
        "تصویری بساز", "عکسی بساز", "نقاشی کن", "نقاشی بکش",
        "طراحی کن", "بکش", "رسم کن", "تصویرسازی کن",
        "generate image", "create image", "make image", "draw",
        "generate a picture", "create a picture", "make a picture",
        "create an image of", "generate an image of", "draw a picture of",
        "بساز از", "تصویر بساز از", "عکس بساز از"
    ]
    
    # Sort keywords by length (longest first) to avoid shorter keywords
    # stealing parts of longer ones
    keywords.sort(key=len, reverse=True)
    
    # Try to extract the prompt by removing the keyword
    processed_text = text.lower()
    for keyword in keywords:
        if keyword.lower() in processed_text:
            # Remove the keyword, which should leave the description
            prompt = re.sub(r'\b' + re.escape(keyword.lower()) + r'\b', '', processed_text, flags=re.IGNORECASE)
            return prompt.strip()
    
    # If no keyword was found, return the original text
    return text.strip()

async def generate_image(prompt: str, size: str = "1024x1024") -> Tuple[Optional[str], Optional[str]]:
    """
    Generate an image using OpenAI's DALL-E model.
    
    Args:
        prompt (str): The text prompt for image generation
        size (str): The image size (default: 1024x1024)
        
    Returns:
        Tuple[Optional[str], Optional[str]]: A tuple containing:
            - The URL of the generated image if successful, None otherwise
            - An error message if something went wrong, None otherwise
    """
    try:
        # Translate prompt to English if it's in Persian
        if any(c in prompt for c in 'ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىيپچژکگی'):
            # The prompt seems to be in Persian, translate it to English for better results
            system_prompt = "You are a helpful translation assistant."
            
            # Call Claude for translation
            response = claude_client.messages.create(
                model="claude-3-5-haiku-20240307",
                max_tokens=250,
                temperature=0.7,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Translate the following text from Persian to English, focusing on making it a good image generation prompt. Don't add any explanations, just return the English translation:\n\n{prompt}"}
                ]
            )
            
            # Get the translated prompt
            translated_prompt = response.content[0].text.strip()
            logger.info(f"Translated prompt from Persian to English: {prompt} -> {translated_prompt}")
            prompt = translated_prompt
        
        # Generate the image using OpenAI DALL-E
        logger.info(f"Generating image with prompt: {prompt}")
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size=size
        )
        
        image_url = response['data'][0]['url']
        return image_url, None
    
    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return None, f"خطا در ساخت تصویر: {str(e)}"
    
    except Exception as e:
        logger.error(f"Unexpected error generating image: {str(e)}")
        return None, f"خطای غیرمنتظره: {str(e)}" 