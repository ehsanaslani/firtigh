import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional
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
        # Get the webpage
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise exception for 4XX/5XX status codes
        
        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
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

async def process_message_links(message_text: str) -> Optional[str]:
    """
    Process links in a message and extract their content.
    
    Args:
        message_text: The message text containing URLs
    
    Returns:
        Extracted content from the links, or None if no valid links found
    """
    urls = extract_urls(message_text)
    
    if not urls:
        return None
    
    # Process up to 2 URLs to avoid overloading the context
    valid_urls = [url for url in urls[:2] if is_valid_url(url)]
    
    if not valid_urls:
        return None
    
    extracted_content = []
    
    for url in valid_urls:
        title, content = await extract_content_from_url(url)
        if content and content != "Error":
            extracted_content.append(f"Content from [{title}]({url}):\n\n{content}\n\n")
    
    if extracted_content:
        result = "📄 *محتوای لینک‌های ارسال شده:*\n\n" + "".join(extracted_content)
        return result
    
    return None 