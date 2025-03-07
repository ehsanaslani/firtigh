import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
from typing import Dict, Any, Optional, Tuple

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
    """Test fetching USD/IRR exchange rate from alanchand.com API."""
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'data': [
            {
                'slug': 'usd',
                'name': 'دلار آمریکا',
                'buy': 48636.42,
                'sell': 48930,
                'dolar_rate': 1,
                'high': 49100,
                'low': 47670,
                'open': 47670
            },
            {
                'slug': 'eur',
                'name': 'یورو',
                'buy': 53000,
                'sell': 53500,
                'dolar_rate': 1.1,
                'high': 54000,
                'low': 52500,
                'open': 53000
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    })
    
    # Configure the mock
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Call the function
    result, error = run_async(exchange_rates.get_currency_rate())
    
    # Verify the result
    assert error is None
    assert result is not None
    assert 'data' in result
    assert len(result['data']) == 2
    assert result['data'][0]['slug'] == 'usd'
    assert result['data'][0]['buy'] == 48636.42
    assert result['data'][0]['sell'] == 48930
    assert 'updated_at' in result

def test_rate_data_formatting():
    """Test proper formatting of rate data."""
    # Test with a successful result
    test_data = {
        'data': [
            {
                'slug': 'usd',
                'name': 'دلار آمریکا',
                'buy': 48636.42,
                'sell': 48930,
                'dolar_rate': 1,
                'high': 49100,
                'low': 47670,
                'open': 47670,
                'change': 1260
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    }
    
    formatted = exchange_rates.format_currency_rate(test_data, 'usd')
    
    # Check that the formatted message contains expected elements
    assert "نرخ دلار آمریکا به ریال" in formatted
    assert "48,636" in formatted  # Buy rate
    assert "48,930" in formatted  # Sell rate
    assert "دلار آمریکا" in formatted
    assert "2023-01-01" in formatted
    
    # Test with different currency - add the currency data first
    test_data_with_euro = {
        'data': [
            {
                'slug': 'usd',
                'name': 'دلار آمریکا',
                'buy': 48636.42,
                'sell': 48930,
                'dolar_rate': 1,
                'high': 49100,
                'low': 47670,
                'open': 47670,
                'change': 1260
            },
            {
                'slug': 'eur',
                'name': 'یورو',
                'buy': 53000,
                'sell': 53500,
                'dolar_rate': 1.1,
                'high': 54000,
                'low': 52500,
                'open': 53000,
                'change': 1500
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    }
    formatted_eur = exchange_rates.format_currency_rate(test_data_with_euro, 'eur')
    assert "ریال" in formatted_eur
    assert "یورو" in formatted_eur

@patch('exchange_rates.get_currency_rate')
def test_usd_toman_rate(mock_get_rate):
    """Test conversion from IRR to Toman."""
    # Set up the mock to return a successful rate response
    mock_get_rate.return_value = ({
        'data': [
            {
                'slug': 'usd',
                'name': 'دلار آمریکا',
                'buy': 48636.42,
                'sell': 48930,
                'dolar_rate': 1,
                'high': 49100,
                'low': 47670,
                'open': 47670,
                'change': 1260
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    }, None)
    
    # Call the function
    result, error = run_async(exchange_rates.get_currency_toman_rate())
    
    # Verify the result
    assert error is None
    assert result is not None
    assert 'data' in result
    assert len(result['data']) == 1
    assert result['data'][0]['buy'] == 4863.642  # Should be divided by 10
    assert result['data'][0]['sell'] == 4893.0  # Should be divided by 10
    assert result['data'][0]['high'] == 4910.0  # Should be divided by 10
    assert result['data'][0]['low'] == 4767.0  # Should be divided by 10

@patch('aiohttp.ClientSession.get')
def test_gold_prices_fetching(mock_get):
    """Test fetching gold prices from alanchand.com API."""
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'data': [
            {
                'name': 'یک گرم طلای 18 عیار',
                'price': 2216200,
                'change': 25900
            },
            {
                'name': 'سکه امامی',
                'price': 28900000,
                'change': 1300000
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    })
    
    # Configure the mock
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Call the function
    result, error = run_async(exchange_rates.fetch_gold_prices())
    
    # Verify the result
    assert error is None
    assert result is not None
    assert 'data' in result
    assert len(result['data']) == 2
    assert result['data'][0]['name'] == 'یک گرم طلای 18 عیار'
    assert result['data'][0]['price'] == 2216200
    assert result['data'][1]['name'] == 'سکه امامی'
    assert result['data'][1]['price'] == 28900000
    assert 'updated_at' in result

def test_gold_price_formatting():
    """Test formatting of gold price data."""
    # Test with a successful result
    test_data = {
        'data': [
            {
                'name': 'یک گرم طلای 18 عیار',
                'price': 2216200,
                'change': 25900
            },
            {
                'name': 'سکه امامی',
                'price': 28900000,
                'change': 1300000
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    }
    
    formatted = exchange_rates.format_gold_prices(test_data)
    
    # Check that the formatted message contains expected elements
    assert "قیمت طلا و سکه" in formatted
    assert "2,216,200" in formatted  # Gold price should be formatted with commas
    assert "28,900,000" in formatted  # Coin price should be formatted with commas
    assert "یک گرم طلای 18 عیار" in formatted
    assert "سکه امامی" in formatted
    assert "2023-01-01" in formatted

@patch('aiohttp.ClientSession.get')
def test_crypto_prices_fetching(mock_get):
    """Test fetching cryptocurrency prices from alanchand.com API."""
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        'data': [
            {
                'name': 'Bitcoin',
                'symbol': 'BTC',
                'price': 65000,
                'change_24h': 2.5
            },
            {
                'name': 'Ethereum',
                'symbol': 'ETH',
                'price': 3500,
                'change_24h': -1.2
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    })
    
    # Configure the mock
    mock_get.return_value.__aenter__.return_value = mock_response
    
    # Call the function
    result, error = run_async(exchange_rates.fetch_crypto_prices())
    
    # Verify the result
    assert error is None
    assert result is not None
    assert 'data' in result
    assert len(result['data']) == 2
    assert result['data'][0]['name'] == 'Bitcoin'
    assert result['data'][0]['symbol'] == 'BTC'
    assert result['data'][0]['price'] == 65000
    assert result['data'][0]['change_24h'] == 2.5
    assert 'updated_at' in result

def test_crypto_price_formatting():
    """Test formatting of cryptocurrency price data."""
    # Test with a successful result
    test_data = {
        'data': [
            {
                'name': 'Bitcoin',
                'symbol': 'BTC',
                'price': 65000,
                'change_24h': 2.5
            },
            {
                'name': 'Ethereum',
                'symbol': 'ETH',
                'price': 3500,
                'change_24h': -1.2
            }
        ],
        'updated_at': '2023-01-01T12:00:00'
    }
    
    formatted = exchange_rates.format_crypto_prices(test_data)
    
    # Check that the formatted message contains expected elements
    assert "قیمت ارزهای دیجیتال" in formatted
    assert "Bitcoin" in formatted
    assert "BTC" in formatted
    assert "$65,000" in formatted
    assert "Ethereum" in formatted
    assert "ETH" in formatted
    assert "$3,500" in formatted
    assert "+2.5%" in formatted  # Positive change with plus sign
    assert "-1.2%" in formatted  # Negative change
    assert "2023-01-01" in formatted

def test_is_crypto_price_request():
    """Test detection of cryptocurrency price requests."""
    # Test positive cases
    assert exchange_rates.is_crypto_price_request("قیمت بیت کوین چنده؟")
    assert exchange_rates.is_crypto_price_request("اتریوم چقدر شده؟")
    assert exchange_rates.is_crypto_price_request("bitcoin price")
    assert exchange_rates.is_crypto_price_request("ارز دیجیتال")
    
    # Test negative cases
    assert not exchange_rates.is_crypto_price_request("قیمت دلار")
    assert not exchange_rates.is_crypto_price_request("نرخ یورو")
    assert not exchange_rates.is_crypto_price_request("قیمت طلا")
    assert not exchange_rates.is_crypto_price_request("Hello world")

def test_is_gold_price_request():
    """Test detection of gold price requests."""
    # Test positive cases
    assert exchange_rates.is_gold_price_request("قیمت طلا چنده؟")
    assert exchange_rates.is_gold_price_request("سکه چقدر شده؟")
    assert exchange_rates.is_gold_price_request("gold price")
    
    # Test negative cases
    assert not exchange_rates.is_gold_price_request("قیمت دلار")
    assert not exchange_rates.is_gold_price_request("بیت کوین")
    assert not exchange_rates.is_gold_price_request("Hello world")

def test_is_exchange_rate_request():
    """Test detection of exchange rate requests."""
    # Test positive cases
    assert exchange_rates.is_exchange_rate_request("قیمت دلار چنده؟")
    assert exchange_rates.is_exchange_rate_request("یورو چقدر شده؟")
    assert exchange_rates.is_exchange_rate_request("dollar price")
    
    # Test negative cases - these should return false because they're about crypto or gold
    assert not exchange_rates.is_exchange_rate_request("قیمت بیت کوین")
    assert not exchange_rates.is_exchange_rate_request("قیمت طلا")
    assert not exchange_rates.is_exchange_rate_request("Hello world") 