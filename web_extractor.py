"""
Web content extractor module for the bot.
Extracts content from URLs using different methods based on the content type.
"""

import re
import logging
import aiohttp
import asyncio
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
import ssl
import certifi
import json
from playwright.async_api import async_playwright
import os
import sentry_sdk  # Optional, but recommended for production monitoring
import psutil
import gc

# Initialize error tracking (optional)
if os.getenv('HEROKU_APP_NAME'):  # Only in production
    sentry_sdk.init(
        dsn="your-sentry-dsn",  # If you use Sentry
        traces_sample_rate=1.0,
        environment="production"
    )

# Check if Brotli is available
try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False
    logging.warning("Brotli package not installed. Some websites with Brotli compression may not be accessible.")

# Configure logging
logger = logging.getLogger(__name__)

# Headers to use for requests - mimics a browser
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0"
}

async def extract_content_from_url(url: str, max_length: int = 10000) -> Optional[str]:
    """
    Extract and summarize content from a URL using Playwright.
    
    Args:
        url: The URL to extract content from
        max_length: Maximum length of the content to extract
    
    Returns:
        Extracted content as a string, or None if extraction failed
    """
    logger.info(f"Extracting content from URL: {url}")
    
    # Validate URL format
    if not is_valid_url(url):
        logger.error(f"Invalid URL format: {url}")
        return f"خطا: آدرس اینترنتی نامعتبر است: {url}"
    
    # Clean up the URL if needed
    url = clean_url(url)
    logger.info(f"Cleaned URL: {url}")
    
    try:
        # Try Playwright first for JavaScript-rendered content
        async with async_playwright() as p:
            browser_args = [
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu',
                '--disable-setuid-sandbox',
            ]
            
            browser = await p.chromium.launch(
                headless=True,
                args=browser_args
            )
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent=DEFAULT_HEADERS["User-Agent"]
                )
                page = await context.new_page()
                
                # Navigate to the URL with timeout
                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                except Exception as e:
                    logger.warning(f"Page load timeout or error: {e}")
                    # Continue anyway as the page might have loaded partially
                
                # Get the page title
                title = await page.title()
                
                # Try to find main content
                content = None
                for selector in [
                    'article', 
                    '[class*="content"]',
                    '[class*="post"]',
                    '[class*="article"]',
                    'main',
                    '#content',
                    '.content',
                    '.post',
                    '.article'
                ]:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            # Get text from all matching elements
                            texts = []
                            for element in elements:
                                text = await element.text_content()
                                if text:
                                    texts.append(text.strip())
                            
                            # Use the longest text content
                            if texts:
                                content = max(texts, key=len)
                                break
                    except Exception as e:
                        logger.debug(f"Error with selector {selector}: {e}")
                
                # If no specific content found, get all body text
                if not content:
                    content = await page.evaluate('''
                        () => {
                            // Remove unwanted elements
                            const elementsToRemove = document.querySelectorAll('script, style, nav, footer, header');
                            elementsToRemove.forEach(el => el.remove());
                            
                            // Get all text nodes
                            return document.body.innerText;
                        }
                    ''')
                
                await browser.close()
                
                if content:
                    # Clean up the text
                    content = clean_extracted_text(content)
                    
                    # Truncate if too long
                    if len(content) > max_length:
                        content = content[:max_length] + "..."
                    
                    return f"عنوان: {title}\n\n{content}"
                
            except Exception as e:
                logger.error(f"Error in Playwright extraction: {e}", exc_info=True)
                await browser.close()
                
    except Exception as e:
        logger.error(f"Error setting up Playwright: {e}", exc_info=True)
    
    # Fallback to basic extraction if Playwright fails
    try:
        logger.info(f"Using fallback extraction method for {url}")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=DEFAULT_HEADERS, timeout=20) as response:
                    if response.status != 200:
                        return f"خطا: سرور پاسخ نامعتبر برگرداند (کد وضعیت {response.status})"
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Get the title
                    title = soup.title.text.strip() if soup.title else "No Title"
                    
                    # Remove unwanted elements
                    for element in soup.select('script, style, nav, footer, header'):
                        element.decompose()
                    
                    # Get all text
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Clean up the text
                    text = clean_extracted_text(text)
                    
                    # Truncate if too long
                    if len(text) > max_length:
                        text = text[:max_length] + "..."
                    
                    return f"عنوان: {title}\n\n{text}"
                    
            except Exception as e:
                logger.error(f"Fallback extraction failed: {e}", exc_info=True)
                return f"خطا: نتوانستم محتوای وب‌سایت را استخراج کنم: {str(e)}"
                
    except Exception as e:
        logger.error(f"Fatal error in extraction: {e}", exc_info=True)
        return f"خطا: مشکل جدی در استخراج محتوا: {str(e)}"

def is_valid_url(url: str) -> bool:
    """Check if a URL is valid."""
    if not url:
        return False
        
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def clean_url(url: str) -> str:
    """Clean and normalize the URL."""
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Remove URL fragments
    url = url.split('#')[0]
    
    return url

def clean_extracted_text(text: str) -> str:
    """Clean up extracted text by removing extra whitespace and normalizing line breaks."""
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # Replace multiple spaces with a single space
    text = re.sub(r' +', ' ', text)
    
    # Remove very short lines (likely menu items or buttons)
    lines = [line for line in text.splitlines() if len(line.strip()) > 30]
    
    # Join lines back together
    text = '\n'.join(lines)
    
    # Trim leading/trailing whitespace
    text = text.strip()
    
    return text

async def determine_content_type(url: str) -> str:
    """
    Determine the content type of a URL by making a HEAD request.
    Falls back to guessing from the URL if HEAD request fails.
    """
    # Add retry mechanism for network stability
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    # First try a HEAD request to check the content type
                    async with session.head(url, headers=DEFAULT_HEADERS, timeout=10, allow_redirects=True) as response:
                        content_type = response.headers.get('Content-Type', '').lower()
                        
                        # Parse the content type
                        if 'text/html' in content_type:
                            return "html"
                        elif 'application/json' in content_type:
                            return "json"
                        elif 'application/pdf' in content_type:
                            return "pdf"
                        elif 'application/msword' in content_type or 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' in content_type:
                            return "doc"
                        # Fall through to try more methods
                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    logger.warning(f"HEAD request failed for {url}: {e} (attempt {attempt+1}/{max_retries})")
                    if attempt == max_retries - 1:  # Last attempt
                        # If we couldn't make a HEAD request, try to guess from the URL
                        if url.endswith('.pdf'):
                            return "pdf"
                        elif url.endswith('.json'):
                            return "json"
                        elif url.endswith('.doc') or url.endswith('.docx'):
                            return "doc"
                        else:
                            # Default to HTML for most URLs
                            return "html"
                    else:
                        # Wait before retrying
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
            
            # If we got here without determining the type, default to HTML
            return "html"
            
        except Exception as e:
            logger.error(f"Error determining content type (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                # Wait before retrying
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                # If all retries failed, default to HTML
                return "html"

async def extract_html_content(url: str) -> Optional[str]:
    """
    Extract main content from an HTML page.
    Uses heuristics to identify the main content area.
    """
    # Add retry mechanism for network stability
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(url, headers=DEFAULT_HEADERS, timeout=15) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch HTML content: status {response.status} (attempt {attempt+1}/{max_retries})")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay * (attempt + 1))
                                continue
                            else:
                                return f"خطا: سرور پاسخ نامعتبر برگرداند (کد وضعیت {response.status})"
                        
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remove unwanted elements
                        for element in soup.select('script, style, nav, footer, header, [class*="menu"], [class*="sidebar"], [class*="ad"], [class*="banner"], iframe'):
                            element.decompose()
                        
                        # Extract title
                        title = soup.title.text.strip() if soup.title else "No Title"
                        
                        # Try to find the main content
                        main_content = None
                        
                        # Look for common content containers
                        content_containers = soup.select('article, [class*="content"], [class*="post"], [class*="article"], main, #content, .content, .post, .article')
                        if content_containers:
                            # Use the largest content container by text length
                            main_content = max(content_containers, key=lambda x: len(x.text.strip()))
                        
                        # If no content container found, try to find the largest text block
                        if not main_content or len(main_content.text.strip()) < 100:
                            paragraphs = soup.find_all('p')
                            if paragraphs:
                                # Find the div that contains the most paragraphs
                                paragraph_parents = {}
                                for p in paragraphs:
                                    parent = p.parent
                                    if parent not in paragraph_parents:
                                        paragraph_parents[parent] = 0
                                    paragraph_parents[parent] += 1
                                
                                if paragraph_parents:
                                    main_content = max(paragraph_parents.keys(), key=lambda x: paragraph_parents[x])
                        
                        # If we still don't have main content, use the body
                        if not main_content:
                            main_content = soup.body
                        
                        if not main_content:
                            return f"عنوان: {title}\n\nمتأسفانه نتوانستم محتوای اصلی را از این صفحه استخراج کنم."
                        
                        # Extract text and clean it up
                        content_text = clean_extracted_text(main_content.get_text("\n", strip=True))
                        
                        return f"عنوان: {title}\n\n{content_text}"
                        
                except aiohttp.ClientError as e:
                    # Special handling for Brotli compression errors
                    if 'brotli' in str(e).lower() or 'content-encoding: br' in str(e).lower():
                        if not BROTLI_AVAILABLE:
                            logger.error(f"Brotli compression is used by {url} but Brotli package is not installed")
                            return f"⚠️ نتوانستم محتوای وب‌سایت {url} را استخراج کنم زیرا از فشرده‌سازی Brotli استفاده می‌کند. برای دسترسی به این وب‌سایت، نیاز به نصب کتابخانه Brotli است."
                    logger.error(f"Error fetching URL: {e}")
                    return None
        except Exception as e:
            logger.error(f"Error extracting HTML content: {e}", exc_info=True)
            return None

async def extract_json_content(url: str) -> Optional[str]:
    """Extract and format content from a JSON API response."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=DEFAULT_HEADERS, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch JSON content: {response.status}")
                    return None
                
                json_data = await response.json()
                
                # Format the JSON data as text
                formatted_json = format_json_for_display(json_data)
                
                return f"داده‌های JSON از {url}:\n\n{formatted_json}"
                
    except Exception as e:
        logger.error(f"Error extracting JSON content: {e}", exc_info=True)
        return None

async def extract_generic_content(url: str) -> Optional[str]:
    """Extract content from a generic URL when the content type is unknown."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=DEFAULT_HEADERS, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch generic content: {response.status}")
                    return None
                
                content_type = response.headers.get("Content-Type", "").lower()
                
                if "text/plain" in content_type:
                    text = await response.text()
                    return f"محتوای متنی از {url}:\n\n{text[:5000]}..."
                else:
                    # For binary content, just return a description
                    return f"این پیوند حاوی محتوای قابل استخراج نیست (نوع محتوا: {content_type})."
                
    except Exception as e:
        logger.error(f"Error extracting generic content: {e}", exc_info=True)
        return None

def format_json_for_display(json_data: Any, max_depth: int = 2, current_depth: int = 0) -> str:
    """
    Format JSON data for display in a human-readable way.
    Limits the depth to avoid overly complex output.
    """
    if current_depth > max_depth:
        if isinstance(json_data, (list, dict)):
            return f"[Complex data with {len(json_data)} items]"
        return str(json_data)
    
    if isinstance(json_data, dict):
        result = []
        for key, value in json_data.items():
            formatted_value = format_json_for_display(value, max_depth, current_depth + 1)
            result.append(f"{key}: {formatted_value}")
        return "{\n  " + ",\n  ".join(result) + "\n}"
    
    elif isinstance(json_data, list):
        if len(json_data) > 10:
            # For long lists, show only first few items
            items = [format_json_for_display(item, max_depth, current_depth + 1) for item in json_data[:5]]
            return f"[{', '.join(items)}, ... و {len(json_data) - 5} مورد دیگر]"
        else:
            items = [format_json_for_display(item, max_depth, current_depth + 1) for item in json_data]
            return f"[{', '.join(items)}]"
    
    elif isinstance(json_data, str):
        # For strings, limit length
        if len(json_data) > 100:
            return f'"{json_data[:100]}..."'
        return f'"{json_data}"'
    
    elif json_data is None:
        return "null"
    
    else:
        return str(json_data)

async def check_memory_usage():
    """Monitor memory usage and force garbage collection if needed"""
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
    if memory_usage > 450:  # Heroku's free tier has 512MB limit
        gc.collect()
        logger.warning(f"High memory usage detected: {memory_usage}MB - Garbage collection triggered") 