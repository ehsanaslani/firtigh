import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import sqlite3
import threading

logger = logging.getLogger(__name__)

# Constants for token pricing (in USD per 1K tokens)
MODEL_PRICES = {
    # GPT-4o models (current pricing as of March 2025)
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    
    # GPT-4 Vision
    "gpt-4-vision-preview": {"input": 0.01, "output": 0.03},
    
    # GPT-4 Turbo
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    
    # Default fallback for unknown models
    "default": {"input": 0.01, "output": 0.03}
}

# Path for storing token usage data
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TOKEN_DB_PATH = os.path.join(DATA_DIR, "token_usage.db")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Thread local storage for in-memory tracking during a session
_local = threading.local()
_local.session_tokens = {
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_tokens": 0,
    "requests": 0,
    "models": {}
}

def _init_database():
    """Initialize the SQLite database for token tracking if it doesn't exist."""
    conn = sqlite3.connect(TOKEN_DB_PATH)
    cursor = conn.cursor()
    
    # Create token usage table for detailed logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS token_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        model TEXT NOT NULL,
        request_type TEXT NOT NULL,
        prompt_tokens INTEGER NOT NULL,
        completion_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        estimated_cost REAL NOT NULL
    )
    ''')
    
    # Create daily summary table for aggregated stats
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_summary (
        date TEXT PRIMARY KEY,
        total_prompt_tokens INTEGER NOT NULL,
        total_completion_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        total_requests INTEGER NOT NULL,
        total_cost REAL NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Token tracking database initialized")

def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate the estimated cost for the token usage."""
    model_lower = model.lower()
    
    # Find the pricing for the model
    pricing = MODEL_PRICES.get(model_lower)
    if not pricing:
        # Try to match by prefix (e.g. gpt-4o-2024-05-13 would match to gpt-4o)
        for key in MODEL_PRICES:
            if model_lower.startswith(key):
                pricing = MODEL_PRICES[key]
                break
        
        # Use default pricing if no match found
        if not pricing:
            pricing = MODEL_PRICES["default"]
            logger.warning(f"Using default pricing for unknown model: {model}")
    
    # Calculate costs (price is per 1K tokens)
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    
    return round(input_cost + output_cost, 6)

def track_token_usage(model: str, request_type: str, prompt_tokens: int, 
                     completion_tokens: int, total_tokens: int) -> Dict[str, Any]:
    """
    Track token usage for an API call and update the database.
    
    Args:
        model: The model used (e.g., "gpt-4o")
        request_type: Type of request (e.g., "Function Calling API", "Vision API")
        prompt_tokens: Number of input/prompt tokens used
        completion_tokens: Number of completion/output tokens used
        total_tokens: Total tokens used
        
    Returns:
        Dictionary with token usage information including cost
    """
    # Ensure database exists
    if not os.path.exists(TOKEN_DB_PATH):
        _init_database()
    
    # Calculate cost
    estimated_cost = _calculate_cost(model, prompt_tokens, completion_tokens)
    
    # Current timestamp
    timestamp = datetime.now().isoformat()
    
    # Store in database
    conn = sqlite3.connect(TOKEN_DB_PATH)
    cursor = conn.cursor()
    
    # Insert detailed log
    cursor.execute(
        "INSERT INTO token_usage (timestamp, model, request_type, prompt_tokens, completion_tokens, total_tokens, estimated_cost) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (timestamp, model, request_type, prompt_tokens, completion_tokens, total_tokens, estimated_cost)
    )
    
    # Update daily summary
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if today exists in summary
    cursor.execute("SELECT * FROM daily_summary WHERE date = ?", (today,))
    row = cursor.fetchone()
    
    if row:
        # Update existing row
        cursor.execute(
            "UPDATE daily_summary SET "
            "total_prompt_tokens = total_prompt_tokens + ?, "
            "total_completion_tokens = total_completion_tokens + ?, "
            "total_tokens = total_tokens + ?, "
            "total_requests = total_requests + 1, "
            "total_cost = total_cost + ? "
            "WHERE date = ?",
            (prompt_tokens, completion_tokens, total_tokens, estimated_cost, today)
        )
    else:
        # Insert new row
        cursor.execute(
            "INSERT INTO daily_summary (date, total_prompt_tokens, total_completion_tokens, total_tokens, total_requests, total_cost) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (today, prompt_tokens, completion_tokens, total_tokens, 1, estimated_cost)
        )
    
    conn.commit()
    conn.close()
    
    # Update in-memory session tracking
    _local.session_tokens["total_prompt_tokens"] += prompt_tokens
    _local.session_tokens["total_completion_tokens"] += completion_tokens  
    _local.session_tokens["total_tokens"] += total_tokens
    _local.session_tokens["requests"] += 1
    
    # Track by model
    if model not in _local.session_tokens["models"]:
        _local.session_tokens["models"][model] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
            "cost": 0
        }
    
    _local.session_tokens["models"][model]["prompt_tokens"] += prompt_tokens
    _local.session_tokens["models"][model]["completion_tokens"] += completion_tokens
    _local.session_tokens["models"][model]["total_tokens"] += total_tokens
    _local.session_tokens["models"][model]["requests"] += 1
    _local.session_tokens["models"][model]["cost"] += estimated_cost
    
    # Return usage details
    return {
        "model": model,
        "request_type": request_type,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": estimated_cost
    }

def get_token_usage_summary(days: int = 30) -> Dict[str, Any]:
    """
    Get a summary of token usage over the specified number of days.
    
    Args:
        days: Number of days to include in the summary (default: 30)
        
    Returns:
        Dictionary with token usage summary
    """
    if not os.path.exists(TOKEN_DB_PATH):
        _init_database()
        return {
            "period_days": days,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_requests": 0,
            "total_cost": 0,
            "daily_usage": [],
            "model_usage": {}
        }
    
    # Calculate the start date
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Connect to database
    conn = sqlite3.connect(TOKEN_DB_PATH)
    cursor = conn.cursor()
    
    # Get daily summary
    cursor.execute(
        "SELECT date, total_prompt_tokens, total_completion_tokens, total_tokens, total_requests, total_cost "
        "FROM daily_summary WHERE date >= ? ORDER BY date",
        (start_date,)
    )
    daily_rows = cursor.fetchall()
    
    # Get model summary
    cursor.execute(
        "SELECT model, SUM(prompt_tokens), SUM(completion_tokens), SUM(total_tokens), COUNT(*), SUM(estimated_cost) "
        "FROM token_usage WHERE timestamp >= ? GROUP BY model",
        (start_date,)
    )
    model_rows = cursor.fetchall()
    
    # Get overall summary
    cursor.execute(
        "SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(total_tokens), COUNT(*), SUM(estimated_cost) "
        "FROM token_usage WHERE timestamp >= ?",
        (start_date,)
    )
    overall = cursor.fetchone()
    
    conn.close()
    
    # Process data
    total_prompt_tokens = overall[0] or 0
    total_completion_tokens = overall[1] or 0
    total_tokens = overall[2] or 0
    total_requests = overall[3] or 0
    total_cost = overall[4] or 0
    
    daily_usage = [
        {
            "date": row[0],
            "prompt_tokens": row[1],
            "completion_tokens": row[2],
            "total_tokens": row[3],
            "requests": row[4],
            "cost": row[5]
        }
        for row in daily_rows
    ]
    
    model_usage = {
        row[0]: {
            "prompt_tokens": row[1],
            "completion_tokens": row[2],
            "total_tokens": row[3],
            "requests": row[4],
            "cost": row[5]
        }
        for row in model_rows
    }
    
    return {
        "period_days": days,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_requests": total_requests,
        "total_cost": round(total_cost, 2),
        "daily_usage": daily_usage,
        "model_usage": model_usage
    }

def get_session_token_usage() -> Dict[str, Any]:
    """Get token usage for the current session."""
    return _local.session_tokens

def reset_session_token_usage():
    """Reset the session token usage tracker."""
    _local.session_tokens = {
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "requests": 0,
        "models": {}
    }

def format_token_usage_report(days: int = 30, include_session: bool = True) -> str:
    """
    Format a token usage report as a human-readable string.
    
    Args:
        days: Number of days to include in the report
        include_session: Whether to include current session stats
        
    Returns:
        A formatted string with the token usage report
    """
    summary = get_token_usage_summary(days)
    
    report = [
        f"===== Token Usage Report ({days} days) =====",
        f"Total Requests: {summary['total_requests']}",
        f"Total Tokens: {summary['total_tokens']:,}",
        f"  - Prompt Tokens: {summary['total_prompt_tokens']:,}",
        f"  - Completion Tokens: {summary['total_completion_tokens']:,}",
        f"Estimated Cost: ${summary['total_cost']:.2f}",
        "",
        "--- By Model ---"
    ]
    
    # Add model breakdown
    for model, usage in summary['model_usage'].items():
        report.append(f"{model}:")
        report.append(f"  Requests: {usage['requests']}")
        report.append(f"  Tokens: {usage['total_tokens']:,} (Input: {usage['prompt_tokens']:,}, Output: {usage['completion_tokens']:,})")
        report.append(f"  Cost: ${usage['cost']:.2f}")
    
    # Add session info if requested
    if include_session:
        session = get_session_token_usage()
        report.extend([
            "",
            "--- Current Session ---",
            f"Requests: {session['requests']}",
            f"Tokens: {session['total_tokens']:,} (Input: {session['total_prompt_tokens']:,}, Output: {session['total_completion_tokens']:,})"
        ])
        
        for model, usage in session['models'].items():
            report.append(f"  {model}: {usage['total_tokens']:,} tokens, ${usage['cost']:.4f}")
    
    return "\n".join(report)

# Initialize the database on module import
if not os.path.exists(TOKEN_DB_PATH):
    _init_database() 