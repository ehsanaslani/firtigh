import logging
import openai
import anthropic
from anthropic import HUMAN_PROMPT, AI_PROMPT
import database
import re
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Initialize the Anthropic client
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def is_history_request(text: str) -> bool:
    """Check if the text contains a request for chat history."""
    if not text:
        return False
    
    # Regular expressions for history-related phrases
    history_patterns = [
        r'خلاصه(?:ی| |‌ی)?(?:.*?)(?:گفتگو|چت|صحبت|بحث)',
        r'تاریخچه(?:ی| |‌ی)?(?:.*?)(?:گفتگو|چت|صحبت|بحث)',
        r'(?:گفتگو|چت|صحبت|بحث)(?:.*?)(?:خلاصه|جمع[ ]?بندی) کن',
        r'چه چیزهایی (?:گفته شد|بحث شد|صحبت شد)',
        r'چی (?:گفته شد|بحث شد|صحبت شد)',
        r'summarize (?:the )?chat',
        r'chat (?:history|summary)'
    ]
    
    for pattern in history_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False

async def extract_time_period(text: str) -> int:
    """
    Extract time period from a request.
    
    Returns number of days to summarize (default: 1)
    """
    # Default to 1 day if no specific time mentioned
    days = 1
    
    # Check for specific time mentions
    if re.search(r'(?:هفته|week)', text, re.IGNORECASE):
        days = 7
    elif re.search(r'(?:ماه|month)', text, re.IGNORECASE):
        days = 30
    elif re.search(r'(?:دو|۲|2).*(?:روز|day)', text, re.IGNORECASE):
        days = 2
    elif re.search(r'(?:سه|۳|3).*(?:روز|day)', text, re.IGNORECASE):
        days = 3
    elif re.search(r'(?:چهار|۴|4).*(?:روز|day)', text, re.IGNORECASE):
        days = 4
    elif re.search(r'(?:پنج|۵|5).*(?:روز|day)', text, re.IGNORECASE):
        days = 5
    
    return days

async def generate_chat_summary(days: int, chat_id: Optional[int] = None) -> str:
    """
    Generate a summary of chat history.
    
    Args:
        days: Number of days to include in the summary
        chat_id: Specific chat to summarize (or None for all chats)
        
    Returns:
        A text summary of the chat history
    """
    try:
        # Get messages from the database
        messages = database.get_messages(days=days, chat_id=chat_id)
        
        if not messages:
            return "در این بازه زمانی پیامی یافت نشد."
        
        # Format messages for the summary
        message_history = ""
        for msg in messages:
            sender = msg.get("sender_name", "ناشناس")
            text = msg.get("text", "")
            if text:
                message_history += f"{sender}: {text}\n\n"
        
        # Prepare the prompt
        system_prompt = """
        شما یک دستیار هوشمند برای خلاصه‌سازی پیام‌های گروه هستید. وظیفه شما تهیه یک خلاصه سازمان‌یافته و ساختارمند از پیام‌های یک گروه تلگرام است.
        
        در خلاصه خود:
        1. موضوعات اصلی بحث را دسته‌بندی کنید
        2. نکات مهم و اطلاعات کلیدی را استخراج کنید
        3. به ترتیب زمانی مباحث اشاره کنید
        4. از فرمت مارک‌داون تلگرام استفاده کنید (مثلاً *متن پررنگ* برای تیترها)
        5. از ایموجی‌های مناسب استفاده کنید
        6. خلاصه را به بخش‌های منطقی تقسیم کنید
        
        از بیان "در این گروه" یا "در این چت" خودداری کنید. به جای آن به موضوعات مستقیماً اشاره کنید.
        """
        
        # Full prompt for the API call
        full_prompt = f"{system_prompt}\n\nلطفا تاریخچه پیام‌های زیر را خلاصه کنید:\n\n{message_history}"
        
        # Call Claude API for summarization using v0.21.2 format
        response = claude_client.completion(
            prompt=full_prompt,
            model="claude-3-5-haiku-20240307",
            max_tokens_to_sample=4000,
            temperature=0.7
        )
        
        summary = response.completion.strip()
        
        # Add header for clarity
        days_text = "روز" if days == 1 else "روز"
        header = f"*خلاصه گفتگوهای {days} {days_text} گذشته* 📋\n\n"
        
        return header + summary
    except Exception as e:
        logger.error(f"Error generating chat summary: {e}")
        return "متأسفانه در تهیه خلاصه گفتگو مشکلی پیش آمد. لطفاً بعداً دوباره تلاش کنید." 