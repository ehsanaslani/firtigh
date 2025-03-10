"""
OpenAI function calling support for the bot.
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Determine which version of OpenAI we're using
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    is_new_openai = True
    logger.info("Using OpenAI API v1.0.0+ client")
except ImportError:
    # Fall back to older openai package
    import openai
    openai_client = openai
    openai_client.api_key = os.environ.get("OPENAI_API_KEY")
    is_new_openai = False
    logger.info("Using legacy OpenAI API client")

# Define function schemas for OpenAI function calling
FUNCTION_DEFINITIONS = [
    {
        "name": "search_web",
        "description": "جستجو در وب برای یافتن اطلاعات جدید یا به‌روز. از این تابع برای جستجوی موضوعات، اخبار و هر اطلاعات آنلاین استفاده کنید.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "عبارت جستجو. باید دقیق و مشخص باشد."
                },
                "is_news": {
                    "type": "boolean",
                    "description": "آیا جستجو برای اخبار است؟ اگر کاربر به دنبال خبر است، true بگذارید."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "extract_content_from_url",
        "description": "استخراج متن و اطلاعات از یک آدرس اینترنتی (URL). از این تابع برای خواندن محتوای وب‌سایت‌ها، مقالات، یا هر صفحه اینترنتی استفاده کنید.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "آدرس اینترنتی (URL) صفحه‌ای که باید محتوای آن استخراج شود."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "get_chat_history",
        "description": "دریافت خلاصه تاریخچه گفتگو برای روزهای اخیر. از این تابع زمانی استفاده کنید که کاربر در مورد مکالمات گذشته سوال می‌پرسد.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "تعداد روزهای گذشته برای خلاصه کردن تاریخچه گفتگو."
                },
                "chat_id": {
                    "type": "integer",
                    "description": "شناسه گفتگو برای دریافت تاریخچه."
                }
            },
            "required": ["days"]
        }
    },
    {
        "name": "get_weather",
        "description": "دریافت اطلاعات آب و هوای فعلی برای یک شهر مشخص. از این تابع برای دریافت وضعیت آب و هوا، دما، رطوبت و سرعت باد استفاده کنید.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "نام شهر برای دریافت آب و هوا، مثل 'تهران'، 'شیراز'، 'مشهد'"
                },
                "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "description": "واحد اندازه‌گیری دما (metric: سلسیوس، imperial: فارنهایت)",
                    "default": "metric"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "geocode",
        "description": "جستجوی مکان‌ها با نام یا آدرس و دریافت مختصات جغرافیایی. از این تابع برای پیدا کردن موقعیت جغرافیایی مکان‌ها استفاده کنید.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "نام مکان یا آدرس برای جستجو، مثل 'برج میلاد تهران' یا 'میدان آزادی'"
                },
                "limit": {
                    "type": "integer",
                    "description": "حداکثر تعداد نتایج",
                    "default": 5
                },
                "language": {
                    "type": "string",
                    "description": "زبان ترجیحی برای نتایج (fa: فارسی، en: انگلیسی)",
                    "default": "fa"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "reverse_geocode",
        "description": "تبدیل مختصات جغرافیایی به آدرس. از این تابع برای دریافت آدرس یک موقعیت جغرافیایی با طول و عرض جغرافیایی استفاده کنید.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "عرض جغرافیایی (latitude)"
                },
                "lon": {
                    "type": "number",
                    "description": "طول جغرافیایی (longitude)"
                },
                "language": {
                    "type": "string",
                    "description": "زبان ترجیحی برای نتایج (fa: فارسی، en: انگلیسی)",
                    "default": "fa"
                }
            },
            "required": ["lat", "lon"]
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

def get_openai_function_definitions() -> List[Dict[str, Any]]:
    """
    Get the list of function definitions to be used with OpenAI API.
    """
    return FUNCTION_DEFINITIONS

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
        
        # Dynamically import web_search to avoid circular imports
        try:
            import web_search
            
            # Call the web search function with the query
            search_results = await web_search.search_web(query, is_news)
            
            # Return the results in the expected format
            return search_results
            
        except ImportError:
            logger.error("Failed to import web_search module")
            return {
                "error": "Web search module not available",
                "message": "متأسفانه در حال حاضر امکان جستجوی وب وجود ندارد."
            }
            
    except Exception as e:
        logger.error(f"Error in search_web: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "message": f"خطا در جستجوی '{query}': {str(e)}"
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
        logger.info(f"Extracting content from URL: {url}")
        
        # Clean up URL if needed
        url = url.strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'https://' + url
            
        # Dynamically import web_extractor to avoid circular imports
        try:
            import web_extractor
            
            # Extract content from the URL
            content = await web_extractor.extract_content_from_url(url)
            
            if content:
                # Create a preview of the content for display
                preview = content[:300] + "..." if len(content) > 300 else content
                
                return {
                    "content": content,
                    "url": url,
                    "message": f"📄 **محتوای استخراج‌شده از آدرس:**\n\n{preview}\n\n🔗 [مشاهده منبع اصلی]({url})"
                }
            else:
                return {
                    "error": "No content extracted",
                    "message": f"متأسفانه نتوانستم محتوایی از {url} استخراج کنم."
                }
                
        except ImportError:
            logger.error("Failed to import web_extractor module")
            return {
                "error": "Web extractor module not available",
                "message": "متأسفانه در حال حاضر امکان استخراج محتوا از آدرس‌های اینترنتی وجود ندارد."
            }
            
    except Exception as e:
        logger.error(f"Error in extract_content_from_url: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "message": f"خطا در استخراج محتوا از {url}: {str(e)}"
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
    Process function calls from an OpenAI API response.
    Executes any requested functions and returns the result for the bot to use in its response.
    
    Args:
        response_message: The message from OpenAI API containing possible function calls
        chat_id: The chat ID for context-specific functions
        user_id: The user ID for user-specific functions
        
    Returns:
        A string with the function results formatted for the user
    """
    # Check if the message contains function calls
    if not hasattr(response_message, 'function_call') and not hasattr(response_message, 'tool_calls'):
        # No function calls to process, return empty string
        return ""
        
    # Process function_call (older API)
    if hasattr(response_message, 'function_call') and response_message.function_call:
        function_call = response_message.function_call
        function_name = function_call.name
        
        # Parse function arguments
        try:
            function_args = json.loads(function_call.arguments)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse function arguments: {function_call.arguments}")
            return "خطا در پردازش درخواست. لطفاً دوباره تلاش کنید."
            
        # Execute the function
        result = await execute_function(function_name, function_args, chat_id, user_id)
        
        # Return the formatted message result
        if "message" in result:
            return result["message"]
        # For backward compatibility with older versions
        elif "formatted_message" in result:
            return result["formatted_message"]
        elif "error" in result:
            return f"خطا: {result['error']}"
        else:
            # If no formatted message or error, create a basic message
            return f"نتیجه عملیات '{function_name}' با موفقیت دریافت شد."
            
    # Process tool_calls (newer API)
    elif hasattr(response_message, 'tool_calls') and response_message.tool_calls:
        all_results = []
        
        for tool_call in response_message.tool_calls:
            if tool_call.type == 'function':
                function_name = tool_call.function.name
                
                # Parse function arguments
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse function arguments: {tool_call.function.arguments}")
                    all_results.append("خطا در پردازش درخواست. لطفاً دوباره تلاش کنید.")
                    continue
                    
                # Execute the function
                result = await execute_function(function_name, function_args, chat_id, user_id)
                
                # Add the formatted result to our collection
                if "message" in result:
                    all_results.append(result["message"])
                elif "formatted_message" in result:  # For backward compatibility
                    all_results.append(result["formatted_message"])
                elif "error" in result:
                    all_results.append(f"خطا در اجرای '{function_name}': {result['error']}")
                else:
                    # If no formatted message or error, create a basic message
                    all_results.append(f"نتیجه عملیات '{function_name}' با موفقیت دریافت شد.")
        
        # Join all results, separated by dividers if there are multiple
        if len(all_results) > 1:
            return "\n\n---\n\n".join(all_results)
        elif all_results:
            return all_results[0]
        else:
            return ""
    
    # No function calls detected
    return ""

async def execute_function(function_name: str, function_args: dict, chat_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Execute the specified function with the given arguments.
    Properly handles the web search and URL extraction functionality.
    """
    logger.info(f"Executing function: {function_name} with args: {function_args}")
    
    try:
        if function_name == "search_web":
            # Validate we have a search query
            query = function_args.get("query", "").strip()
            if not query:
                return {
                    "error": "برای جستجو به یک عبارت معتبر نیاز است.",
                    "message": "برای انجام جستجو لطفاً عبارت معتبری وارد کنید."
                }
            
            # Get is_news flag, default to False if not provided
            is_news = function_args.get("is_news", False)
            
            # Call the search_web function from this module
            search_results = await search_web(query, is_news)
            
            # If there's a message field already, use it
            if "message" in search_results:
                return search_results
                
            # For backward compatibility with different return formats
            if "formatted_message" in search_results:
                search_results["message"] = search_results["formatted_message"]
                return search_results
                
            # Handle the case where we have results directly from web_search module
            if "results" in search_results:
                results = search_results["results"]
                message = f"🔍 نتایج جستجو برای '{query}':\n\n"
                
                if not results:
                    message += "متأسفانه نتیجه‌ای یافت نشد."
                else:
                    for i, result in enumerate(results, 1):
                        title = result.get("title", "").strip()
                        snippet = result.get("snippet", "").strip()
                        link = result.get("link", "").strip()
                        message += f"**{i}. {title}**\n{snippet}\n🔗 {link}\n\n"
                
                search_results["message"] = message
                return search_results
            
            # If no recognized format, create a generic error message
            if "error" in search_results:
                return {
                    "error": search_results.get("error", "خطای نامشخص"),
                    "message": f"خطا در جستجو: {search_results.get('error', 'خطای نامشخص')}"
                }
            
            # Generic fallback
            return {
                "error": "فرمت پاسخ نامشخص",
                "message": "جستجو انجام شد، اما نتایج به فرمت قابل فهم نیست."
            }
                
        elif function_name == "extract_content_from_url":
            # Validate URL
            url = function_args.get("url", "").strip()
            if not url:
                return {
                    "error": "برای استخراج محتوا به یک آدرس اینترنتی معتبر نیاز است.",
                    "message": "لطفاً یک آدرس اینترنتی (URL) معتبر وارد کنید."
                }
                
            # Call the extract_content_from_url function from this module
            result = await extract_content_from_url(url)
            
            # If there's a message field already, use it
            if "message" in result:
                return result
                
            # For backward compatibility with different return formats
            if "formatted_message" in result:
                result["message"] = result["formatted_message"]
                return result
                
            # Handle error cases
            if "error" in result:
                return {
                    "error": result.get("error", "خطای نامشخص"),
                    "message": f"خطا در استخراج محتوا: {result.get('error', 'خطای نامشخص')}"
                }
                
            # Handle the case where we have content but no formatted message
            if "content" in result:
                content = result["content"]
                preview = content[:300] + "..." if len(content) > 300 else content
                message = f"📄 **محتوای استخراج‌شده از آدرس:**\n\n{preview}\n\n🔗 [مشاهده منبع اصلی]({url})"
                
                result["message"] = message
                return result
                
            # Generic fallback
            return {
                "error": "فرمت پاسخ نامشخص",
                "message": "استخراج محتوا انجام شد، اما نتایج به فرمت قابل فهم نیست."
            }
                
        elif function_name == "get_chat_history":
            days = function_args.get("days", 1)
            chat_id_param = function_args.get("chat_id", chat_id)
            
            if not chat_id_param:
                return {
                    "error": "شناسه چت مشخص نشده است.",
                    "message": "برای دریافت تاریخچه گفتگو، شناسه چت مورد نیاز است."
                }
                
            # Import the memory module dynamically
            try:
                import memory
                
                # Call the get_chat_history_summary function if it exists
                if hasattr(memory, "get_chat_history_summary"):
                    history = await memory.get_chat_history_summary(chat_id_param, days)
                    return {
                        "history": history,
                        "message": history
                    }
                # For compatibility with older versions that might have different function names
                elif hasattr(memory, "summarize_chat_history"):
                    history = await memory.summarize_chat_history(chat_id_param, days)
                    return {
                        "history": history,
                        "message": history
                    }
                else:
                    return {
                        "error": "تابع خلاصه تاریخچه گفتگو پیدا نشد.",
                        "message": "متأسفانه امکان دریافت تاریخچه گفتگو در حال حاضر وجود ندارد."
                    }
            except ImportError:
                logger.error("Failed to import memory module")
                return {
                    "error": "ماژول حافظه پیدا نشد.",
                    "message": "متأسفانه در حال حاضر امکان دریافت تاریخچه گفتگو وجود ندارد."
                }
            except Exception as e:
                logger.error(f"Error getting chat history: {e}")
                return {
                    "error": f"خطا در دریافت تاریخچه گفتگو: {str(e)}",
                    "message": "متأسفانه نتوانستم تاریخچه گفتگو را دریافت کنم."
                }
        
        elif function_name == "get_weather":
            # Validate city parameter
            city = function_args.get("city", "").strip()
            if not city:
                return {
                    "error": "برای دریافت آب و هوا، یک شهر معتبر مورد نیاز است.",
                    "message": "لطفاً نام شهر را برای دریافت اطلاعات آب و هوا مشخص کنید."
                }
            
            # Get units parameter (metric/imperial), default to metric
            units = function_args.get("units", "metric")
            
            try:
                # Import the WeatherService dynamically
                from information_services import WeatherService
                
                # Create an instance of WeatherService
                weather_service = WeatherService()
                
                # Get weather data
                weather_data = await weather_service.get_weather(city, units)
                
                # Check if the weather data was successfully retrieved
                if not weather_data.get("success", False):
                    error_message = weather_data.get("error", "")
                    if "کلید API" in error_message:
                        # Special handling for API key not configured
                        return {
                            "error": "سرویس آب و هوا پیکربندی نشده است.",
                            "message": "متأسفانه امکان دریافت اطلاعات آب و هوا در حال حاضر فراهم نیست. می‌توانید از وب‌سایت‌هایی مانند AccuWeather یا Weather.com برای بررسی آب و هوای شهرها استفاده کنید."
                        }
                    else:
                        return {
                            "error": weather_data.get("error", "خطای نامشخص در دریافت آب و هوا"),
                            "message": f"متأسفانه نتوانستم اطلاعات آب و هوای {city} را دریافت کنم. {weather_data.get('error', '')}"
                        }
                
                # Select the appropriate units based on the 'units' parameter
                temp_unit = "°C" if units == "metric" else "°F"
                wind_unit = "m/s" if units == "metric" else "mph"
                
                # Format a Persian message with the weather information
                message = (
                    f"🌤️ **آب و هوای {weather_data.get('city', city)}**:\n\n"
                    f"🌡️ **دما**: {weather_data.get('temperature', 'N/A')}{temp_unit}\n"
                    f"💧 **رطوبت**: {weather_data.get('humidity', 'N/A')}%\n"
                    f"🍃 **باد**: {weather_data.get('wind_speed', 'N/A')} {wind_unit}\n"
                    f"☁️ **وضعیت**: {weather_data.get('description', 'N/A')}\n"
                )
                
                # Return the weather data with a formatted message
                return {
                    "city": weather_data.get("city", city),
                    "temperature": weather_data.get("temperature", "N/A"),
                    "humidity": weather_data.get("humidity", "N/A"),
                    "wind_speed": weather_data.get("wind_speed", "N/A"),
                    "description": weather_data.get("description", "N/A"),
                    "message": message
                }
                
            except ImportError:
                logger.error("WeatherService module not found")
                return {
                    "error": "سرویس آب و هوا در دسترس نیست.",
                    "message": "متأسفانه در حال حاضر امکان دریافت اطلاعات آب و هوا وجود ندارد."
                }
            except Exception as e:
                logger.error(f"Error getting weather: {e}", exc_info=True)
                return {
                    "error": f"خطا در دریافت آب و هوا: {str(e)}",
                    "message": f"متأسفانه در دریافت اطلاعات آب و هوای {city} مشکلی پیش آمد."
                }
        
        elif function_name == "geocode":
            # Validate query parameter
            query = function_args.get("query", "").strip()
            if not query:
                return {
                    "error": "برای جستجوی مکان، یک عبارت جستجو مورد نیاز است.",
                    "message": "لطفاً نام مکان یا آدرسی که می‌خواهید جستجو کنید را وارد کنید."
                }
            
            # Get optional parameters with defaults
            limit = function_args.get("limit", 5)
            language = function_args.get("language", "fa")
            
            try:
                # Import the NominatimService dynamically
                from information_services import NominatimService
                
                # Create an instance of NominatimService
                geocoding_service = NominatimService()
                
                # Perform geocoding
                geocode_result = await geocoding_service.geocode(query, limit, language)
                
                # Check if the geocoding was successful
                if not geocode_result.get("success", False):
                    return {
                        "error": geocode_result.get("error", "خطای نامشخص در جستجوی مکان"),
                        "message": f"متأسفانه در جستجوی '{query}' مشکلی پیش آمد. لطفاً عبارت دیگری را امتحان کنید."
                    }
                
                # Return the geocoding results with a formatted message
                return {
                    "query": query,
                    "results": geocode_result.get("results", []),
                    "message": geocode_result.get("message", f"نتایج جستجو برای '{query}'")
                }
                
            except ImportError:
                logger.error("NominatimService module not found")
                return {
                    "error": "سرویس جستجوی مکان در دسترس نیست.",
                    "message": "متأسفانه در حال حاضر امکان جستجوی مکان‌ها وجود ندارد."
                }
            except Exception as e:
                logger.error(f"Error in geocoding: {e}", exc_info=True)
                return {
                    "error": f"خطا در جستجوی مکان: {str(e)}",
                    "message": f"متأسفانه در جستجوی مکان '{query}' مشکلی پیش آمد."
                }
                
        elif function_name == "reverse_geocode":
            # Validate lat and lon parameters
            try:
                lat = float(function_args.get("lat", 0))
                lon = float(function_args.get("lon", 0))
            except (ValueError, TypeError):
                return {
                    "error": "مختصات جغرافیایی نامعتبر",
                    "message": "لطفاً مختصات جغرافیایی معتبر وارد کنید (عرض و طول جغرافیایی باید اعداد باشند)."
                }
            
            # Validate lat/lon are in reasonable ranges
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return {
                    "error": "مختصات جغرافیایی خارج از محدوده",
                    "message": "مختصات جغرافیایی باید در محدوده معتبر باشند (عرض: -90 تا 90، طول: -180 تا 180)."
                }
            
            # Get optional parameters with defaults
            language = function_args.get("language", "fa")
            
            try:
                # Import the NominatimService dynamically
                from information_services import NominatimService
                
                # Create an instance of NominatimService
                geocoding_service = NominatimService()
                
                # Perform reverse geocoding
                reverse_result = await geocoding_service.reverse_geocode(lat, lon, language)
                
                # Check if the reverse geocoding was successful
                if not reverse_result.get("success", False):
                    return {
                        "error": reverse_result.get("error", "خطای نامشخص در تبدیل مختصات به آدرس"),
                        "message": f"متأسفانه در تبدیل مختصات ({lat}, {lon}) به آدرس مشکلی پیش آمد."
                    }
                
                # Return the reverse geocoding results with a formatted message
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "result": reverse_result.get("result", {}),
                    "message": reverse_result.get("message", f"آدرس یافت شده برای مختصات ({lat}, {lon})")
                }
                
            except ImportError:
                logger.error("NominatimService module not found")
                return {
                    "error": "سرویس تبدیل مختصات به آدرس در دسترس نیست.",
                    "message": "متأسفانه در حال حاضر امکان تبدیل مختصات به آدرس وجود ندارد."
                }
            except Exception as e:
                logger.error(f"Error in reverse geocoding: {e}", exc_info=True)
                return {
                    "error": f"خطا در تبدیل مختصات به آدرس: {str(e)}",
                    "message": f"متأسفانه در تبدیل مختصات ({lat}, {lon}) به آدرس مشکلی پیش آمد."
                }
        
        # Handle other functions similarly
        
        # Return a default error for unimplemented functions
        logger.warning(f"Function {function_name} not implemented")
        return {
            "error": f"عملکرد {function_name} پیاده‌سازی نشده است.",
            "message": "متأسفانه این قابلیت در حال حاضر پشتیبانی نمی‌شود."
        }
        
    except Exception as e:
        # Log the full stack trace for debugging
        logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
        return {
            "error": f"خطا در اجرای تابع: {str(e)}",
            "message": "متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً مجدداً تلاش کنید."
        }

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

def select_relevant_functions(prompt: str, must_include: List[str] = None) -> List[Dict[str, Any]]:
    """
    Select only the relevant function definitions based on message content.
    Always includes the functions specified in must_include.
    
    Args:
        prompt: The user message to analyze
        must_include: List of function names to always include (default: ["search_web"])
        
    Returns:
        List of relevant function definitions
    """
    if must_include is None:
        must_include = ["search_web"]  # Always include search by default
    
    prompt_lower = prompt.lower()
    selected_functions = []
    
    # First, add the must-include functions
    for func_name in must_include:
        for func in FUNCTION_DEFINITIONS:
            if func["name"] == func_name and func not in selected_functions:
                selected_functions.append(func)
    
    # Check for URL extraction needs
    if any(term in prompt_lower for term in ["http", "www.", ".com", ".ir", ".org", "url", "وبسایت", "سایت", "لینک"]):
        for func in FUNCTION_DEFINITIONS:
            if func["name"] == "extract_content_from_url" and func not in selected_functions:
                selected_functions.append(func)
    
    # Check for weather queries
    if any(term in prompt_lower for term in ["هوا", "آب و هوا", "دما", "باران", "برف", "weather", "بارش", "درجه"]):
        for func in FUNCTION_DEFINITIONS:
            if func["name"] == "get_weather" and func not in selected_functions:
                selected_functions.append(func)
    
    # Check for location/geocoding queries
    if any(term in prompt_lower for term in ["آدرس", "مکان", "کجاست", "جغرافیایی", "نقشه", "موقعیت", "خیابان", "map", "location"]):
        location_functions = ["geocode", "reverse_geocode"]
        for func in FUNCTION_DEFINITIONS:
            if func["name"] in location_functions and func not in selected_functions:
                selected_functions.append(func)
    
    # Check for chat history queries
    if any(term in prompt_lower for term in ["تاریخچه", "گفتگو", "چت", "history", "chat"]):
        for func in FUNCTION_DEFINITIONS:
            if func["name"] == "get_chat_history" and func not in selected_functions:
                selected_functions.append(func)
    
    # If no relevant functions found (beyond must_include), return must_include functions only
    return selected_functions 