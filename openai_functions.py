import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import database
import web_search
import web_extractor
import config
from datetime import datetime, timedelta
import aiohttp
from information_services import WeatherService
import os

# Set up logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client with version compatibility
try:
    # First try to detect which version is installed
    import openai
    
    # Check if this is the newer OpenAI client (1.0.0+)
    if hasattr(openai, "OpenAI"):
        from openai import OpenAI
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        is_new_openai = True
        logger.info("Using OpenAI API v1.0.0+ client")
    else:
        # This is the older OpenAI client (pre-1.0.0)
        openai.api_key = config.OPENAI_API_KEY
        openai_client = openai
        is_new_openai = False
        logger.info("Using OpenAI API legacy client (pre-1.0.0)")
except ImportError as e:
    logger.error(f"Error importing OpenAI: {str(e)}")
    # Fallback to older client as a last resort
    import openai
    openai.api_key = config.OPENAI_API_KEY
    openai_client = openai
    is_new_openai = False
    logger.info("Failed to import newer OpenAI client, falling back to legacy client")

def get_openai_function_definitions() -> List[Dict[str, Any]]:
    """
    Get the list of function definitions to be used with OpenAI API.
    """
    return [
        {
            "name": "search_web",
            "description": "Search the web for information or news",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "is_news": {
                        "type": "boolean",
                        "description": "Whether to search for news or general information"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "extract_content_from_url",
            "description": "Extract content from a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to extract content from"
                    }
                },
                "required": ["url"]
            }
        },
        {
            "name": "get_chat_history",
            "description": "Retrieve and summarize recent chat history",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history to retrieve (1-7)"
                    },
                    "chat_id": {
                        "type": "integer",
                        "description": "The chat ID to get history for"
                    }
                },
                "required": ["days", "chat_id"]
            }
        },
        {
            "name": "get_weather",
            "description": "Get current weather information for a specific city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city to get weather for, e.g. 'Tehran', 'Shiraz'"
                    },
                    "units": {
                        "type": "string",
                        "enum": ["metric", "imperial"],
                        "description": "The unit system to use for temperature (metric: Celsius, imperial: Fahrenheit)",
                        "default": "metric"
                    }
                },
                "required": ["city"]
            }
        },
        {
            "name": "get_top_news",
            "description": "Retrieve top news from Persian and international news sources",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["general", "politics", "business", "technology", "entertainment", "sports", "science", "health"],
                        "description": "The category of news to retrieve"
                    },
                    "persian_only": {
                        "type": "boolean",
                        "description": "Whether to retrieve only Persian news or include international news as well"
                    }
                }
            }
        },
        {
            "name": "get_trending_hashtags",
            "description": "Retrieve trending hashtags and topics from X (Twitter)",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["worldwide", "iran"],
                        "description": "The region to get trends for (default: worldwide)",
                        "default": "worldwide"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of trending hashtags to retrieve (1-30)",
                        "default": 20
                    }
                }
            }
        }
    ]

# Function implementations
async def search_web(query: str, is_news: bool = False) -> Dict[str, Any]:
    """
    Search the web for information using the specified query.
    
    Args:
        query: The search query
        is_news: Whether to search for news
        
    Returns:
        A dictionary with search results
    """
    try:
        logger.info(f"Searching web for: {query} (is_news={is_news})")
        
        # Call the web search function (using your web_search implementation)
        # Make sure web_search is properly imported and initialized
        if not hasattr(web_search, "search_web"):
            # Fallback if web_search module is not properly set up
            raise ImportError("Web search module not properly configured")
            
        search_results = await web_search.search_web(query, is_news)
        
        # Format and extract relevant information
        results = []
        
        if not search_results or not isinstance(search_results, list):
            # Handle empty or invalid results
            return {
                "results": [],
                "query": query,
                "is_news": is_news,
                "formatted_message": f"برای جستجوی '{query}' نتیجه‌ای یافت نشد."
            }
        
        # Process the results
        for result in search_results[:5]:  # Limit to top 5 results
            if isinstance(result, dict):
                results.append({
                    "title": result.get("title", "بدون عنوان"),
                    "snippet": result.get("snippet", "توضیحات در دسترس نیست."),
                    "url": result.get("link", "")
                })
            else:
                # Skip non-dictionary results
                continue
        
        # Create a formatted message for display
        formatted_message = f"🔍 **نتایج جستجو برای: {query}**\n\n"
        
        if not results:
            formatted_message += "متأسفانه نتیجه‌ای یافت نشد."
        else:
            for i, result in enumerate(results, 1):
                formatted_message += f"{i}. **{result['title']}**\n"
                formatted_message += f"{result['snippet']}\n"
                formatted_message += f"🔗 {result['url']}\n\n"
        
        return {
            "results": results,
            "query": query,
            "is_news": is_news,
            "formatted_message": formatted_message
        }
        
    except ImportError as ie:
        logger.error(f"Import error in search_web: {ie}")
        return {
            "error": "جستجوی وب پیکربندی نشده است.",
            "query": query,
            "is_news": is_news,
            "results": [],
            "formatted_message": "متأسفانه در حال حاضر امکان جستجوی وب فراهم نیست. لطفاً با پشتیبانی تماس بگیرید."
        }
    except Exception as e:
        logger.error(f"Error in search_web: {e}", exc_info=True)
        return {
            "error": str(e),
            "query": query,
            "is_news": is_news,
            "results": [],
            "formatted_message": f"متأسفانه در جستجوی وب برای '{query}' مشکلی پیش آمد: {str(e)}"
        }

async def extract_content_from_url(url: str) -> Dict[str, Any]:
    """
    Extract content from a URL.
    
    Args:
        url: The URL to extract content from
        
    Returns:
        A dictionary with the extracted content
    """
    try:
        # Log the extraction request
        logger.info(f"Extracting content from URL: {url}")
        
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            return {
                "error": "URL format invalid",
                "url": url,
                "formatted_message": f"فرمت آدرس وب نامعتبر است. لطفاً آدرس را با http:// یا https:// شروع کنید."
            }
        
        # Check if web_extractor is properly configured
        if not hasattr(web_extractor, "extract_content_from_url"):
            raise ImportError("Web extraction module not properly configured")
        
        # Extract content from the URL
        title, content = await web_extractor.extract_content_from_url(url)
        
        if title == "Error" or not content:
            return {
                "error": "Failed to extract content",
                "url": url,
                "formatted_message": f"نمی‌توانم محتوا را از این آدرس استخراج کنم: {url}\n\n{content}"
            }
        
        # Create a nicely formatted message
        formatted_message = f"📄 **{title}**\n\n"
        
        # Truncate content if it's too long for display
        display_content = content
        if len(content) > 1500:
            display_content = content[:1500] + "...\n\n(محتوا بسیار طولانی است و خلاصه شده است)"
        
        formatted_message += display_content
        formatted_message += f"\n\n🔗 [منبع]({url})"
        
        return {
            "title": title,
            "content": content,
            "url": url,
            "formatted_message": formatted_message
        }
        
    except ImportError as ie:
        logger.error(f"Import error in extract_content_from_url: {ie}")
        return {
            "error": "استخراج محتوا از وب پیکربندی نشده است.",
            "url": url,
            "formatted_message": "متأسفانه در حال حاضر امکان استخراج محتوا از وب فراهم نیست. لطفاً با پشتیبانی تماس بگیرید."
        }
    except Exception as e:
        logger.error(f"Error in extract_content_from_url: {e}", exc_info=True)
        return {
            "error": str(e),
            "url": url,
            "formatted_message": f"متأسفانه در استخراج محتوا از آدرس {url} مشکلی پیش آمد: {str(e)}"
        }

async def get_chat_history(days: int, chat_id: int) -> Dict[str, Any]:
    """
    Retrieve group chat history.
    
    Args:
        days: Number of days of history to retrieve
        chat_id: The ID of the chat to get history for
        
    Returns:
        A dictionary with the chat history
    """
    try:
        # Log the history request
        logger.info(f"Getting chat history for {days} days from chat {chat_id}")
        
        # Clamp days to a reasonable range
        days = max(1, min(30, int(days)))
        
        # Generate chat history summary
        history = await database.get_formatted_message_history(days, chat_id)
        
        return {
            "messages": history,
            "days": days
        }
        
    except Exception as e:
        logger.error(f"Error in get_chat_history: {e}")
        return {
            "error": str(e),
            "summary": "Error retrieving chat history."
        }

async def process_function_calls(response_message, chat_id: Optional[int] = None, user_id: Optional[int] = None) -> str:
    """
    Process function calls from the OpenAI API response.
    Compatible with both newer and older OpenAI API versions.
    
    Args:
        response_message: The response message from the OpenAI API
        chat_id: The chat ID (for context)
        user_id: The user ID (for context)
    
    Returns:
        The processed response as a string
    """
    try:
        message = response_message.choices[0].message
        user_message_content = ""  # Default empty string to prevent null content
        
        # Handle different API versions
        if is_new_openai:
            # Newer OpenAI client (v1.0.0+) uses tool_calls
            has_function_call = hasattr(message, 'tool_calls') and message.tool_calls
            if not has_function_call:
                return message.content or ""
                
            # Process the function call
            tool_call = message.tool_calls[0]
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            tool_call_id = tool_call.id
            
            # Get message content (ensure it's not None)
            user_message_content = message.content or ""
        else:
            # Older OpenAI client uses function_call
            has_function_call = hasattr(message, 'function_call') and message.function_call
            if not has_function_call:
                return message.content or ""
                
            # Process the function call
            function_name = message.function_call.name
            function_args = json.loads(message.function_call.arguments)
            tool_call_id = None  # Not used in the old API
            
            # Get message content (ensure it's not None)
            user_message_content = message.content or ""
        
        if not has_function_call:
            return message.content or ""
        
        # Log the function call
        logger.info(f"Function call: {function_name} with arguments {function_args}")
        
        # Execute the appropriate function
        result = await execute_function(function_name, function_args, chat_id, user_id)
        
        # Get a more concise version of the result for the API call
        api_result = get_api_safe_result(result)
        
        # Prepare formatted message for direct return if API call fails
        formatted_message = result.get("formatted_message", "")
        if not formatted_message and "error" in result:
            formatted_message = f"متأسفانه در پردازش درخواست شما مشکلی پیش آمد: {result['error']}"
        
        # Follow-up with the AI using the function result
        try:
            if is_new_openai:
                # New OpenAI client (v1.0.0+)
                second_response = await openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "user", "content": user_message_content},
                        {"role": "assistant", "content": None, "tool_calls": message.tool_calls},
                        {"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(api_result)}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
                return second_response.choices[0].message.content
            else:
                # Legacy OpenAI client (pre-1.0.0)
                # For older client, we need to ensure all content fields are strings
                second_response = await openai_client.ChatCompletion.acreate(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "user", "content": user_message_content},
                        {"role": "assistant", "content": "", "function_call": {"name": function_name, "arguments": json.dumps(function_args)}},
                        {"role": "function", "name": function_name, "content": json.dumps(api_result)}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
                return second_response.choices[0].message.content
        except Exception as api_error:
            # If the API call fails, return the formatted message directly
            logger.error(f"Error in follow-up API call: {api_error}", exc_info=True)
            if formatted_message:
                return formatted_message
            else:
                return f"اطلاعات درخواستی شما دریافت شد، اما در فرمت‌بندی پاسخ مشکلی پیش آمد.\n\nنتیجه: {json.dumps(api_result, ensure_ascii=False)}"
            
    except Exception as e:
        logger.error(f"Error processing function calls: {e}", exc_info=True)
        return f"متأسفانه در پردازش درخواست شما مشکلی پیش آمد: {str(e)}"

async def execute_function(function_name: str, function_args: dict, chat_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Execute the requested function with provided arguments"""
    try:
        # Log the function execution
        logger.info(f"Executing function: {function_name} with args: {function_args}")
        
        if function_name == "search_web":
            query = function_args.get("query", "")
            if not query:
                return {
                    "error": "نیاز به یک جستجوی معتبر است.",
                    "formatted_message": "برای جستجو در وب، لطفاً یک عبارت جستجو وارد کنید."
                }
            
            is_news = function_args.get("is_news", False)
            result = await search_web(query, is_news)
            
            # Ensure there's a formatted_message
            if "formatted_message" not in result:
                if "error" in result:
                    result["formatted_message"] = f"متأسفانه در جستجوی '{query}' مشکلی پیش آمد: {result['error']}"
                else:
                    result["formatted_message"] = f"نتایج جستجو برای '{query}' دریافت شد، اما نمایش آن با مشکل مواجه شد."
            
            return result
            
        elif function_name == "extract_content_from_url":
            url = function_args.get("url", "")
            if not url:
                return {
                    "error": "نیاز به یک آدرس وب معتبر است.",
                    "formatted_message": "برای استخراج محتوا، لطفاً یک آدرس وب معتبر وارد کنید."
                }
            
            # Clean up the URL if needed
            url = url.strip()
            if not (url.startswith('http://') or url.startswith('https://')):
                url = 'https://' + url
            
            result = await extract_content_from_url(url)
            
            # Ensure there's a formatted_message
            if "formatted_message" not in result:
                if "error" in result:
                    result["formatted_message"] = f"متأسفانه در استخراج محتوا از {url} مشکلی پیش آمد: {result['error']}"
                elif "content" in result:
                    # Create a simple formatted message from the title and content
                    title = result.get("title", "محتوای استخراج شده")
                    content_preview = result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"]
                    result["formatted_message"] = f"**{title}**\n\n{content_preview}\n\n🔗 [مشاهده منبع]({url})"
                else:
                    result["formatted_message"] = f"محتوا از {url} استخراج شد، اما نمایش آن با مشکل مواجه شد."
            
            return result
            
        elif function_name == "get_chat_history":
            days = function_args.get("days", 3)
            chat_id_param = function_args.get("chat_id", chat_id)
            return await get_chat_history(days, chat_id_param)
            
        elif function_name == "get_weather":
            city = function_args.get("city")
            units = function_args.get("units", "metric")
            
            # Initialize the weather service
            weather_service = WeatherService()
            weather_data = await weather_service.get_weather(city, units)
            
            if isinstance(weather_data, dict) and not weather_data.get("success", False):
                return {
                    "error": weather_data.get("error", "خطای نامشخص"),
                    "formatted_message": f"متأسفانه در دریافت اطلاعات آب و هوای {city} مشکلی پیش آمد."
                }
            
            # Format weather response
            temp_unit = "°C" if units == "metric" else "°F"
            wind_unit = "m/s" if units == "metric" else "mph"
            
            return {
                "city": weather_data.get("city", city),
                "country": weather_data.get("country", ""),
                "temperature": weather_data.get("temperature", "N/A"),
                "description": weather_data.get("description", "N/A"),
                "humidity": weather_data.get("humidity", "N/A"),
                "wind_speed": weather_data.get("wind_speed", "N/A"),
                "formatted_message": (
                    f"🌤️ آب و هوای {weather_data.get('city', city)} ({weather_data.get('country', '')}):\n\n"
                    f"🌡️ دما: {weather_data.get('temperature', 'N/A')}{temp_unit}\n"
                    f"📝 وضعیت: {weather_data.get('description', 'N/A')}\n"
                    f"💧 رطوبت: {weather_data.get('humidity', 'N/A')}%\n"
                    f"💨 سرعت باد: {weather_data.get('wind_speed', 'N/A')} {wind_unit}"
                )
            }
            
        elif function_name == "get_top_news":
            category = function_args.get("category", "general")
            persian_only = function_args.get("persian_only", False)
            result = await get_top_news(category, persian_only)
            
            # Format the result
            if "error" in result:
                result["formatted_message"] = f"متأسفانه در دریافت اخبار مشکلی پیش آمد: {result['error']}"
            else:
                # Create a nicely formatted news digest
                persian_category_names = {
                    "general": "عمومی", "politics": "سیاسی", "business": "اقتصادی",
                    "technology": "فناوری", "entertainment": "سرگرمی", "sports": "ورزشی",
                    "science": "علمی", "health": "سلامت"
                }
                
                category_persian = persian_category_names.get(category, "عمومی")
                
                formatted_message = f"📰 **اخبار {category_persian}** (به‌روز شده در {datetime.now().strftime('%H:%M')})\n\n"
                
                # Group news by source without limiting (as requested by user)
                news_by_source = {}
                for article in result["articles"]:
                    source = article["source"]
                    if source not in news_by_source:
                        news_by_source[source] = []
                    news_by_source[source].append(article)
                
                # Format each source's news with complete URLs
                for source, articles in news_by_source.items():
                    formatted_message += f"**{source}**:\n"
                    for article in articles[:2]:  # Still limit to 2 headlines per source for readability
                        title = article["title"]
                        url = article.get("url", "")
                        formatted_message += f"• {title}\n  {url}\n"
                    formatted_message += "\n"
                
                result["formatted_message"] = formatted_message
            
            return result
            
        elif function_name == "get_trending_hashtags":
            region = function_args.get("region", "worldwide")
            count = function_args.get("count", 20)  # Use the requested count without limiting
            result = await get_trending_hashtags(region, count)
            
            # Format the result
            if "error" in result:
                result["formatted_message"] = f"متأسفانه در دریافت هشتگ‌های داغ مشکلی پیش آمد: {result['error']}"
            else:
                # Create a nicely formatted trends digest
                region_persian = {"worldwide": "جهانی", "iran": "ایران"}.get(region, "جهانی")
                
                formatted_message = f"🔥 **هشتگ‌های داغ در ایکس (توییتر) - {region_persian}**\n"
                formatted_message += f"به‌روزرسانی: {datetime.now().strftime('%H:%M')}\n\n"
                
                # Add trending hashtags without limiting
                if result.get("trends"):
                    for i, trend in enumerate(result["trends"][:count], 1):
                        name = trend['name']
                        volume = trend.get('tweet_volume', 'N/A')
                        url = trend.get('url', '')
                        
                        # Format tweet volume in Persian
                        volume_text = "نامشخص" if volume == 'N/A' else f"{volume:,}".replace(',', '،') + " توییت"
                        
                        formatted_message += f"{i}. **{name}** - {volume_text}\n   {url}\n"
                else:
                    formatted_message += "متأسفانه، هشتگی یافت نشد."
                
                result["formatted_message"] = formatted_message
            
            return result
        else:
            return {
                "error": f"Function {function_name} not implemented",
                "formatted_message": "متأسفانه این عملیات در حال حاضر پشتیبانی نمی‌شود."
            }
            
    except Exception as e:
        logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
        return {"error": str(e), "formatted_message": f"خطا در اجرای درخواست: {str(e)}"}

def get_api_safe_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a token-optimized version of the result to send to the OpenAI API.
    Preserves complete information for news and trends but optimizes other data types.
    
    Args:
        result: The full result from the function
        
    Returns:
        An API-ready version with preserved news and trends data
    """
    # For news and trends, we'll keep all the original information as requested
    if "articles" in result or "trends" in result:
        # Keep the original result but ensure the formatted message is included
        if "formatted_message" in result:
            api_result = result.copy()
            api_result["message"] = result["formatted_message"]
            return api_result
        return result
    
    # For other function types, still apply optimizations
    api_result = {}
    
    # Always include the formatted message if available
    if "formatted_message" in result:
        api_result["message"] = result["formatted_message"]
    
    # Include error information if present
    if "error" in result:
        api_result["error"] = result["error"]
        return api_result
    
    # For other types, include basic information but optimize nested structures
    for key, value in result.items():
        if key not in ["formatted_message"]:  # Skip what we've already handled
            if not isinstance(value, (dict, list)):  # Skip complex nested structures unless needed
                api_result[key] = value
    
    return api_result

async def get_top_news(category: str = "general", persian_only: bool = False) -> Dict[str, Any]:
    """
    Retrieve top news from Persian and international news sources.
    
    Args:
        category: The category of news to retrieve (general, politics, business, etc.)
        persian_only: Whether to retrieve only Persian news
        
    Returns:
        A dictionary with the top news articles
    """
    try:
        logger.info(f"Retrieving top news for category: {category}, persian_only: {persian_only}")
        
        # Define Persian news sources with RSS feeds
        persian_sources = [
            {
                "name": "بی‌بی‌سی فارسی",
                "url": "https://www.bbc.com/persian",
                "rss": "https://feeds.bbci.co.uk/persian/rss.xml",
                "category_mapping": {
                    "general": "https://feeds.bbci.co.uk/persian/rss.xml",
                    "politics": "https://feeds.bbci.co.uk/persian/rss.xml",
                    "business": "https://feeds.bbci.co.uk/persian/rss.xml",
                    "technology": "https://feeds.bbci.co.uk/persian/rss.xml",
                    "sports": "https://feeds.bbci.co.uk/persian/rss.xml"
                }
            },
            {
                "name": "یورونیوز فارسی",
                "url": "https://per.euronews.com/",
                "rss": "https://per.euronews.com/rss",
                "category_mapping": {
                    "general": "https://per.euronews.com/rss"
                }
            },
            {
                "name": "دویچه وله فارسی",
                "url": "https://www.dw.com/fa-ir/",
                "rss": "https://rss.dw.com/rdf/rss-per-all",
                "category_mapping": {
                    "general": "https://rss.dw.com/rdf/rss-per-all"
                }
            },
            {
                "name": "همشهری آنلاین",
                "url": "https://www.hamshahrionline.ir/",
                "rss": "https://www.hamshahrionline.ir/rss",
                "category_mapping": {
                    "general": "https://www.hamshahrionline.ir/rss",
                    "politics": "https://www.hamshahrionline.ir/rss/tp/30",
                    "sports": "https://www.hamshahrionline.ir/rss/tp/14"
                }
            },
            {
                "name": "خبرگزاری ایسنا",
                "url": "https://www.isna.ir/",
                "rss": "https://www.isna.ir/rss",
                "category_mapping": {
                    "general": "https://www.isna.ir/rss",
                    "politics": "https://www.isna.ir/rss/tp/3",
                    "sports": "https://www.isna.ir/rss/tp/14"
                }
            },
            {
                "name": "تابناک",
                "url": "https://www.tabnak.ir/",
                "rss": "https://www.tabnak.ir/fa/rss/1",
                "category_mapping": {
                    "general": "https://www.tabnak.ir/fa/rss/1",
                    "politics": "https://www.tabnak.ir/fa/rss/1",
                    "sports": "https://www.tabnak.ir/fa/rss/7"
                }
            },
            {
                "name": "ورزش ۳",
                "url": "https://www.varzesh3.com/",
                "rss": "https://www.varzesh3.com/rss/all",
                "category_mapping": {
                    "general": "https://www.varzesh3.com/rss/all",
                    "sports": "https://www.varzesh3.com/rss/all"
                }
            }
        ]
        
        # Define international news sources
        international_sources = [
            {
                "name": "BBC",
                "url": "https://www.bbc.com/news",
                "rss": "http://feeds.bbci.co.uk/news/rss.xml",
                "category_mapping": {
                    "general": "http://feeds.bbci.co.uk/news/rss.xml",
                    "world": "http://feeds.bbci.co.uk/news/world/rss.xml",
                    "business": "http://feeds.bbci.co.uk/news/business/rss.xml",
                    "technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
                    "entertainment": "http://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
                    "health": "http://feeds.bbci.co.uk/news/health/rss.xml",
                    "science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
                }
            },
            {
                "name": "CNN",
                "url": "https://www.cnn.com/",
                "rss": "http://rss.cnn.com/rss/edition.rss",
                "category_mapping": {
                    "general": "http://rss.cnn.com/rss/edition.rss",
                    "world": "http://rss.cnn.com/rss/edition_world.rss",
                    "technology": "http://rss.cnn.com/rss/edition_technology.rss",
                    "health": "http://rss.cnn.com/rss/edition_health.rss",
                    "entertainment": "http://rss.cnn.com/rss/edition_entertainment.rss",
                    "sports": "http://rss.cnn.com/rss/edition_sport.rss",
                    "business": "http://rss.cnn.com/rss/money_news_international.rss"
                }
            },
            {
                "name": "Reuters",
                "url": "https://www.reuters.com/",
                "rss": "https://www.reutersagency.com/feed/",
                "category_mapping": {
                    "general": "https://www.reutersagency.com/feed/"
                }
            },
            {
                "name": "Associated Press",
                "url": "https://apnews.com/",
                "rss": "https://rsshub.app/apnews/topics/apf-topnews",
                "category_mapping": {
                    "general": "https://rsshub.app/apnews/topics/apf-topnews",
                    "world": "https://rsshub.app/apnews/topics/apf-intlnews",
                    "politics": "https://rsshub.app/apnews/topics/apf-politics",
                    "sports": "https://rsshub.app/apnews/topics/apf-sports",
                    "entertainment": "https://rsshub.app/apnews/topics/apf-entertainment",
                    "business": "https://rsshub.app/apnews/topics/apf-business"
                }
            },
            {
                "name": "Al Jazeera",
                "url": "https://www.aljazeera.com/",
                "rss": "https://www.aljazeera.com/xml/rss/all.xml",
                "category_mapping": {
                    "general": "https://www.aljazeera.com/xml/rss/all.xml"
                }
            }
        ]
        
        # Combine sources based on persian_only flag
        sources = persian_sources + ([] if persian_only else international_sources)
        
        # Fetch news from RSS feeds with timeout and proper error handling
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            tasks = []
            for source in sources:
                # Get the appropriate RSS feed URL for the requested category
                rss_url = source.get("category_mapping", {}).get(category, source.get("rss"))
                if not rss_url:
                    # If no category-specific RSS feed is available, use the general one
                    rss_url = source.get("rss")
                
                # Skip sources without RSS feeds
                if rss_url:
                    tasks.append(fetch_rss_feed(session, source, rss_url))
            
            # Gather all results (continue even if some fail)
            all_news = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results, filtering out exceptions and failed fetches
            flattened_news = []
            successful_sources = []
            failed_sources = []
            
            for i, source_news in enumerate(all_news):
                if isinstance(source_news, Exception):
                    # Log the exception and continue
                    logger.error(f"Error fetching from {sources[i]['name']}: {source_news}")
                    failed_sources.append(sources[i]['name'])
                    continue
                    
                if source_news:
                    flattened_news.extend(source_news)
                    successful_sources.append(sources[i]['name'])
                else:
                    # No news returned, but not an exception
                    failed_sources.append(sources[i]['name'])
        
        # Sort by date (most recent first) and limit to a reasonable number
        if flattened_news:
            # Sort news, handling cases where published_at might be empty
            def get_date_for_sorting(article):
                try:
                    # Try to parse the date if it exists
                    if article.get("published_at"):
                        return article["published_at"]
                    return "9999"  # Default to a far future date if missing
                except:
                    return "9999"
                    
            flattened_news.sort(key=get_date_for_sorting, reverse=True)
            
            # Limit to 30 most recent articles
            flattened_news = flattened_news[:30]
        
        # Format the response
        result = {
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "sources": successful_sources,
            "failed_sources": failed_sources,
            "articles": flattened_news
        }
        
        # Create a human-readable formatted message
        persian_category_names = {
            "general": "عمومی", "politics": "سیاسی", "business": "اقتصادی",
            "technology": "فناوری", "entertainment": "سرگرمی", "sports": "ورزشی",
            "science": "علمی", "health": "سلامت"
        }
        
        category_persian = persian_category_names.get(category, "عمومی")
        
        # Check if we have any results
        if not flattened_news:
            if failed_sources and not successful_sources:
                # All sources failed
                result["formatted_message"] = (
                    f"📰 **اخبار {category_persian}**\n\n"
                    f"متأسفانه در دریافت اخبار از منابع خبری مشکلی پیش آمد. "
                    f"لطفاً کمی بعد دوباره تلاش کنید."
                )
            else:
                # No news found
                result["formatted_message"] = (
                    f"📰 **اخبار {category_persian}**\n\n"
                    f"در حال حاضر خبر مهمی در این دسته‌بندی یافت نشد."
                )
        else:
            # Format successful news results
            formatted_message = f"📰 **اخبار {category_persian}** (به‌روز شده در {datetime.now().strftime('%H:%M')})\n\n"
            
            # Group news by source
            news_by_source = {}
            for article in flattened_news:
                source = article["source"]
                if source not in news_by_source:
                    news_by_source[source] = []
                news_by_source[source].append(article)
            
            # Format each source's news with complete URLs
            for source, articles in news_by_source.items():
                formatted_message += f"**{source}**:\n"
                for article in articles[:2]:  # Limit to 2 headlines per source for readability
                    title = article["title"]
                    url = article.get("url", "")
                    formatted_message += f"• {title}\n  {url}\n"
                formatted_message += "\n"
            
            result["formatted_message"] = formatted_message
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_top_news: {e}", exc_info=True)
        return {
            "error": str(e),
            "category": category,
            "articles": [],
            "formatted_message": f"متأسفانه در دریافت اخبار مشکلی پیش آمد: {str(e)}"
        }

async def fetch_rss_feed(session, source, rss_url):
    """
    Fetch and parse an RSS feed from a news source.
    
    Args:
        session: aiohttp client session
        source: Source information dictionary
        rss_url: URL of the RSS feed
        
    Returns:
        List of news articles
    """
    try:
        # Add user-agent header to mimic a browser and avoid blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
        }
        
        # Increase timeout to 15 seconds for slow RSS feeds
        async with session.get(rss_url, headers=headers, timeout=15) as response:
            if response.status != 200:
                logger.warning(f"Failed to fetch RSS feed from {source['name']}: {response.status}")
                return []
                
            content = await response.text()
            
            # Check if content is valid before parsing
            if not content or len(content) < 50:  # Arbitrary minimum valid XML size
                logger.warning(f"Empty or too small RSS content from {source['name']}")
                return []
                
            return parse_rss_content(content, source)
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching RSS feed from {source['name']}")
        return []
    except aiohttp.ClientError as e:
        logger.error(f"Client error fetching RSS feed from {source['name']}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching RSS feed from {source['name']}: {e}")
        return []

def parse_rss_content(content, source):
    """
    Parse RSS content and extract news articles.
    
    Args:
        content: RSS feed content as string
        source: Source information dictionary
        
    Returns:
        List of news articles
    """
    try:
        import xml.etree.ElementTree as ET
        import re
        from datetime import datetime
        import email.utils
        
        # Try to parse XML - handle potential errors
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error(f"XML parsing error from {source['name']}: {e}")
            # Try to clean content before parsing again
            clean_content = re.sub(r'[^\x20-\x7E\x0A\x0D\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', '', content)
            try:
                root = ET.fromstring(clean_content)
            except ET.ParseError:
                logger.error(f"Failed to parse XML even after cleaning from {source['name']}")
                return []
        
        # Handle different RSS formats
        articles = []
        
        # RSS 2.0 format
        try:
            if root.tag == 'rss':
                channel = root.find('channel')
                if channel is not None:
                    for item in channel.findall('item'):
                        try:
                            title_elem = item.find('title')
                            link_elem = item.find('link')
                            desc_elem = item.find('description')
                            date_elem = item.find('pubDate')
                            
                            if title_elem is not None and title_elem.text:
                                title = title_elem.text.strip()
                                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                                description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""
                                
                                # Clean description (remove HTML tags)
                                if description:
                                    description = re.sub(r'<[^>]+>', '', description)
                                
                                # Parse date
                                published_at = ""
                                if date_elem is not None and date_elem.text:
                                    try:
                                        # Parse RFC 822 date format
                                        parsed_date = email.utils.parsedate_to_datetime(date_elem.text)
                                        published_at = parsed_date.isoformat()
                                    except Exception:
                                        # If parsing fails, keep the original string
                                        published_at = date_elem.text
                                
                                articles.append({
                                    "title": title,
                                    "source": source["name"],
                                    "url": link,
                                    "published_at": published_at,
                                    "summary": description[:200] + "..." if description and len(description) > 200 else description
                                })
                        except Exception as item_error:
                            logger.error(f"Error parsing item from {source['name']}: {item_error}")
                            continue  # Skip this item but continue with others
        except Exception as rss_error:
            logger.error(f"Error parsing RSS format from {source['name']}: {rss_error}")
        
        # Atom format
        try:
            if root.tag.endswith('feed') or 'atom' in root.tag.lower():
                namespaces = {'atom': 'http://www.w3.org/2005/Atom'}
                
                # Try with and without namespace
                entries = root.findall('.//{http://www.w3.org/2005/Atom}entry') or root.findall('.//entry')
                
                for item in entries:
                    try:
                        # Try both with and without namespace
                        title_elem = (
                            item.find('.//{http://www.w3.org/2005/Atom}title') or 
                            item.find('.//title')
                        )
                        link_elem = (
                            item.find('.//{http://www.w3.org/2005/Atom}link') or 
                            item.find('.//link')
                        )
                        content_elem = (
                            item.find('.//{http://www.w3.org/2005/Atom}content') or 
                            item.find('.//content')
                        )
                        summary_elem = (
                            item.find('.//{http://www.w3.org/2005/Atom}summary') or 
                            item.find('.//summary')
                        )
                        date_elem = (
                            item.find('.//{http://www.w3.org/2005/Atom}published') or 
                            item.find('.//{http://www.w3.org/2005/Atom}updated') or
                            item.find('.//published') or
                            item.find('.//updated')
                        )
                        
                        if title_elem is not None:
                            title = title_elem.text.strip() if title_elem.text else ""
                            
                            # Get link from href attribute or text content
                            link = ""
                            if link_elem is not None:
                                link = link_elem.get('href', '') or link_elem.text or ""
                            
                            # Get content or summary
                            description = ""
                            if content_elem is not None and content_elem.text:
                                description = content_elem.text.strip()
                            elif summary_elem is not None and summary_elem.text:
                                description = summary_elem.text.strip()
                            
                            # Clean description (remove HTML tags)
                            if description:
                                description = re.sub(r'<[^>]+>', '', description)
                            
                            # Parse date
                            published_at = ""
                            if date_elem is not None and date_elem.text:
                                try:
                                    # Try ISO format first
                                    parsed_date = datetime.fromisoformat(date_elem.text.replace('Z', '+00:00'))
                                    published_at = parsed_date.isoformat()
                                except Exception:
                                    # If parsing fails, keep the original string
                                    published_at = date_elem.text
                            
                            articles.append({
                                "title": title,
                                "source": source["name"],
                                "url": link,
                                "published_at": published_at,
                                "summary": description[:200] + "..." if description and len(description) > 200 else description
                            })
                    except Exception as item_error:
                        logger.error(f"Error parsing Atom item from {source['name']}: {item_error}")
                        continue  # Skip this item but continue with others
        except Exception as atom_error:
            logger.error(f"Error parsing Atom format from {source['name']}: {atom_error}")
        
        # If we found articles, return them
        if articles:
            return articles
            
        # Fall back to a more generic approach if both formats failed
        try:
            # Look for any elements with 'title' and 'link'
            for item in root.findall('.//*'):
                if item.tag.endswith('item') or item.tag.endswith('entry'):
                    try:
                        # Find child elements with common tags
                        title = None
                        link = None
                        description = None
                        
                        for child in item:
                            if child.tag.endswith('title') and child.text:
                                title = child.text.strip()
                            elif child.tag.endswith('link') and child.text:
                                link = child.text.strip()
                            elif child.tag.endswith('description') and child.text:
                                description = child.text.strip()
                            elif child.tag.endswith('content') and child.text:
                                description = child.text.strip()
                        
                        if title and (link or description):
                            # Clean description (remove HTML tags)
                            if description:
                                description = re.sub(r'<[^>]+>', '', description)
                                
                            articles.append({
                                "title": title,
                                "source": source["name"],
                                "url": link or "",
                                "published_at": "",
                                "summary": description[:200] + "..." if description and len(description) > 200 else (description or "")
                            })
                    except Exception as fallback_error:
                        logger.error(f"Error in fallback parsing from {source['name']}: {fallback_error}")
                        continue
        except Exception as generic_error:
            logger.error(f"Error in generic XML parsing from {source['name']}: {generic_error}")
        
        return articles
        
    except Exception as e:
        logger.error(f"Error parsing RSS content from {source['name']}: {e}", exc_info=True)
        return []

async def get_trending_hashtags(region: str = "worldwide", count: int = 20) -> Dict[str, Any]:
    """
    Retrieve trending hashtags and topics from X (Twitter).
    
    Args:
        region: The region to get trends for (worldwide, iran)
        count: Number of trends to retrieve
        
    Returns:
        A dictionary with trending topics
    """
    try:
        logger.info(f"Retrieving trending hashtags for region: {region}, count: {count}")
        
        # Normalize and validate the count
        count = max(1, min(count, 30))
        
        # Define trending hashtag sources to scrape
        trend_sources = [
            {
                "name": "GetDayTrends",
                "url": "https://getdaytrends.com/" + ("iran/" if region == "iran" else "")
            },
            {
                "name": "Trends24",
                "url": "https://trends24.in/" + ("iran/" if region == "iran" else "")
            },
            {
                "name": "TrendinaliaGlobal",
                "url": "https://www.trendinalia.com/twitter-trending-topics/global/" + ("iran/" if region == "iran" else "global/")
            }
        ]
        
        # Fetch trends data from multiple sources
        async with aiohttp.ClientSession() as session:
            # We'll prioritize GetDayTrends but try multiple sources for redundancy
            for source in trend_sources:
                try:
                    trends_data = await fetch_trending_hashtags(session, source["url"], source["name"])
                    if trends_data and len(trends_data) > 0:
                        # We found good data, no need to check other sources
                        break
                except Exception as e:
                    logger.error(f"Error fetching trends from {source['name']}: {e}")
                    trends_data = []
            
        # Format the response
        result = {
            "region": region,
            "timestamp": datetime.now().isoformat(),
            "trends": trends_data[:count] if trends_data else []
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in get_trending_hashtags: {e}")
        return {
            "error": str(e),
            "region": region,
            "trends": []
        }

async def fetch_trending_hashtags(session, url, source_name):
    """
    Fetch trending hashtags from specified source.
    
    Args:
        session: aiohttp client session
        url: URL to scrape for trends
        source_name: Name of the source for logging
        
    Returns:
        List of trending topics
    """
    try:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}, timeout=10) as response:
            if response.status != 200:
                logger.warning(f"Failed to fetch trends from {source_name}: {response.status}")
                return []
                
            # Parse the HTML content
            from bs4 import BeautifulSoup
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            
            trends = []
            
            # Different parsing logic based on the source
            if source_name == "GetDayTrends":
                # GetDayTrends.com format
                trend_items = soup.select("table.trends-table tr")
                
                for item in trend_items[1:]:  # Skip header row
                    try:
                        rank_elem = item.select_one("td.rank-cell")
                        name_elem = item.select_one("td.trend-cell a.trend-link")
                        volume_elem = item.select_one("td.volume-cell span.volume")
                        
                        if name_elem and name_elem.text:
                            name = name_elem.text.strip()
                            # Extract tweet volume if available
                            tweet_volume = "N/A"
                            if volume_elem:
                                tweet_volume = volume_elem.text.strip().replace(",", "").replace("K", "000").replace("+", "")
                            
                            # Get trend rank
                            rank = rank_elem.text.strip() if rank_elem else "N/A"
                            
                            trends.append({
                                "name": name,
                                "rank": rank,
                                "tweet_volume": tweet_volume,
                                "url": f"https://twitter.com/search?q={name.replace('#', '%23')}"
                            })
                    except Exception as e:
                        logger.error(f"Error parsing trend item from {source_name}: {e}")
                        continue
                        
            elif source_name == "Trends24":
                # Trends24.in format
                trend_items = soup.select("div.trend-card ol.trend-list li")
                
                for i, item in enumerate(trend_items, 1):
                    try:
                        name_elem = item.select_one("a")
                        
                        if name_elem and name_elem.text:
                            name = name_elem.text.strip()
                            
                            trends.append({
                                "name": name,
                                "rank": str(i),
                                "tweet_volume": "N/A",
                                "url": f"https://twitter.com/search?q={name.replace('#', '%23')}"
                            })
                    except Exception as e:
                        logger.error(f"Error parsing trend item from {source_name}: {e}")
                        continue
                        
            elif source_name == "TrendinaliaGlobal":
                # Trendinalia format
                trend_items = soup.select("ul.trends li")
                
                for i, item in enumerate(trend_items, 1):
                    try:
                        name_elem = item.select_one("a")
                        
                        if name_elem and name_elem.text:
                            name = name_elem.text.strip()
                            
                            trends.append({
                                "name": name,
                                "rank": str(i),
                                "tweet_volume": "N/A",
                                "url": f"https://twitter.com/search?q={name.replace('#', '%23')}"
                            })
                    except Exception as e:
                        logger.error(f"Error parsing trend item from {source_name}: {e}")
                        continue
            
            return trends
            
    except Exception as e:
        logger.error(f"Error in fetch_trending_hashtags from {source_name}: {e}")
        return [] 