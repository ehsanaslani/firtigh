import logging
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json

logger = logging.getLogger(__name__)

async def get_usd_irr_rate() -> dict:
    """
    Fetch USD to IRR exchange rate from alanchand.com
    Returns a dictionary with current rate and related information
    """
    url = "https://alanchand.com/"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch exchange rate data: HTTP {response.status}")
                    return {
                        "success": False,
                        "error": f"Failed to fetch data: HTTP {response.status}"
                    }
                
                html = await response.text()
            
        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        try:
            # Find the USD rate information on alanchand.com
            current_rate = None
            change_amount = None
            change_percent = None
            
            # Look for the USD rate - this will need to be updated based on alanchand.com's structure
            # Since alanchand.com might have a different structure, we'll look for USD data
            usd_element = soup.select_one("[data-currency='USD']")
            if usd_element:
                price_element = usd_element.select_one(".currency-price")
                if price_element:
                    current_rate = price_element.text.strip()
                
                # Try to find change percentage if available
                change_element = usd_element.select_one(".currency-change")
                if change_element:
                    change_text = change_element.text.strip()
                    match = re.search(r'([\d.]+)%', change_text)
                    if match:
                        change_percent = match.group(0)
            
            # If we didn't find the element with the specific selector, try a more general approach
            if not current_rate:
                # Look for any element containing USD rate information
                usd_elements = soup.find_all(string=re.compile(r'USD|دلار|Dollar', re.IGNORECASE))
                for element in usd_elements:
                    parent = element.parent
                    if parent:
                        # Look for numbers near this element
                        price_text = parent.get_text()
                        price_match = re.search(r'[\d,]+', price_text)
                        if price_match:
                            current_rate = price_match.group(0)
                            break
            
            # Clean up the current rate (remove commas and non-numeric chars)
            if current_rate:
                current_rate = current_rate.replace(',', '')
                # Keep only digits and a single decimal point if exists
                current_rate = re.sub(r'[^\d.]', '', current_rate)
            
            # If all attempts failed, return an error
            if not current_rate:
                return {
                    "success": False,
                    "error": "Failed to find exchange rate data in the page"
                }
            
            return {
                "success": True,
                "currency": "USD/IRR",
                "current_rate": current_rate,
                "change_percent": change_percent,
                "source": "alanchand.com",
                "source_url": url,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error parsing exchange rate data: {e}")
            return {
                "success": False,
                "error": f"Failed to parse data: {str(e)}"
            }
    except Exception as e:
        logger.error(f"Error fetching exchange rate data: {e}")
        return {
            "success": False,
            "error": f"Failed to fetch data: {str(e)}"
        }

def format_exchange_rate_result(result: dict) -> str:
    """
    Format the exchange rate data for display in a message.
    
    Args:
        result: Exchange rate data from get_usd_irr_rate()
        
    Returns:
        Formatted string with exchange rate information
    """
    if not result.get("success", False):
        return f"❌ خطا در دریافت نرخ ارز: {result.get('error', 'خطای نامشخص')}"
    
    # Format the rate with commas for thousands
    rate = result.get("current_rate", "N/A")
    try:
        rate_value = float(rate)
        formatted_rate = f"{rate_value:,.0f}"
    except (ValueError, TypeError):
        formatted_rate = rate
    
    # Format the change percentage
    change = result.get("change_percent", "N/A")
    if change and "%" in change:
        change_value = float(change.replace("%", "").strip())
        if change_value > 0:
            change_icon = "🟢"
        elif change_value < 0:
            change_icon = "🔴"
        else:
            change_icon = "⚪"
        change_formatted = f"{change_icon} {change}"
    else:
        change_formatted = change
    
    # Format the timestamp
    timestamp = result.get("timestamp", "")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            time_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            time_formatted = timestamp
    else:
        time_formatted = "زمان نامشخص"
    
    # Create the formatted message
    message = (
        f"💵 *نرخ دلار آمریکا به ریال*\n\n"
        f"نرخ فعلی: *{formatted_rate} ریال*\n"
        f"تغییرات: {change_formatted}\n"
        f"منبع: [alanchand.com]({result.get('source_url', 'https://alanchand.com/')})\n"
        f"زمان به‌روزرسانی: {time_formatted}"
    )
    
    return message

async def get_usd_toman_rate() -> dict:
    """Get USD to Toman exchange rate (Toman = Rial / 10)"""
    result = await get_usd_irr_rate()
    
    if result.get("success", False):
        # Convert Rial to Toman
        try:
            rate_rial = float(result.get("current_rate", "0"))
            rate_toman = rate_rial / 10
            
            # Update the result with Toman rate
            result["currency"] = "USD/TOMAN"
            result["current_rate"] = str(rate_toman)
            result["original_rial_rate"] = str(rate_rial)
        except (ValueError, TypeError):
            result["success"] = False
            result["error"] = "Failed to convert Rial rate to Toman"
    
    return result 