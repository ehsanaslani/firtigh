import re
import logging
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional, Dict, Any
import urllib.parse

logger = logging.getLogger(__name__)

# Regular expression for detecting URLs
URL_PATTERN = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'

def extract_urls(text: str) -> List[str]:
    """
    Extract URLs from text.
    
    Args:
        text: The text to extract URLs from
    
    Returns:
        List of URLs found in the text
    """
    if not text:
        return []
    return re.findall(URL_PATTERN, text)

async def extract_content_from_url(url: str, max_chars: int = 2000) -> Tuple[str, str]:
    """
    Extract content from a URL.
    
    Args:
        url: The URL to extract content from
        max_chars: Maximum number of characters to extract
    
    Returns:
        Tuple of (title, content) from the webpage
    """
    try:
        # Get the webpage using aiohttp
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return f"Error: HTTP {response.status}", f"Could not fetch content from {url}"
                
                html = await response.text()
        
        # Parse the HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Get the title
        title = soup.title.string if soup.title else "No title found"
        
        # Extract the main content (focusing on paragraph tags for simplicity)
        paragraphs = soup.find_all('p')
        content = ""
        
        for p in paragraphs:
            # Skip if paragraph is empty or too short
            text = p.get_text().strip()
            if len(text) < 20:  # Skip very short paragraphs (likely navigation, etc.)
                continue
                
            content += text + "\n\n"
            
            # Stop if we've extracted enough text
            if len(content) >= max_chars:
                content = content[:max_chars] + "..."
                break
        
        if not content:
            # Try extracting from div tags if no good paragraphs were found
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                content = main_content.get_text(strip=True)[:max_chars]
        
        # Cleanup the content (remove excessive whitespace)
        content = re.sub(r'\s+', ' ', content).strip()
        
        return title, content
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {e}")
        return "Error", f"Could not extract content from {url}: {str(e)}"

def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.
    
    Args:
        url: The URL to check
    
    Returns:
        True if valid, False otherwise
    """
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

# The process_message_links function is removed as it's no longer used in the function calling approach 