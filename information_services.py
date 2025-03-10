import aiohttp
from datetime import datetime
import os
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List

# Configure logging
logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        
        # Log API key status (masked for security)
        logger.info(f"WeatherService initialized. API Key available: {'Yes' if self.api_key else 'No'}")
    
    async def get_weather(self, city: str, units: str = "metric") -> dict:
        """Get current weather for a specified city"""
        # Check if API key is available
        if not self.api_key:
            logger.error("No OpenWeather API key available")
            return {
                "success": False,
                "error": "کلید API سرویس آب و هوا تنظیم نشده است."
            }
            
        try:
            params = {
                "q": city,
                "appid": self.api_key,
                "units": units
            }
            
            logger.info(f"Fetching weather for {city} with units {units}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        error_data = await response.text()
                        logger.error(f"Failed to fetch weather: HTTP {response.status}. Response: {error_data}")
                        return {
                            "success": False,
                            "error": f"خطا در دریافت اطلاعات آب و هوا: کد خطا {response.status}"
                        }
                    
                    data = await response.json()
                    
            # Format the weather data
            try:
                weather_info = {
                    "success": True,
                    "city": data["name"],
                    "country": data.get("sys", {}).get("country", ""),
                    "temperature": round(data["main"]["temp"]),
                    "description": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": round(data["wind"]["speed"]),
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                
                logger.info(f"Successfully retrieved weather for {city}")
                return weather_info
                
            except KeyError as e:
                logger.error(f"Error parsing weather data: {e}. Data: {data}")
                return {
                    "success": False,
                    "error": "خطا در پردازش اطلاعات آب و هوا"
                }
                
        except Exception as e:
            logger.error(f"Error in weather service: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"خطا در سرویس آب و هوا: {str(e)}"
            }

class NominatimService:
    def __init__(self):
        self.base_url = "https://nominatim.openstreetmap.org"
        self.last_request_time = 0
        self.user_agent = "FirtighBot/1.0 (https://t.me/firtigh_bot)"
        
        logger.info("NominatimService initialized")
    
    async def _ensure_rate_limit(self):
        """Ensure we don't exceed 1 request per second as per Nominatim usage policy"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < 1.0:
            wait_time = 1.0 - time_since_last_request
            logger.info(f"Rate limiting: Waiting {wait_time:.2f} seconds before next Nominatim request")
            await asyncio.sleep(wait_time)
            
        self.last_request_time = time.time()
    
    async def geocode(self, query: str, limit: int = 5, language: str = "fa") -> dict:
        """
        Search for places by name/address (forward geocoding)
        
        Args:
            query: The search query (place name, address, etc.)
            limit: Maximum number of results (1-50)
            language: Preferred language for results
            
        Returns:
            Dictionary with geocoding results
        """
        try:
            # Enforce rate limit
            await self._ensure_rate_limit()
            
            # Validate and constrain parameters
            limit = max(1, min(limit, 10))  # Limit between 1 and 10 to be reasonable
            
            params = {
                "q": query,
                "format": "json",
                "addressdetails": 1,
                "limit": limit,
                "accept-language": language
            }
            
            headers = {
                "User-Agent": self.user_agent,
                "Referer": "https://t.me/firtigh_bot"
            }
            
            logger.info(f"Geocoding query: {query}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/search", 
                                      params=params, 
                                      headers=headers) as response:
                    if response.status != 200:
                        error_data = await response.text()
                        logger.error(f"Failed geocoding request: HTTP {response.status}. Response: {error_data}")
                        return {
                            "success": False,
                            "error": f"Error in geocoding request: Status {response.status}"
                        }
                    
                    data = await response.json()
            
            # Format the geocoding results
            if not data:
                return {
                    "success": True,
                    "results": [],
                    "message": f"No results found for '{query}'"
                }
                
            formatted_results = []
            for item in data:
                result = {
                    "place_id": item.get("place_id"),
                    "name": item.get("display_name", ""),
                    "latitude": float(item.get("lat", 0)),
                    "longitude": float(item.get("lon", 0)),
                    "type": item.get("type", ""),
                    "importance": item.get("importance", 0),
                    "address": item.get("address", {})
                }
                formatted_results.append(result)
                
            # Include attribution as required by Nominatim usage policy
            message = self._format_geocode_message(query, formatted_results)
            
            return {
                "success": True,
                "query": query,
                "results": formatted_results,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error in geocoding service: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error in geocoding service: {str(e)}"
            }
    
    async def reverse_geocode(self, lat: float, lon: float, language: str = "fa") -> dict:
        """
        Get address for a location (reverse geocoding)
        
        Args:
            lat: Latitude
            lon: Longitude
            language: Preferred language for results
            
        Returns:
            Dictionary with reverse geocoding results
        """
        try:
            # Enforce rate limit
            await self._ensure_rate_limit()
            
            params = {
                "lat": lat,
                "lon": lon,
                "format": "json",
                "addressdetails": 1,
                "accept-language": language
            }
            
            headers = {
                "User-Agent": self.user_agent,
                "Referer": "https://t.me/firtigh_bot"
            }
            
            logger.info(f"Reverse geocoding at coordinates: {lat}, {lon}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/reverse", 
                                      params=params, 
                                      headers=headers) as response:
                    if response.status != 200:
                        error_data = await response.text()
                        logger.error(f"Failed reverse geocoding request: HTTP {response.status}. Response: {error_data}")
                        return {
                            "success": False,
                            "error": f"Error in reverse geocoding request: Status {response.status}"
                        }
                    
                    data = await response.json()
            
            # Format the reverse geocoding result
            if not data or "error" in data:
                return {
                    "success": False,
                    "error": data.get("error", "No results found")
                }
                
            result = {
                "place_id": data.get("place_id"),
                "name": data.get("display_name", ""),
                "latitude": float(data.get("lat", 0)),
                "longitude": float(data.get("lon", 0)),
                "type": data.get("type", ""),
                "address": data.get("address", {})
            }
                
            # Include attribution as required by Nominatim usage policy
            message = self._format_reverse_geocode_message(result)
            
            return {
                "success": True,
                "latitude": lat,
                "longitude": lon,
                "result": result,
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Error in reverse geocoding service: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error in reverse geocoding service: {str(e)}"
            }
    
    def _format_geocode_message(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Format geocoding results into a user-friendly message"""
        if not results:
            return f"🔍 هیچ نتیجه‌ای برای '{query}' یافت نشد."
            
        message = f"🔍 نتایج جستجوی مکانی برای '{query}':\n\n"
        
        for i, result in enumerate(results, 1):
            message += f"**{i}. {result['name']}**\n"
            message += f"📍 مختصات: {result['latitude']}, {result['longitude']}\n"
            
            # Add address components if available
            address = result.get("address", {})
            if address:
                address_parts = []
                for key in ["country", "state", "city", "town", "road"]:
                    if key in address:
                        address_parts.append(address[key])
                if address_parts:
                    message += f"🏙️ {', '.join(address_parts)}\n"
                    
            message += "\n"
            
        # Add attribution as required by Nominatim usage policy
        message += "🌐 داده‌ها از [OpenStreetMap](https://www.openstreetmap.org/) با استفاده از [Nominatim](https://nominatim.org/)"
        
        return message
    
    def _format_reverse_geocode_message(self, result: Dict[str, Any]) -> str:
        """Format reverse geocoding result into a user-friendly message"""
        message = f"📍 **موقعیت یافت شده:**\n\n"
        message += f"{result['name']}\n\n"
        
        # Add address components if available
        address = result.get("address", {})
        if address:
            message += "**جزئیات آدرس:**\n"
            for key, value in address.items():
                message += f"• {key}: {value}\n"
            
        message += f"\n🌐 مختصات: {result['latitude']}, {result['longitude']}\n\n"
            
        # Add attribution as required by Nominatim usage policy
        message += "داده‌ها از [OpenStreetMap](https://www.openstreetmap.org/) با استفاده از [Nominatim](https://nominatim.org/)"
        
        return message 