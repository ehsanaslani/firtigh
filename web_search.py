"""
Web search functionality for the bot using various search APIs.
Supports searching with Serper, SerpAPI, or a fallback method if neither is available.
"""

import os
import json
import logging
import aiohttp
import asyncio
import time
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Load API keys from environment variables
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")

async def search_web(query: str, is_news: bool = False, max_results: int = 5) -> Dict[str, Any]:
    """
    Search the web using available search APIs.
    
    Args:
        query: The search query
        is_news: Whether to search for news specifically
        max_results: Maximum number of results to return
        
    Returns:
        Dict containing search results formatted for display
    """
    logger.info(f"Searching web for: '{query}', is_news={is_news}")
    
    # Try different search methods in order of preference
    search_methods = [
        search_with_serper,
        search_with_serpapi,
        search_with_google_cse,
        basic_search_fallback
    ]
    
    for search_method in search_methods:
        try:
            results = await search_method(query, is_news, max_results)
            if results and results.get("results"):
                logger.info(f"Search successful using {search_method.__name__}")
                return results
        except Exception as e:
            logger.error(f"Error with {search_method.__name__}: {e}")
    
    # If all methods fail, return a minimal result set
    logger.warning("All search methods failed, returning minimal results")
    return {
        "query": query,
        "results": [
            {
                "title": "جستجو موفقیت‌آمیز نبود",
                "snippet": "متأسفانه نتوانستم نتایج جستجو را دریافت کنم. ممکن است مشکلی در اتصال به سرویس‌های جستجو وجود داشته باشد.",
                "link": ""
            }
        ],
        "message": "متأسفانه جستجو با مشکل مواجه شد. ممکن است مشکلی در اتصال به سرویس‌های جستجو وجود داشته باشد."
    }

async def search_with_serper(query: str, is_news: bool = False, max_results: int = 5) -> Dict[str, Any]:
    """Search the web using Serper.dev API"""
    if not SERPER_API_KEY:
        logger.warning("No SERPER_API_KEY found in environment variables")
        raise ValueError("SERPER_API_KEY not configured")
    
    search_type = "news" if is_news else "search"
    url = f"https://google.serper.dev/search"
    
    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": query,
        "gl": "ir",
        "hl": "fa",
        "num": max_results
    }
    
    if is_news:
        payload["type"] = "news"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=20) as response:
            if response.status != 200:
                logger.error(f"Serper API error: {response.status}")
                raise Exception(f"Serper API error: {response.status}")
            
            data = await response.json()
            
            # Format results
            formatted_results = []
            
            # Process organic results
            if "organic" in data:
                for item in data["organic"][:max_results]:
                    formatted_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", "")
                    })
            
            # Process news results if searching for news
            elif "news" in data:
                for item in data["news"][:max_results]:
                    formatted_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", ""),
                        "date": item.get("date", ""),
                        "source": item.get("source", "")
                    })
            
            return {
                "query": query,
                "results": formatted_results,
                "message": format_search_message(query, formatted_results, is_news)
            }

async def search_with_serpapi(query: str, is_news: bool = False, max_results: int = 5) -> Dict[str, Any]:
    """Search the web using SerpAPI"""
    if not SERPAPI_API_KEY:
        logger.warning("No SERPAPI_API_KEY found in environment variables")
        raise ValueError("SERPAPI_API_KEY not configured")
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "hl": "fa",
        "gl": "ir",
        "num": max_results
    }
    
    if is_news:
        params["tbm"] = "nws"
    
    url = "https://serpapi.com/search"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=20) as response:
            if response.status != 200:
                logger.error(f"SerpAPI error: {response.status}")
                raise Exception(f"SerpAPI error: {response.status}")
            
            data = await response.json()
            
            # Format results
            formatted_results = []
            
            # Process organic results
            if "organic_results" in data:
                for item in data["organic_results"][:max_results]:
                    formatted_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", "")
                    })
            
            # Process news results if searching for news
            elif "news_results" in data:
                for item in data["news_results"][:max_results]:
                    formatted_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", ""),
                        "date": item.get("date", ""),
                        "source": item.get("source", "")
                    })
            
            return {
                "query": query,
                "results": formatted_results,
                "message": format_search_message(query, formatted_results, is_news)
            }

async def search_with_google_cse(query: str, is_news: bool = False, max_results: int = 5) -> Dict[str, Any]:
    """Search the web using Google Custom Search Engine"""
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.warning("No GOOGLE_API_KEY or GOOGLE_CSE_ID found in environment variables")
        raise ValueError("Google CSE not configured")
    
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "hl": "fa",
        "gl": "ir",
        "num": max_results
    }
    
    if is_news:
        params["searchType"] = "news"
    
    url = "https://www.googleapis.com/customsearch/v1"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=20) as response:
            if response.status != 200:
                logger.error(f"Google CSE error: {response.status}")
                raise Exception(f"Google CSE error: {response.status}")
            
            data = await response.json()
            
            # Format results
            formatted_results = []
            
            if "items" in data:
                for item in data["items"][:max_results]:
                    result = {
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "link": item.get("link", "")
                    }
                    
                    # Try to get date for news results
                    if is_news and "pagemap" in item and "newsarticle" in item["pagemap"]:
                        news_article = item["pagemap"]["newsarticle"][0]
                        if "datepublished" in news_article:
                            result["date"] = news_article["datepublished"]
                        if "source" in news_article:
                            result["source"] = news_article["source"]
                    
                    formatted_results.append(result)
            
            return {
                "query": query,
                "results": formatted_results,
                "message": format_search_message(query, formatted_results, is_news)
            }

async def basic_search_fallback(query: str, is_news: bool = False, max_results: int = 5) -> Dict[str, Any]:
    """
    Fallback search method that returns manually formatted results.
    This is used when no API keys are available or all other methods fail.
    """
    logger.warning("Using basic fallback search - this returns minimal fake results")
    
    # Create a fallback dummy result
    results = [
        {
            "title": "جستجو با خطا مواجه شد",
            "snippet": "متأسفانه، در حال حاضر قادر به انجام جستجو نیستم. لطفاً بعداً دوباره امتحان کنید.",
            "link": "https://www.google.com/search?q=" + query.replace(" ", "+")
        }
    ]
    
    return {
        "query": query,
        "results": results,
        "message": "متأسفانه جستجوی اینترنتی در حال حاضر در دسترس نیست. ممکن است کلیدهای API تنظیم نشده باشند."
    }

def format_search_message(query: str, results: List[Dict[str, str]], is_news: bool = False) -> str:
    """
    Format search results into a human-readable message
    
    Args:
        query: Original search query
        results: List of search result items
        is_news: Whether these are news results
        
    Returns:
        Formatted message with search results
    """
    if not results:
        return f"جستجو برای «{query}» نتیجه‌ای نداشت. 😕"
    
    result_type = "اخبار" if is_news else "جستجو"
    message = f"🔍 نتایج {result_type} برای «{query}»:\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "").strip()
        snippet = result.get("snippet", "").strip()
        link = result.get("link", "").strip()
        
        # Add additional info for news results
        if is_news:
            date = result.get("date", "").strip()
            source = result.get("source", "").strip()
            
            if date and source:
                message += f"**{i}. {title}**\n{snippet}\n🗞️ {source} | 📅 {date}\n🔗 {link}\n\n"
            elif source:
                message += f"**{i}. {title}**\n{snippet}\n🗞️ {source}\n🔗 {link}\n\n"
            else:
                message += f"**{i}. {title}**\n{snippet}\n🔗 {link}\n\n"
        else:
            message += f"**{i}. {title}**\n{snippet}\n🔗 {link}\n\n"
    
    return message