"""
Test script for bot integration with token tracking.
"""

import asyncio
import logging
from bot import generate_ai_response
import token_tracking

# Configure logging
logging.basicConfig(level=logging.INFO)

async def test_bot_with_token_tracking():
    """Test the bot integration with token tracking."""
    print("Testing bot with token tracking...")
    
    # Send a simple message to the bot
    response = await generate_ai_response('سلام، امروز چطوری؟')
    
    print(f"Response: {response}")
    print("\nChecking token usage report:")
    
    # Get token usage report
    report = token_tracking.format_token_usage_report(days=1)
    print(report)

if __name__ == "__main__":
    asyncio.run(test_bot_with_token_tracking()) 