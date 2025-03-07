import aiohttp
from datetime import datetime
import os

class WeatherService:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
    
    async def get_weather(self, city: str, units: str = "metric") -> dict:
        """Get current weather for a specified city"""
        params = {
            "q": city,
            "appid": self.api_key,
            "units": units
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "error": f"Failed to fetch weather: HTTP {response.status}"
                    }
                
                data = await response.json()
                
        return {
            "success": True,
            "city": data["name"],
            "country": data["sys"]["country"],
            "temperature": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "timestamp": datetime.now().isoformat()
        } 