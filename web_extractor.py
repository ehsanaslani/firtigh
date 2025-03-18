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
import scrapy
from scrapy.crawler import CrawlerRunner
from scrapy.http import Request
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from scrapy import signals
from crochet import setup, wait_for
import os
from playwright import async_playwright
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

# Initialize crochet for running Scrapy with asyncio
setup()

class ContentExtractorSpider(scrapy.Spider):
    """Spider to extract content from a URL."""
    name = 'content_extractor'
    
    def __init__(self, url=None, max_length=10000, *args, **kwargs):
        super(ContentExtractorSpider, self).__init__(*args, **kwargs)
        self.start_urls = [url] if url else []
        self.max_length = max_length
        self.extracted_content = None
        self.extracted_title = None
        
    def start_requests(self):
        for url in self.start_urls:
            yield Request(url=url, headers=DEFAULT_HEADERS, callback=self.parse)
            
    def parse(self, response):
        # Extract title
        self.extracted_title = response.css('title::text').get() or "No Title"
        
        # Try to find main content
        # First look for common content containers
        main_content = None
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
            content = response.css(selector)
            if content:
                # Use the first match for simplicity
                main_content = content.get()
                break
                
        # If no content container found, use the body
        if not main_content:
            main_content = response.css('body').get()
            
        # Remove scripts, styles, and other non-content elements
        if main_content:
            # Use a simple regex-based approach to clean HTML
            import re
            main_content = re.sub(r'<script.*?</script>', '', main_content, flags=re.DOTALL)
            main_content = re.sub(r'<style.*?</style>', '', main_content, flags=re.DOTALL)
            main_content = re.sub(r'<nav.*?</nav>', '', main_content, flags=re.DOTALL)
            main_content = re.sub(r'<footer.*?</footer>', '', main_content, flags=re.DOTALL)
            main_content = re.sub(r'<header.*?</header>', '', main_content, flags=re.DOTALL)
            
            # Extract text from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(main_content, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up text
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)
            
            # Truncate if too long
            if len(text) > self.max_length:
                text = text[:self.max_length] + "..."
                
            self.extracted_content = text


@wait_for(timeout=30)
def run_spider(url, max_length=10000):
    """Run the spider and return results."""
    results = {}
    
    def crawler_results(signal, sender, item, response, spider):
        nonlocal results
        results['title'] = spider.extracted_title
        results['content'] = spider.extracted_content
        
    runner = CrawlerRunner()
    crawler = runner.create_crawler(ContentExtractorSpider)
    crawler.signals.connect(crawler_results, signal=signals.item_scraped)
    
    deferred = crawler.crawl(ContentExtractorSpider, url=url, max_length=max_length)
    
    # We return the deferred and crochet waits for it to fire
    return deferred.addCallback(lambda _: results)


async def check_memory_usage():
    """Monitor memory usage and force garbage collection if needed"""
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss / 1024 / 1024  # Convert to MB
    if memory_usage > 450:  # Heroku's free tier has 512MB limit
        gc.collect()
        logger.warning(f"High memory usage detected: {memory_usage}MB - Garbage collection triggered")

async def extract_content_from_url(url: str, max_length: int = 10000) -> Optional[str]:
    await check_memory_usage()
    """
    Extract and summarize content from a URL using Scrapy.
    
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
    
    # Try the Scrapy extraction method
    try:
        # Determine content type first to handle special cases
        try:
            content_type = await asyncio.wait_for(determine_content_type(url), timeout=10.0)
            logger.info(f"Content type for {url}: {content_type}")
            
            # Handle special content types
            if content_type in ["pdf", "doc", "docx"]:
                return f"این پیوند حاوی یک فایل {content_type} است. در حال حاضر امکان استخراج محتوا از این نوع فایل وجود ندارد."
                
            elif content_type == "json":
                # For JSON, use the existing extract_json_content function
                content = await asyncio.wait_for(extract_json_content(url), timeout=10.0)
                if content:
                    return content
        except Exception as e:
            logger.error(f"Error determining content type: {e}", exc_info=True)
            # Continue with HTML extraction
        
        # For HTML and other text content, use Scrapy
        try:
            # Use crochet to run Scrapy from asyncio
            results = run_spider(url, max_length)
            
            if results and results.get('content'):
                title = results.get('title', 'No Title')
                content = results.get('content')
                return f"عنوان: {title}\n\n{content}"
            else:
                logger.warning(f"Scrapy extraction returned empty results for {url}")
                
        except Exception as e:
            logger.error(f"Error in Scrapy extraction: {e}", exc_info=True)
            
        # If we get here, try the fallback method
        logger.warning(f"Scrapy extraction failed for {url}, trying fallback method")
        
    except Exception as e:
        logger.error(f"Error in extraction process: {e}", exc_info=True)
    
    # Fallback to the original method if Scrapy fails
    try:
        logger.info(f"Using fallback extraction method for {url}")
        async with async_playwright() as p:
            # Configure Chrome for Heroku environment
            chrome_executable_path = os.getenv('GOOGLE_CHROME_BIN', None)
            browser_args = []
            
            if chrome_executable_path:  # We're on Heroku
                browser_args = [
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-setuid-sandbox',
                ]
            
            # Launch browser with appropriate configuration
            browser = await p.chromium.launch(
                headless=True,
                executable_path=chrome_executable_path,
                args=browser_args
            )
            
            page = await browser.new_page()
            await page.goto(url)
            
            # Try to get the content as text
            html = await page.content()
            
            # Use a very simple extraction approach
            soup = BeautifulSoup(html, 'html.parser')
            
            # Get the title
            title = soup.title.text.strip() if soup.title else "No Title"
            
            # Remove scripts, styles, and other non-content elements
            for tag in soup(['script', 'style', 'meta', 'link', 'noscript', 'iframe']):
                tag.decompose()
            
            # Get all text
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up the text
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)
            
            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return f"عنوان: {title}\n\n{text}"
            
    except Exception as e:
        logger.error(f"Fallback extraction failed: {e}", exc_info=True)
        if os.getenv('HEROKU_APP_NAME'):
            sentry_sdk.capture_exception(e)
        return f"خطا: مشکلی در استخراج محتوا رخ داد. لطفاً بعداً دوباره تلاش کنید."

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
    
    # Trim leading/trailing whitespace
    text = text.strip()
    
    return text

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