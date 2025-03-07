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
        num_results: Number of results to return (max 10 per request)
    
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
        # For news queries, we want more results (up to 15)
        is_news = await is_news_query(query)
        max_results = 15 if is_news else num_results
        
        # Google CSE API has a limit of 10 results per request, so we may need multiple requests
        formatted_results = []
        
        # Number of results to fetch in this iteration
        batch_size = min(10, max_results)
        start_index = 1
        
        while len(formatted_results) < max_results:
            # Build request URL
            url = f"https://www.googleapis.com/customsearch/v1"
            params = {
                "key": GOOGLE_API_KEY,
                "cx": SEARCH_ENGINE_ID,
                "q": query,
                "num": batch_size,
                "start": start_index
            }
            
            # For news queries, prioritize Persian news sources
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
            if "items" in results:
                for item in results["items"]:
                    # Extract source domain from URL
                    source_url = item.get("link", "")
                    try:
                        source = source_url.split("://")[1].split("/")[0]
                    except:
                        source = "unknown source"
                    
                    formatted_results.append({
                        "title": item.get("title", "No title"),
                        "link": source_url,
                        "snippet": item.get("snippet", "No description"),
                        "source": source,
                        "date": item.get("pagemap", {}).get("metatags", [{}])[0].get("og:article:published_time", "")
                    })
            
            # Break the loop if we got fewer results than requested or reached our limit
            if "items" not in results or len(results["items"]) < batch_size or len(formatted_results) >= max_results:
                break
                
            # Update start index for the next page
            start_index += batch_size
        
        # For news queries with no results, try again without Persian site restrictions
        if is_news and not formatted_results:
            logger.info("No results from Persian news sources, trying general search")
            params["q"] = query
            response = requests.get(url, params=params)
            results = response.json()
            
            if "items" in results:
                for item in results["items"]:
                    # Extract source domain from URL
                    source_url = item.get("link", "")
                    try:
                        source = source_url.split("://")[1].split("/")[0]
                    except:
                        source = "unknown source"
                        
                    formatted_results.append({
                        "title": item.get("title", "No title"),
                        "link": source_url,
                        "snippet": item.get("snippet", "No description"),
                        "source": source,
                        "date": item.get("pagemap", {}).get("metatags", [{}])[0].get("og:article:published_time", "")
                    })
        
        # Increment search usage count
        usage_limits.increment_search_usage()
        
        # Limit to max_results
        return formatted_results[:max_results]
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
    
    # Ensure we have at least 5 results but not more than 15 for news
    if is_news:
        min_results = min(5, len(results))
        max_results = min(15, len(results))
        results = results[0:max_results]
        
        formatted_text = f"📰 *آخرین اخبار* ({len(results)} مورد):\n\n"
        
        # News items with better formatting
        for i, result in enumerate(results, 1):
            # Clean up title (remove site name if it appears at the end)
            title = result['title']
            source = result['source']
            if " - " in title and source.lower() in title.lower().split(" - ")[-1]:
                title = " - ".join(title.split(" - ")[:-1])
                
            # Format date if available
            date_str = ""
            if result.get('date'):
                try:
                    from datetime import datetime
                    date_obj = datetime.fromisoformat(result['date'].replace('Z', '+00:00'))
                    date_str = f" ({date_obj.strftime('%Y-%m-%d')})"
                except:
                    pass
            
            # Format link as markdown link for clickability
            link = result['link']
            
            # Line 1: Number and title with date
            formatted_text += f"{i}. *{title}*{date_str}\n"
            
            # Line 2: Source with emoji
            formatted_text += f"   📄 *منبع*: {source}\n"
            
            # Line 3: Snippet
            formatted_text += f"   {result['snippet']}\n"
            
            # Line 4: Link as clickable markdown link
            formatted_text += f"   🔗 [مشاهده خبر کامل]({link})\n\n"
            
    else:
        formatted_text = "🔍 *نتایج جستجو*:\n\n"
        
        for i, result in enumerate(results, 1):
            formatted_text += f"{i}. *{result['title']}*\n"
            # Format link as markdown link for clickability
            formatted_text += f"   🔗 [مشاهده لینک]({result['link']})\n"
            formatted_text += f"   {result['snippet']}\n\n"
    
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