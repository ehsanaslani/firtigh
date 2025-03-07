import logging
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import re

logger = logging.getLogger(__name__)

async def get_usd_irr_rate() -> dict:
    """
    Fetch USD to IRR exchange rate from tgju.org
    Returns a dictionary with current rate and related information
    """
    url = "https://www.tgju.org/profile/price_dollar_rl"
    
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
            # First look for the current rate in the market data table
            current_rate = None
            change_amount = None
            change_percent = None
            
            # Try to find the market table that contains price data
            market_table = soup.select_one("table.market-table")
            if market_table:
                # Extract data from the first row of the table (current price)
                first_row = market_table.select_one("tr:first-child")
                if first_row:
                    cells = first_row.select("td")
                    if len(cells) >= 6:
                        current_rate = cells[1].text.strip()
                        change_percent = cells[5].text.strip()
                        
            # If we didn't find the data in the market table, try other selectors
            if not current_rate:
                # Try to find the price in the info box (sometimes used by tgju)
                price_box = soup.select_one(".info-price")
                if price_box:
                    current_rate = price_box.text.strip()
                
                # Try to find the change percentage in the info box
                change_box = soup.select_one(".info-change")
                if change_box:
                    change_text = change_box.text.strip()
                    match = re.search(r'([\d.]+)%', change_text)
                    if match:
                        change_percent = match.group(0)
            
            # If we still didn't find the rate, try the mobile view
            if not current_rate:
                mobile_price = soup.select_one(".price")
                if mobile_price:
                    current_rate = mobile_price.text.strip()
            
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
                "source": "tgju.org",
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
        f"منبع: [tgju.org]({result.get('source_url', 'https://www.tgju.org')})\n"
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