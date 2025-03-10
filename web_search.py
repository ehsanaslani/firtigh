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

async def search_web(query: str, num_results: int = 20) -> List[Dict[str, str]]:
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
        max_results = num_results
        
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
            
    formatted_text = "🔍 *نتایج جستجو*:\n\n"      
    for i, result in enumerate(results, 1):
            formatted_text += f"{i}. *{result['title']}*\n"
            # Format link as markdown link for clickability
            formatted_text += f"   🔗 [مشاهده لینک]({result['link']})\n"
            formatted_text += f"   {result['snippet']}\n\n"
    
    return formatted_text