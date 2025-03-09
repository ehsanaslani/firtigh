import os
import re
import json
import openai
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Import config for model settings
import config

# Import database to fetch chat history
import database

logger = logging.getLogger(__name__)

async def is_history_request(text: str) -> bool:
    """Check if a message is asking for chat history or summary."""
    history_keywords = [
        "تاریخچه", "history", "گذشته", "خلاصه", "summary", "جمع بندی", "بحث", 
        "گفتگو", "discussion", "چت", "chat", "روز قبل", "روز پیش", "روز گذشته", 
        "هفته", "week", "اخیر", "recent", "آخرین"
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in history_keywords)

async def extract_time_period(text: str) -> int:
    """Extract the time period (in days) from the request text."""
    # Default to 3 days
    default_days = 3
    
    # Check for common time periods in Persian and English
    if "یک روز" in text or "دیروز" in text or "yesterday" in text or "1 day" in text or "one day" in text:
        return 1
    elif "دو روز" in text or "2 day" in text or "two day" in text:
        return 2
    elif "سه روز" in text or "3 day" in text or "three day" in text:
        return 3
    elif "چهار روز" in text or "4 day" in text or "four day" in text:
        return 4
    elif "پنج روز" in text or "5 day" in text or "five day" in text:
        return 5
    elif "شش روز" in text or "6 day" in text or "six day" in text:
        return 6
    elif "هفت روز" in text or "یک هفته" in text or "7 day" in text or "seven day" in text or "week" in text:
        return 7
    elif "ده روز" in text or "10 day" in text or "ten day" in text:
        return 10
    elif "یک ماه" in text or "30 day" in text or "thirty day" in text or "month" in text:
        return 30
    
    return default_days

async def generate_chat_summary(days: int, chat_id: Optional[int] = None) -> str:
    """
    Generate a summary of chat history using OpenAI.
    
    Args:
        days: Number of days to look back
        chat_id: If provided, only summarize messages from this chat
    
    Returns:
        A summary of the chat history
    """
    try:
        # Get formatted message history
        message_history = database.get_formatted_message_history(days, chat_id)
        
        if "No messages found" in message_history:
            return "در این بازه زمانی هیچ پیامی ذخیره نشده است. 🤷‍♂️"
        
        # Prepare system prompt
        system_prompt = (
            "شما یک خلاصه‌کننده حرفه‌ای هستید که باید تاریخچه پیام‌های یک گروه تلگرام را به زبان فارسی خلاصه کنید. "
            "سعی کنید خلاصه مختصر اما جامع باشد و موضوعات اصلی گفتگو را پوشش دهد. "
            "ایموجی‌های مناسب را نیز اضافه کنید تا خلاصه برای خواننده جذاب‌تر شود. "
            "از فرمت تلگرام استفاده کنید (مثلا *متن پررنگ* برای موضوعات مهم). "
            "خلاصه باید شامل نام افرادی باشد که فعال‌ترین بوده‌اند. "
            "تاریخ‌های مهم را نیز ذکر کنید."
        )
        
        # Create API request
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"لطفا تاریخچه پیام‌های زیر را خلاصه کنید:\n\n{message_history}"}
        ]
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model=config.OPENAI_MODEL_SUMMARY,
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Add header for clarity
        days_text = "روز" if days == 1 else "روز"
        header = f"*خلاصه گفتگوهای {days} {days_text} گذشته* 📋\n\n"
        
        return header + summary
    except Exception as e:
        logger.error(f"Error generating chat summary: {e}")
        return "متأسفانه در خلاصه‌سازی تاریخچه پیام‌ها مشکلی پیش آمد. 😔" 