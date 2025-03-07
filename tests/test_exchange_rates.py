import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import exchange_rates

# Helper function to run async tests
def run_async(coroutine):
    """Helper to run async functions in tests."""
    # Create a new event loop for each test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

@patch('aiohttp.ClientSession.get')
def test_usd_irr_rate_fetching(mock_get):
    """Test fetching USD/IRR exchange rate from alanchand.com."""
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="""
        <html>
            <body>
                <div data-currency="USD">
                    <span class="currency-price">890,500</span>
                    <span class="currency-change">2.5%</span>
                </div>
            </body>
        </html>
    """)
    
    # Configure the mock
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Call the function
    result = run_async(exchange_rates.get_usd_irr_rate())
    
    # Verify the result
    assert result["success"] is True
    assert result["currency"] == "USD/IRR"
    assert result["current_rate"] == "890500"  # Commas should be removed
    assert result["change_percent"] == "2.5%"
    assert result["source"] == "alanchand.com"
    assert "timestamp" in result

def test_rate_data_formatting():
    """Test proper formatting of rate data."""
    # Test with a successful result
    test_data = {
        "success": True,
        "currency": "USD/IRR",
        "current_rate": "890500",
        "change_percent": "2.5%",
        "source": "alanchand.com",
        "source_url": "https://alanchand.com/",
        "timestamp": "2023-01-01T12:00:00"
    }
    
    formatted = exchange_rates.format_exchange_rate_result(test_data)
    
    # Check that the formatted message contains expected elements
    assert "نرخ دلار آمریکا به ریال" in formatted
    assert "890,500" in formatted  # Should be formatted with commas
    assert "2.5%" in formatted
    assert "alanchand.com" in formatted
    assert "2023-01-01" in formatted
    
    # Test with failed result
    error_data = {
        "success": False,
        "error": "Test error message"
    }
    
    formatted_error = exchange_rates.format_exchange_rate_result(error_data)
    assert "خطا در دریافت نرخ ارز" in formatted_error
    assert "Test error message" in formatted_error

@patch('exchange_rates.get_usd_irr_rate')
def test_usd_toman_rate(mock_irr_rate):
    """Test conversion from IRR to Toman."""
    # Set up the mock to return a successful IRR rate
    mock_irr_rate.return_value = {
        "success": True,
        "currency": "USD/IRR",
        "current_rate": "890500",
        "change_percent": "2.5%",
        "source": "alanchand.com",
        "source_url": "https://alanchand.com/",
        "timestamp": "2023-01-01T12:00:00"
    }
    
    # Call the function
    result = run_async(exchange_rates.get_usd_toman_rate())
    
    # Verify the result
    assert result["success"] is True
    assert result["currency"] == "USD/TOMAN"
    assert float(result["current_rate"]) == 89050.0  # Should be divided by 10
    
    # The original_rial_rate might be converted to a float string
    assert float(result["original_rial_rate"]) == float("890500")
    assert result["change_percent"] == "2.5%" 