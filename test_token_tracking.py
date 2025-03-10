"""
Test script for token tracking functionality.
"""

import token_tracking
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_token_tracking():
    """Test token tracking functionality."""
    print("Testing token tracking...")
    
    # Track some token usage
    result = token_tracking.track_token_usage(
        model="gpt-4o-mini",
        request_type="Test Request",
        prompt_tokens=100,
        completion_tokens=20,
        total_tokens=120
    )
    
    print(f"Token usage tracked: {result}")
    
    # Get usage summary
    summary = token_tracking.get_token_usage_summary(days=1)
    print(f"Token usage summary:\n{summary}")
    
    # Get formatted report
    report = token_tracking.format_token_usage_report(days=1)
    print(f"\nToken usage report:\n{report}")

if __name__ == "__main__":
    test_token_tracking() 