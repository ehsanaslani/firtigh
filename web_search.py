import os
import json
import logging
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
import usage_limits

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Google Custom Search API credentials
SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Persian news sources to prioritize
PERSIAN_NEWS_SOURCES = [
    "bbc.com/persian",
    "bbcpersian.com",
    "euronews.com/persian",
    "iranintl.com",
    "radiofarda.com",
    "dw.com/fa-ir",
    "irna.ir",
    "isna.ir",
    "mehrnews.com",
    "khabaronline.ir",
    "farsnews.ir"
]

async def is_news_query(query: str) -> bool:
    """
    Check if a query is related to news.
    
    Args:
        query: The search query
        
    Returns:
        True if it's a news query, False otherwise
    """
    news_indicators = [
        "اخبار", "news", "خبر", "رویداد", "حوادث", "رسانه", "media",
        "headlines", "تیتر", "گزارش", "report", "روزنامه", "newspaper",
        "اتفاقات", "events", "تازه‌ترین", "latest", "جدیدترین"
    ]
    
    query_lower = query.lower()
    return any(indicator in query_lower for indicator in news_indicators)

async def search_web(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using Google Custom Search API.
    
    Args:
        query: The search query
        num_results: Number of results to return (max 10)
    
    Returns:
        List of search results with title, link, and snippet
    """
    # Check if we've reached the daily search limit
    if not usage_limits.can_use_search():
        logger.warning("Daily search limit reached, returning error message")
        return [{"title": "Search Limit Reached", 
                 "link": "", 
                 "snippet": "روزانه فقط تعداد محدودی جستجو امکان‌پذیر است. لطفا فردا دوباره امتحان کنید. 🔍"}]
                 
    if not SEARCH_ENGINE_ID or not GOOGLE_API_KEY:
        logger.error("Google Search API credentials not configured")
        return [{"title": "Search Error", 
                 "link": "", 
                 "snippet": "Web search is not configured. Please set GOOGLE_SEARCH_ENGINE_ID and GOOGLE_API_KEY environment variables."}]
    
    try:
        # Cap num_results to 10 (Google CSE API limit per request)
        num_results = min(num_results, 10)
        
        # Build request URL
        url = f"https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": SEARCH_ENGINE_ID,
            "q": query,
            "num": num_results
        }
        
        # For news queries, prioritize Persian news sources
        is_news = await is_news_query(query)
        if is_news:
            logger.info(f"Detected news query: {query}, prioritizing Persian news sources")
            # Add Persian news sites to the query for news-related searches
            # This creates a biased query that will prioritize these sites
            persian_sites_query = " OR ".join([f"site:{site}" for site in PERSIAN_NEWS_SOURCES[:5]])
            params["q"] = f"({query}) ({persian_sites_query})"
        
        # Make the request
        response = requests.get(url, params=params)
        results = response.json()
        
        # Extract and format the results
        formatted_results = []
        if "items" in results:
            for item in results["items"]:
                formatted_results.append({
                    "title": item.get("title", "No title"),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", "No description")
                })
        
        # For news queries with no results, try again without Persian site restrictions
        if is_news and not formatted_results:
            logger.info("No results from Persian news sources, trying general search")
            params["q"] = query
            response = requests.get(url, params=params)
            results = response.json()
            
            if "items" in results:
                for item in results["items"]:
                    formatted_results.append({
                        "title": item.get("title", "No title"),
                        "link": item.get("link", ""),
                        "snippet": item.get("snippet", "No description")
                    })
        
        # Increment search usage count
        usage_limits.increment_search_usage()
        
        return formatted_results
    except Exception as e:
        logger.error(f"Error searching the web: {e}")
        return [{"title": "Search Error", 
                 "link": "", 
                 "snippet": f"An error occurred during web search: {str(e)}"}]

def format_search_results(results: List[Dict[str, str]], is_news: bool = False) -> str:
    """
    Format search results into a readable string.
    
    Args:
        results: List of search results
        is_news: Whether the results are for a news query
        
    Returns:
        Formatted string of search results
    """
    if not results:
        return "جستجو نتیجه‌ای نداشت. 🔍"
    
    if is_news:
        formatted_text = "📰 *آخرین اخبار*:\n\n"
    else:
        formatted_text = "🔍 *نتایج جستجو*:\n\n"
    
    for i, result in enumerate(results, 1):
        formatted_text += f"{i}. *{result['title']}*\n"
        formatted_text += f"   {result['link']}\n"
        formatted_text += f"   {result['snippet']}\n\n"
    
    if is_news:
        formatted_text += "🔍 *توجه*: نتایج از منابع خبری فارسی‌زبان استخراج شده است."
    
    return formatted_text

async def is_search_request(text: str) -> bool:
    """
    Check if a message is asking for a web search.
    
    Args:
        text: The message text
    
    Returns:
        True if it's a search request, False otherwise
    """
    search_keywords = [
        "جستجو", "search", "بگرد", "پیدا کن", "اینترنت", "internet", 
        "سرچ", "گوگل", "google", "اخبار", "news", "find", "lookup"
    ]
    
    question_indicators = ["?", "چیست", "چیه", "کیه", "کجاست", "چطور", "چگونه", "آیا"]
    
    text_lower = text.lower()
    
    # Check for explicit search commands
    has_search_keyword = any(keyword in text_lower for keyword in search_keywords)
    
    # Check if it seems like a question that might need real-time info
    has_question = any(indicator in text_lower for indicator in question_indicators)
    
    # If text contains both a search keyword and a question indicator, it's a search request
    return has_search_keyword and has_question 