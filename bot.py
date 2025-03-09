import os
import sys
import time
import re
import json
import random
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import openai
import anthropic
from anthropic import HUMAN_PROMPT, AI_PROMPT
import requests
from io import BytesIO
from telegram import Update, InputMediaPhoto, Message, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAnimation, InputMediaDocument, BotCommand, ParseMode
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes, CallbackQueryHandler, CallbackContext
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from urllib.parse import urlparse
import database
import web_search
import web_extractor
import memory
import usage_limits
import summarizer
import link_processing
import image_processing
import exchange_rates
import image_generator
from group_isolation import get_group_chat_id
from config import BOT_NAME

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize the Anthropic client
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Constants for enhanced memory
MAX_MEMORY_MESSAGES = 1000  # Maximum number of messages to remember
BOT_NAME = "فیرتیق"
BOT_FULL_NAME = "فیرتیق الله باقرزاده"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"سلام {user.mention_html()}! من {BOT_FULL_NAME} هستم. برای دریافت پاسخ، من رو با @firtigh یا {BOT_NAME} در پیام خود تگ کنید."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        f"👋 سلام {update.effective_user.first_name if update.effective_user else ''}!\n\n"
        "من فیرتیق هستم، یک ربات هوشمند که میتونم به سوال‌های شما پاسخ بدم و در گفتگوها شرکت کنم.\n\n"
        "*دستورات قابل استفاده:*\n"
        "/start - شروع کار با ربات\n"
        "/help - نمایش این راهنما\n"
        "/dollar - دریافت نرخ دلار به ریال\n"
        "/toman - دریافت نرخ دلار به تومان\n"
        "/currency [ارز] [تومان] - دریافت نرخ ارز دلخواه (مثال: /currency eur)\n"
        "/gold - دریافت قیمت طلا و سکه\n"
        "/crypto [ارز] - دریافت قیمت ارزهای دیجیتال (مثال: /crypto btc)\n\n"
        "*قابلیت‌های من:*\n"
        "• پاسخ به سوالات شما به زبان فارسی \n"
        "• جستجوی اینترنت با کلمه کلیدی \"جستجو\" یا \"search\"\n"
        "• تشخیص و پاسخ به درخواست‌های اخبار با کلیدواژه‌هایی مثل \"اخبار\" یا \"خبر\"\n"
        "• استخراج محتوا از لینک‌های موجود در پیام\n"
        "• نمایش قیمت ارز، طلا، سکه و ارزهای دیجیتال\n"
        "• درک و استفاده از تصاویر در گفتگو\n"
        "• ساخت تصویر با دستوراتی مثل \"تصویر بساز از...\" (محدود به ۳ بار در روز)\n\n"
        "*برای استفاده از من:*\n"
        "• در چت خصوصی: پیام خود را مستقیماً بنویسید\n"
        "• در گروه‌ها: من را با @firtigh یا @@firtigh تگ کنید\n\n"
        "من به صورت خودکار آموزش می‌بینم و از تاریخچه گفتگوها برای ارائه پاسخ‌های بهتر استفاده می‌کنم."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def is_serious_question(text: str) -> bool:
    """Determine if a message appears to be a serious question."""
    serious_indicators = [
        '?', 'چطور', 'چگونه', 'آیا', 'چرا', 'کی', 'کجا', 'چه', 'چند',
        'help', 'problem', 'issue', 'error', 'مشکل', 'خطا', 'کمک'
    ]
    
    # Check if any serious indicators are in the text
    for indicator in serious_indicators:
        if indicator in text.lower():
            return True
            
    return False

async def generate_ai_response(prompt: str, chat_history: Optional[str] = None, 
                               user_profile: Optional[str] = None, search_results: Optional[str] = None,
                               web_content: Optional[str] = None, image_url: Optional[str] = None) -> str:
    """
    Generate an AI response using Claude 3.5 Haiku
    
    Args:
        prompt (str): The user's query
        chat_history (Optional[str]): Recent chat history for context
        user_profile (Optional[str]): User profile for personalization
        search_results (Optional[str]): Search results to include in the response
        web_content (Optional[str]): Web content from fetched links
        image_url (Optional[str]): URL of an image if present in the query
        
    Returns:
        str: The generated response
    """
    try:
        # Construct the prompt with system instructions
        system_instructions = (
            "You are a helpful, friendly, and witty Persian-speaking AI assistant named فیرتیق (Firtigh). "
            "Respond to users in a conversational, natural, and helpful way. "
            "You should always respond in Persian (Farsi) unless specifically asked to respond in another language. "
            "Format links as [display text](URL) so they are clickable in Telegram. "
            "If asked about your creator, say you were created by @ehsaasa. "
            "Stay in character as a helpful, somewhat playful assistant. "
            "Avoid unnecessarily formal language and aim for a friendly tone."
        )
        
        # Build the entire prompt
        full_prompt = f"{system_instructions}\n\n"
        
        # Add chat history for context if available
        if chat_history:
            full_prompt += f"Recent chat history:\n{chat_history}\n\n"
        
        # Add user profile for personalization if available
        if user_profile:
            full_prompt += f"User profile information:\n{user_profile}\n\n"
        
        # Add the main prompt from the user
        full_prompt += f"User query: {prompt}\n\n"
        
        # Add additional context if available
        additional_context = ""
        
        # Check if this is a news-related query by looking for the news header in search results
        is_news_query = search_results and "📰 *آخرین اخبار*" in search_results
        
        # Add search results to the prompt if available
        if search_results:
            if is_news_query:
                # Special instructions for news queries
                additional_context += (
                    f"\n\nSearch results (news):\n{search_results}\n\n"
                    f"Instructions for responding to this news query:\n"
                    f"1. Maintain all news sources (marked with 📄) and links exactly as they appear in the search results\n"
                    f"2. Categorize the news (e.g., political, economic, sports)\n"
                    f"3. Preserve clickable links in the format [Full news](URL)\n"
                    f"4. Include between 5-15 news items in your response\n"
                    f"5. For each news item, cite the source\n"
                    f"6. Provide a brief overall summary at the end\n"
                    f"7. Always format links as [descriptive text](URL) to ensure they're clickable\n"
                    f"8. Never include a raw URL without the [text](URL) format as it won't be clickable\n"
                )
            else:
                additional_context += (
                    f"\n\nWeb search results:\n{search_results}\n\n"
                    f"Instructions for using these search results:\n"
                    f"1. Use information from these search results to answer the user's question\n"
                    f"2. Preserve clickable links in the [text](URL) format\n"
                    f"3. When referencing a source, use the format [source title](link) to keep the link clickable\n"
                    f"4. Never include a raw URL without the [text](URL) format\n"
                )
        
        # Add web content to the prompt if available
        if web_content:
            additional_context += (
                f"\n\nExtracted content from links:\n{web_content}\n\n"
                f"Instructions for using this content:\n"
                f"1. Summarize and categorize the information\n"
                f"2. Include the original link in your response as [site/page title](URL) to keep it clickable\n"
                f"3. If referencing other links in the content, also format them as [descriptive text](URL)\n"
            )
        
        # Append additional context to the prompt
        if additional_context:
            full_prompt += f"Additional information:{additional_context}"
        
        # Set max tokens based on query type - news queries need more space
        max_tokens = 4000 if is_news_query else 2000
        
        # Set the model - use Haiku for text-only, Sonnet for image queries
        model = "claude-3-5-sonnet-20240620" if image_url else "claude-3-5-haiku-20240307"
        
        # Call Claude API using v0.21.2 format
        response = claude_client.completion(
            prompt=full_prompt,
            model=model,
            max_tokens_to_sample=max_tokens,
            temperature=0.8,  # Slightly higher temperature for more creative responses
        )
        
        return response.completion.strip()
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "متأسفم، در حال حاضر نمی‌توانم پاسخی تولید کنم. 😔"

def is_simple_query(prompt: str) -> bool:
    """
    Determine if a query is simple enough to use the cheaper model.
    
    Args:
        prompt: The user's query/prompt
    
    Returns:
        True if the query is simple, False otherwise
    """
    # Simple queries are typically short
    if len(prompt) < 50:
        return True
    
    # Simple queries typically don't contain multiple questions
    if prompt.count("?") + prompt.count("؟") > 1:
        return False
    
    # Simple queries typically don't request detailed analysis
    complex_terms = [
        "analyze", "explain", "discuss", "compare", "contrast", "evaluate",
        "تحلیل", "توضیح", "شرح", "مقایسه", "ارزیابی", "بررسی"
    ]
    
    for term in complex_terms:
        if term in prompt.lower():
            return False
    
    return True

async def extract_media_info(message, context):
    """
    Extract media information from a message.
    
    Args:
        message: The message to extract media from
        context: The telegram context for file downloads
    
    Returns:
        Tuple of (media_type, media_description, media_data)
    """
    media_type = None
    media_description = ""
    media_data = None
    
    try:
        # Check for photos
        if message.photo:
            media_type = "photo"
            media_description = "[تصویر]"
            # Get the largest photo (last in the array)
            photo = message.photo[-1]
            media_data = await download_telegram_file(photo.file_id, context)
            
        # Check for animations/GIFs
        elif message.animation:
            media_type = "animation"
            media_description = "[GIF/انیمیشن]"
            # Try to get a thumbnail or the animation itself
            if message.animation.thumbnail:
                media_data = await download_telegram_file(message.animation.thumbnail.file_id, context)
            else:
                media_data = await download_telegram_file(message.animation.file_id, context)
                
        # Check for stickers
        elif message.sticker:
            media_type = "sticker"
            emoji = message.sticker.emoji or ""
            media_description = f"[استیکر {emoji}]"
            if message.sticker.thumbnail:
                media_data = await download_telegram_file(message.sticker.thumbnail.file_id, context)
            else:
                media_data = await download_telegram_file(message.sticker.file_id, context)
                
        # Check for documents/files
        elif message.document:
            media_type = "document"
            file_name = message.document.file_name or "فایل"
            media_description = f"[فایل: {file_name}]"
            # We don't download documents, just mention them
    
    except Exception as e:
        logger.error(f"Error extracting media info: {e}")
    
    return (media_type, media_description, media_data)

async def get_conversation_context(update: Update, context: ContextTypes.DEFAULT_TYPE, depth=3):
    """
    Extract conversation context from reply chains, including images.
    
    Args:
        update: The current update
        context: The telegram context for file downloads
        depth: How many messages back in the reply chain to collect (default: 3)
    
    Returns:
        Tuple of (context_text, media_data_list)
    """
    context_messages = []
    media_data_list = []
    current_message = update.message
    current_depth = 0
    
    # Check if this is a direct reply to a message
    if current_message and current_message.reply_to_message:
        replied_to = current_message.reply_to_message
        
        # Get sender info if available
        sender_name = "someone"
        if replied_to.from_user:
            if replied_to.from_user.username:
                sender_name = f"@{replied_to.from_user.username}"
            elif replied_to.from_user.first_name:
                sender_name = replied_to.from_user.first_name
        
        # Extract media information
        media_type, media_description, media_data = await extract_media_info(replied_to, context)
        
        # If media data was extracted, add it to our list
        if media_data:
            media_data_list.append({
                "type": media_type,
                "data": media_data,
                "sender": sender_name
            })
        
        # Capture message content with rich context
        message_content = ""
        
        # Text content
        if replied_to.text:
            message_content += replied_to.text
        
        # Add media description if available
        if media_description:
            message_content += f" {media_description}"
            
        # Add the message to our context list if it has content
        if message_content:
            context_messages.append(f"{sender_name}: {message_content}")
    
        # Process the reply chain up to specified depth
        while current_message and current_message.reply_to_message and current_depth < depth:
            replied_to = current_message.reply_to_message
            
            # Get sender info if available
            sender_name = "someone"
            if replied_to.from_user:
                if replied_to.from_user.username:
                    sender_name = f"@{replied_to.from_user.username}"
                elif replied_to.from_user.first_name:
                    sender_name = replied_to.from_user.first_name
            
            # Extract media information from this message too
            media_type, media_description, media_data = await extract_media_info(replied_to, context)
            
            # If media data was extracted, add it to our list
            if media_data:
                media_data_list.append({
                    "type": media_type,
                    "data": media_data,
                    "sender": sender_name
                })
            
            # Add text content to context messages
            message_content = ""
            if replied_to.text:
                message_content += replied_to.text
            
            # Add media description if available
            if media_description:
                message_content += f" {media_description}"
                
            # Add the message to our context list if it has content
            if message_content:
                context_messages.append(f"{sender_name}: {message_content}")
            
            # Move up the chain to the previous message
            current_message = replied_to
            current_depth += 1
    
    # Reverse the list so it's in chronological order
    context_messages.reverse()
    media_data_list.reverse()
    
    # If we have context messages, format them
    if context_messages:
        context_text = "سابقه گفتگو:\n" + "\n".join(context_messages) + "\n\n"
        logger.info(f"Found conversation context: {context_text}")
        return context_text, media_data_list
    
    return "", []

async def download_telegram_file(file_id, context):
    """Download a Telegram file and convert it to base64."""
    try:
        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Convert to base64
        base64_data = base64.b64encode(file_bytes).decode('utf-8')
        return base64_data
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return None

def escape_markdown_v2(text):
    """
    Escape special characters for Telegram's MarkdownV2 format.
    """
    # Characters that need to be escaped in MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Escape each special character with a backslash
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def escape_summary_for_markdown(text):
    """
    Escape a summary for Markdown format, preserving intended formatting.
    This is different from MarkdownV2 as we want to preserve *bold* and _italic_ formatting.
    """
    # We need to escape brackets, parentheses, etc. but not formatting characters
    special_chars = ['[', ']', '(', ')', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # First, temporarily replace formatting indicators
    text = text.replace('\\*', '%%%ASTERISK%%%')
    text = text.replace('\\_', '%%%UNDERSCORE%%%')
    
    # Escape special characters
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    # Restore formatting indicators
    text = text.replace('%%%ASTERISK%%%', '\\*')
    text = text.replace('%%%UNDERSCORE%%%', '\\_')
    
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    # Skip processing if there's no message
    if not update.message:
        return
    
    message_text = update.message.text or ""
    chat_id = update.effective_chat.id if update.effective_chat else None
    
    # Store message in database for history tracking
    if update.message.from_user and chat_id:
        # Only store group messages (not private chats)
        if update.effective_chat.type in ["group", "supergroup"]:
            # Prepare message data
            message_data = {
                "message_id": update.message.message_id,
                "chat_id": chat_id,
                "sender_id": update.message.from_user.id,
                "sender_name": update.message.from_user.username or update.message.from_user.first_name,
                "text": message_text,
                "date": time.time(),  # Current timestamp
                "has_photo": bool(update.message.photo),
                "has_animation": bool(update.message.animation),
                "has_sticker": bool(update.message.sticker),
                "has_document": bool(update.message.document)
            }
            
            # Check for images in the message
            if update.message.photo:
                # Get the highest resolution photo
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                
                # Store image information in the message data
                image_data = {
                    "file_id": photo.file_id,
                    "file_unique_id": photo.file_unique_id,
                    "width": photo.width,
                    "height": photo.height,
                    "file_path": file.file_path
                }
                
                # Add image data to the message being stored
                message_data["has_image"] = True
                message_data["image_data"] = image_data
            
            # Add sticker info if present
            if update.message.sticker:
                message_data["sticker_emoji"] = update.message.sticker.emoji
            
            # Add document info if present
            if update.message.document:
                message_data["document_name"] = update.message.document.file_name
            
            # Save to database
            database.save_message(message_data)
            
            # Process for memory and user profiles
            # We use asyncio.create_task to process in the background without delaying response
            asyncio.create_task(memory.process_message_for_memory(message_data))
            
            # Check for name corrections
            if message_text:
                name_correction = memory.analyze_for_name_correction(message_text)
                if name_correction:
                    logger.info(f"Detected name correction: {name_correction['wrong']} -> {name_correction['correct']}")
                    memory.store_name_correction(name_correction["wrong"], name_correction["correct"])
    
    bot_username = context.bot.username.lower() if context.bot.username else "firtigh"
    bot_user_id = context.bot.id
    
    # Different ways the bot might be mentioned in a group
    mentions = [
        f"{BOT_NAME}",            # Persian name (فیرتیق)
        f"{BOT_NAME.lower()}",    # Lowercase Persian name
        "firtigh",                # English transliteration
        f"@{bot_username}",       # Standard @username mention
        "@firtigh",               # Default username mention
    ]
    
    # Check if any form of mention is in the message (case insensitive)
    is_mentioned = message_text and any(mention.lower() in message_text.lower() for mention in mentions)
    
    # Check if this is a reply to the bot's message
    is_reply_to_bot = False
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        is_reply_to_bot = update.message.reply_to_message.from_user.id == bot_user_id
        if is_reply_to_bot:
            logger.info(f"User replied to bot's message: {message_text}")
    
    # Process if the bot is mentioned or if this is a reply to the bot's message
    if is_mentioned or is_reply_to_bot:
        # Log the interaction
        if is_mentioned:
            logger.info(f"Bot mentioned in message: {message_text}")
        
        # Check if this is an instruction to the bot
        is_instruction = False
        if message_text:
            instruction_indicators = [
                "یاد بگیر", "به خاطر بسپار", "به یاد داشته باش", "فراموش نکن", "یادت باشه", 
                "بدان که", "این رو یاد بگیر", "از این به بعد", "از الان به بعد", "دستور میدم",
                "پس از این", "این طوری رفتار کن", "باید", "نباید", "مجبوری", "وظیفه داری"
            ]
            is_instruction = any(indicator in message_text.lower() for indicator in instruction_indicators)
            
            if is_instruction:
                logger.info(f"Detected instruction: {message_text}")
                # Store the instruction in a new database table or as a special memory item
                instruction_data = {
                    "instruction": message_text,
                    "timestamp": time.time(),
                    "user_id": update.message.from_user.id if update.message.from_user else None,
                    "username": update.message.from_user.username or update.message.from_user.first_name if update.message.from_user else "Unknown"
                }
                
                # Create a memory item for this instruction
                memory_item = {
                    "timestamp": time.time(),
                    "message_id": update.message.message_id,
                    "message_text": message_text,
                    "is_memorable": True,  # Force memorability
                    "topics": ["دستورالعمل", "رفتار بات", "قواعد"],
                    "key_points": [f"دستور: {message_text[:100]}..."],
                    "sentiment": "neutral",
                    "sender_id": update.message.from_user.id if update.message.from_user else None,
                    "sender_name": update.message.from_user.username or update.message.from_user.first_name if update.message.from_user else "Unknown"
                }
                
                # Store this instruction in group memory
                if chat_id:
                    await memory.update_group_memory(chat_id, memory_item)
        
        # Get the query - if it's a mention, remove the mention text
        query = message_text
        if is_mentioned and message_text:
            # More carefully remove the mention text
            query = message_text
            for mention in mentions:
                # Look for the mention with word boundaries to avoid partial word matches
                pattern = r'\b' + re.escape(mention) + r'\b'
                query = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
        
        # If there's no query after processing, ask for more information
        if not query and not (update.message.photo or update.message.animation):
            await update.message.reply_text("من رو صدا زدی، ولی سوالی نپرسیدی. چطور می‌تونم کمکت کنم؟ 🤔")
            return
        
        # Check if this is a request for chat history
        if await summarizer.is_history_request(query):
            # Extract time period from query
            days = await summarizer.extract_time_period(query)
            
            # Inform user that we're generating summary
            await update.message.reply_chat_action("typing")
            await update.message.reply_text(f"در حال آماده‌سازی خلاصه گفتگوهای {days} روز گذشته... ⏳")
            
            # Generate and send the summary
            summary = await summarizer.generate_chat_summary(days, chat_id)
            
            # Try to send with Markdown formatting
            try:
                # Use regular Markdown for summaries to preserve formatting
                escaped_summary = escape_summary_for_markdown(summary)
                await update.message.reply_text(escaped_summary, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception as e:
                logger.error(f"Error sending formatted summary: {e}")
                # Fall back to plain text
                await update.message.reply_text(summary)
            
            return
        
        # Check if this is an exchange rate request
        if exchange_rates.is_exchange_rate_request(query):
            currency_slug = exchange_rates.detect_currency_in_query(query)
            is_toman = "تومان" in query.lower() or "تومن" in query.lower()
            
            processing_message = await update.message.reply_text("در حال دریافت نرخ ارز... ⌛")
            
            if is_toman:
                rate_data, error = await exchange_rates.get_currency_toman_rate(currency_slug)
                if error:
                    await processing_message.edit_text(f"❌ {error}")
                    return
                
                formatted_rate = exchange_rates.format_toman_rate(rate_data, currency_slug)
                await processing_message.edit_text(formatted_rate)
            else:
                rate_data, error = await exchange_rates.get_currency_rate(currency_slug)
                if error:
                    await processing_message.edit_text(f"❌ {error}")
                    return
                
                formatted_rate = exchange_rates.format_currency_rate(rate_data, currency_slug)
                await processing_message.edit_text(formatted_rate)
            
            return
        
        # Check if this is about gold prices
        elif exchange_rates.is_gold_price_request(query):
            processing_message = await update.message.reply_text("در حال دریافت قیمت طلا و سکه... ⌛")
            
            # Fetch gold prices
            gold_data, error = await exchange_rates.fetch_gold_prices()
            
            if error or not gold_data:
                await processing_message.edit_text(f"❌ {error}" if error else "❌ خطا در دریافت اطلاعات قیمت طلا و سکه.")
                return
            
            # Format the response
            formatted_response = exchange_rates.format_gold_prices(gold_data)
            
            # Send the formatted response
            await processing_message.edit_text(formatted_response)
            return
        
        # Check if this is about cryptocurrency prices
        elif exchange_rates.is_crypto_price_request(query):
            processing_message = await update.message.reply_text("در حال دریافت قیمت ارزهای دیجیتال... ⌛")
            
            # Detect specific cryptocurrency if mentioned
            specific_crypto = exchange_rates.detect_crypto_in_query(query)
            
            # Fetch crypto prices
            crypto_data, error = await exchange_rates.fetch_crypto_prices()
            
            if error or not crypto_data:
                await processing_message.edit_text(f"❌ {error}" if error else "❌ خطا در دریافت اطلاعات ارزهای دیجیتال.")
                return
            
            # Filter for specific cryptocurrency if detected in query
            if specific_crypto and 'data' in crypto_data:
                filtered_data = {
                    'data': [item for item in crypto_data['data'] 
                             if item.get('symbol', '').lower() == specific_crypto.lower()],
                    'updated_at': crypto_data.get('updated_at', 'نامشخص')
                }
                
                if filtered_data['data']:
                    formatted_response = exchange_rates.format_crypto_prices(filtered_data)
                else:
                    # If specific crypto not found, return all data
                    formatted_response = exchange_rates.format_crypto_prices(crypto_data)
            else:
                # Format the response with all cryptocurrencies
                formatted_response = exchange_rates.format_crypto_prices(crypto_data)
            
            # Send the formatted response
            await processing_message.edit_text(formatted_response)
            return
        
        # Check if this is an image generation request
        elif image_generator.is_image_generation_request(query):
            # Check if the user has reached the daily limit
            if not usage_limits.can_generate_image():
                await update.message.reply_text(
                    "متأسفانه به محدودیت روزانه ساخت تصویر رسیده‌اید (۳ بار در روز). لطفاً فردا دوباره امتحان کنید. 🖼️"
                )
                return
                
            # Extract the image prompt
            image_prompt = image_generator.extract_image_prompt(query)
            
            if not image_prompt:
                await update.message.reply_text(
                    "لطفاً توضیح دهید چه تصویری می‌خواهید بسازم. مثال: '@firtigh تصویر بساز از یک گربه ایرانی کنار حافظیه شیراز'"
                )
                return
                
            # Show a typing indicator while generating the image
            await update.message.reply_chat_action("typing")
            
            # Show that we're generating the image
            processing_message = await update.message.reply_text("در حال ساخت تصویر... ⌛")
            
            # Generate the image
            image_url, error = await image_generator.generate_image(image_prompt)
            
            if error or not image_url:
                await processing_message.edit_text(f"❌ {error if error else 'خطا در ساخت تصویر.'}")
                return
                
            try:
                # Increment usage counter
                usage_count = usage_limits.increment_image_gen_usage()
                remaining = 3 - usage_count  # 3 is the daily limit
                
                # Download the image
                response = requests.get(image_url)
                
                # Send the image with the prompt as caption
                await update.message.reply_photo(
                    photo=BytesIO(response.content),
                    caption=f"🖼️ تصویر ساخته شده بر اساس درخواست شما:\n\n«{image_prompt}»\n\n{remaining} بار دیگر می‌توانید امروز تصویر بسازید."
                )
                
                # Delete the processing message
                await processing_message.delete()
            except Exception as e:
                logger.error(f"Error sending generated image: {e}")
                await processing_message.edit_text(f"❌ خطا در ارسال تصویر: {str(e)}")
            
            return
        
        # Initialize variables for web search and link content
        search_results = None
        web_content = None
        is_news_query = False  # Initialize is_news_query variable
        
        # Check if this is a search request
        if await web_search.is_search_request(query):
            # Check if we've reached daily search limit
            if not usage_limits.can_perform_search():
                await update.message.reply_text(
                    "متأسفانه به محدودیت روزانه جستجوی اینترنت رسیده‌ایم. لطفا فردا دوباره امتحان کنید. 🔍"
                )
                return
                
            # Extract search query (remove search command keywords)
            search_keywords = ["جستجو", "search", "بگرد", "پیدا کن", "سرچ", "گوگل", "google"]
            search_query = query
            for keyword in search_keywords:
                search_query = search_query.replace(keyword, "").strip()
            
            if not search_query:
                await update.message.reply_text("لطفا عبارت جستجو را وارد کنید. مثلا: '@firtigh جستجو آخرین اخبار ایران'")
                return
            
            # Inform user that we're searching
            await update.message.reply_chat_action("typing")
            
            # Check if it's a news query
            is_news_query = await web_search.is_news_query(search_query)
            if is_news_query:
                await update.message.reply_text(f"در حال جستجوی اخبار برای: «{search_query}» در منابع خبری فارسی 📰")
            else:
                await update.message.reply_text(f"در حال جستجوی اینترنت برای: «{search_query}» 🔍")
            
            # Perform the search
            search_result_data = await web_search.search_web(search_query)
            search_results = web_search.format_search_results(search_result_data, is_news=is_news_query)
            
            # Increment search usage count
            usage_limits.increment_search_usage()
        
        # Process links in the message
        if message_text:
            logger.info("Checking for links in message")
            web_content = await web_extractor.process_message_links(message_text)
            if web_content:
                logger.info(f"Found and processed links in message. Content length: {len(web_content)}")
        
        # Continue with normal message processing
        # Get conversation context from reply chain
        conversation_context, media_data_list = await get_conversation_context(update, context)
        
        # Get sender info for the bot to address the user appropriately
        sender_info = ""
        user_id = None
        if update.message.from_user:
            user_id = update.message.from_user.id
            sender_name = ""
            # First try to get username
            if update.message.from_user.username:
                sender_name = update.message.from_user.username
            # If no username, try first name + last name
            elif update.message.from_user.first_name:
                sender_name = update.message.from_user.first_name
                if update.message.from_user.last_name:
                    sender_name += f" {update.message.from_user.last_name}"
            
            if sender_name:
                # Get Persian name if available
                persian_name = memory.get_persian_name(sender_name)
                
                sender_info = (
                    f"نام کاربر فرستنده پیام: {sender_name}\n"
                    f"نام فارسی کاربر (اگر موجود باشد): {persian_name}\n"
                    f"شناسه کاربر: {user_id}\n"
                    f"(لطفاً در پاسخ خود، کاربر را با نام فارسی او خطاب کنید. "
                    f"اگر نام فارسی او مشخص نیست، تلفظ صحیح فارسی نام او را حدس بزنید. "
                    f"برای مثال، 'Mohsen' را به 'محسن' و 'Ali' را به 'علی' تبدیل کنید. "
                    f"اگر نام او قبلاً تصحیح شده است، از همان نام تصحیح شده استفاده کنید.)\n"
                )
        
        # Initialize variables for handling media
        image_data = None
        has_media = False
        media_description = ""

        # Handle photos - add usage limits
        if update.message.photo:
            logger.info("Message contains photo")
            
            # Check if we've reached daily media processing limit
            if not usage_limits.can_process_media():
                await update.message.reply_text(
                    "متأسفانه به محدودیت روزانه پردازش تصاویر رسیده‌ایم. لطفا فردا دوباره امتحان کنید. 🖼️"
                )
                return
                
            has_media = True
            media_description = "[تصویر] "
            # Get the largest photo (last in the array)
            photo = update.message.photo[-1]
            image_data = await download_telegram_file(photo.file_id, context)
            
            # Increment media usage count if we successfully got the image
            if image_data:
                usage_limits.increment_media_usage()
        
        # Handle animations/GIFs - add usage limits
        elif update.message.animation:
            logger.info("Message contains animation/GIF")
            
            # Check if we've reached daily media processing limit
            if not usage_limits.can_process_media():
                await update.message.reply_text(
                    "متأسفانه به محدودیت روزانه پردازش تصاویر و ویدیوها رسیده‌ایم. لطفا فردا دوباره امتحان کنید. 🎬"
                )
                return
                
            has_media = True
            media_description = "[GIF/انیمیشن] "
            # Try to get a thumbnail or the animation itself
            if update.message.animation.thumbnail:
                image_data = await download_telegram_file(update.message.animation.thumbnail.file_id, context)
            else:
                image_data = await download_telegram_file(update.message.animation.file_id, context)
                
            # Increment media usage count if we successfully got the image
            if image_data:
                usage_limits.increment_media_usage()
        
        # Combine context with the query and media description
        if query:
            full_prompt = f"{conversation_context}{sender_info}پیام کاربر: {media_description}{query}"
        else:
            full_prompt = f"{conversation_context}{sender_info}پیام کاربر: {media_description}لطفا این را توصیف کن و نظرت را بگو"
        
        # Add context about it being a reply to the bot if applicable
        if is_reply_to_bot:
            full_prompt = f"{full_prompt}\n\n(این پیام مستقیما به پیام قبلی شما پاسخ داده شده است)"
            
        # Add context about it being an instruction if applicable
        if is_instruction:
            full_prompt = f"{full_prompt}\n\n(این پیام شامل دستورالعملی برای شماست که باید آن را به خاطر بسپارید و مطابق آن عمل کنید)"
        
        # Determine if the message is serious
        is_serious = await is_serious_question(query if query else "")
        
        # Log media info
        if has_media or (media_data_list and len(media_data_list) > 0):
            logger.info(f"Processing message with media. Current image: {bool(image_data)}, Context images: {len(media_data_list)}")
        
        # Extract media data from the media_data_list
        additional_images = None
        if media_data_list and len(media_data_list) > 0:
            additional_images = media_data_list
        
        # Generate and send AI response - now with chat_id and user_id for memory
        await update.message.reply_chat_action("typing")
        ai_response = await generate_ai_response(
            full_prompt, 
            is_serious, 
            image_data, 
            search_results, 
            web_content, 
            chat_id, 
            user_id, 
            additional_images
        )
        
        # Try to send with Markdown formatting, but fall back to plain text if there's an error
        message_sent = False
        try:
            # Check if the response contains links (markdown format)
            contains_links = re.search(r'\[([^\]]+)\]\(([^)]+)\)', ai_response) is not None
            
            # Special handling for responses with links or news queries to ensure links are clickable
            if contains_links or is_news_query:
                try:
                    # Use standard Markdown for responses with links to ensure links work
                    await update.message.reply_text(ai_response, parse_mode=ParseMode.MARKDOWN)
                    message_sent = True
                except Exception as e:
                    logger.error(f"Error sending response with links using Markdown: {e}")
                    # Try with HTML parsing instead which might handle links better
                    try:
                        # Convert markdown links to HTML links first (before other conversions)
                        html_response = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', ai_response)
                        
                        # Convert other markdown formatting to HTML
                        html_response = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', html_response)  # Bold **text**
                        html_response = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', html_response)      # Bold *text*
                        html_response = re.sub(r'\_([^_]+)\_', r'<i>\1</i>', html_response)      # Italic _text_
                        
                        # Send with HTML parsing
                        await update.message.reply_text(html_response, parse_mode=ParseMode.HTML)
                        message_sent = True
                    except Exception as e2:
                        logger.error(f"Error sending response with HTML: {e2}")
                        # Will fall back to plain text below if both approaches fail
            # Skip escape for messages that contain code blocks or complex formatting
            elif "```" in ai_response or "~~~" in ai_response:
                # Try sending with regular Markdown first
                await update.message.reply_text(ai_response, parse_mode=ParseMode.MARKDOWN)
                message_sent = True
            else:
                # Escape for MarkdownV2 and send
                escaped_response = escape_markdown_v2(ai_response)
                await update.message.reply_text(escaped_response, parse_mode=ParseMode.MARKDOWN_V2)
                message_sent = True
        except Exception as e:
            logger.error(f"Error sending formatted message: {e}")
            # Fall back to plain text with no formatting ONLY if the formatted message failed
            if not message_sent:
                await update.message.reply_text(ai_response)

async def dollar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /dollar command - Return current USD to IRR exchange rate
    """
    try:
        # Send a "typing" indicator to show the bot is processing
        await update.message.reply_chat_action("typing")
        
        # Get exchange rate from API
        result = await exchange_rates.get_usd_irr_rate()
        formatted_result = exchange_rates.format_exchange_rate_result(result)
        
        # Send the result
        await update.message.reply_text(
            formatted_result,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error processing dollar command: {str(e)}")
        await update.message.reply_text(
            f"خطا در دریافت نرخ ارز: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def toman_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /toman command - Return current USD to Toman exchange rate
    """
    try:
        # Send a "typing" indicator to show the bot is processing
        await update.message.reply_chat_action("typing")
        
        # Get exchange rate and convert to Toman
        result = await exchange_rates.get_usd_toman_rate()
        
        # Format the result
        if result.get("success", False):
            buy_rate = result.get("buy_rate", "N/A")
            sell_rate = result.get("sell_rate", "N/A")
            
            # Format numbers with commas
            try:
                buy_value = float(buy_rate)
                formatted_buy = f"{buy_value:,.0f}"
            except (ValueError, TypeError):
                formatted_buy = buy_rate
                
            try:
                sell_value = float(sell_rate)
                formatted_sell = f"{sell_value:,.0f}"
            except (ValueError, TypeError):
                formatted_sell = sell_rate
            
            # Create the formatted response
            formatted_result = (
                f"💵 *نرخ دلار آمریکا به تومان*\n\n"
                f"قیمت خرید: *{formatted_buy} تومان*\n"
                f"قیمت فروش: *{formatted_sell} تومان*\n"
                f"تغییرات: {result.get('change_percent', 'N/A')}\n"
                f"منبع: [alanchand.com]({result.get('source_url', 'https://alanchand.com/')})"
            )
        else:
            formatted_result = f"❌ خطا در دریافت نرخ ارز: {result.get('error', 'خطای نامشخص')}"
        
        # Send the result
        await update.message.reply_text(
            formatted_result,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error processing toman command: {str(e)}")
        await update.message.reply_text(
            f"خطا در دریافت نرخ ارز: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def currency_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /currency command - Return exchange rate for specified currency to IRR
    Usage: /currency [currency_code]
    Example: /currency eur (for Euro)
    """
    try:
        # Send a "typing" indicator to show the bot is processing
        await update.message.reply_chat_action("typing")
        
        # Check if there's a currency code specified
        currency_slug = "usd"  # Default to USD
        
        if context.args and len(context.args) > 0:
            # The first argument should be the currency code
            arg = context.args[0].lower()
            # Remove any non-alphanumeric characters
            currency_slug = ''.join(c for c in arg if c.isalnum())
        
        # Get exchange rate from API
        result = await exchange_rates.get_currency_rate(currency_slug)
        
        # Check if we want to display in Tomans
        use_toman = False
        if len(context.args) > 1 and context.args[1].lower() in ["toman", "تومان", "تومن"]:
            use_toman = True
            result = await exchange_rates.get_currency_toman_rate(currency_slug)
        
        # Format and send the result
        if use_toman:
            # Format the result for Toman display
            if result.get("success", False):
                buy_rate = result.get("buy_rate", "N/A")
                sell_rate = result.get("sell_rate", "N/A")
                currency_name = result.get("currency_name", currency_slug.upper())
                
                # Format numbers with commas
                try:
                    buy_value = float(buy_rate)
                    formatted_buy = f"{buy_value:,.0f}"
                except (ValueError, TypeError):
                    formatted_buy = buy_rate
                    
                try:
                    sell_value = float(sell_rate)
                    formatted_sell = f"{sell_value:,.0f}"
                except (ValueError, TypeError):
                    formatted_sell = sell_rate
                
                # Create the formatted response
                formatted_result = (
                    f"💵 *نرخ {currency_name} به تومان*\n\n"
                    f"قیمت خرید: *{formatted_buy} تومان*\n"
                    f"قیمت فروش: *{formatted_sell} تومان*\n"
                    f"تغییرات: {result.get('change_percent', 'N/A')}\n"
                    f"منبع: [alanchand.com]({result.get('source_url', 'https://alanchand.com/')})"
                )
            else:
                formatted_result = f"❌ خطا در دریافت نرخ ارز: {result.get('error', 'خطای نامشخص')}"
        else:
            # Format the result for Rial display
            formatted_result = exchange_rates.format_exchange_rate_result(result)
        
        # Send the result
        await update.message.reply_text(
            formatted_result,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error processing currency command: {str(e)}")
        await update.message.reply_text(
            f"خطا در دریافت نرخ ارز: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def gold_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command handler for /gold - Displays gold and coin prices
    """
    # Inform user that we're fetching data
    message = await update.message.reply_text("در حال دریافت قیمت طلا و سکه... ⌛")
    
    # Fetch gold prices
    gold_data, error = await exchange_rates.fetch_gold_prices()
    
    if error or not gold_data:
        await message.edit_text(f"❌ {error}" if error else "❌ خطا در دریافت اطلاعات قیمت طلا و سکه.")
        return
    
    # Format the response
    formatted_response = exchange_rates.format_gold_prices(gold_data)
    
    # Send the formatted response
    await message.edit_text(formatted_response)

async def crypto_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command handler for /crypto - Displays cryptocurrency prices
    """
    # Inform user that we're fetching data
    message = await update.message.reply_text("در حال دریافت قیمت ارزهای دیجیتال... ⌛")
    
    # Get specific cryptocurrency if provided in arguments
    args = context.args
    specific_crypto = None
    
    if args and len(args) > 0:
        specific_crypto = exchange_rates.detect_crypto_in_query(" ".join(args))
    
    # Fetch crypto prices
    crypto_data, error = await exchange_rates.fetch_crypto_prices()
    
    if error or not crypto_data:
        await message.edit_text(f"❌ {error}" if error else "❌ خطا در دریافت اطلاعات ارزهای دیجیتال.")
        return
    
    # Filter for specific cryptocurrency if requested
    if specific_crypto and 'data' in crypto_data:
        filtered_data = {
            'data': [item for item in crypto_data['data'] 
                     if item.get('symbol', '').lower() == specific_crypto.lower()],
            'updated_at': crypto_data.get('updated_at', 'نامشخص')
        }
        
        if not filtered_data['data']:
            await message.edit_text(f"❌ ارز دیجیتال {specific_crypto.upper()} در داده‌های دریافتی یافت نشد.")
            return
        
        formatted_response = exchange_rates.format_crypto_prices(filtered_data)
    else:
        # Format the response with all cryptocurrencies
        formatted_response = exchange_rates.format_crypto_prices(crypto_data)
    
    # Send the formatted response
    await message.edit_text(formatted_response)

def main() -> None:
    """Start the bot."""
    # Get the Telegram token from environment variable
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("No TELEGRAM_TOKEN environment variable found!")
        return

    # Ensure database is initialized
    database.initialize_database()
    
    # Initialize memory
    memory.initialize_memory()
    
    # Log configuration
    logger.info(f"Bot name: {BOT_NAME}")
    logger.info(f"Bot full name: {BOT_FULL_NAME}")
    logger.info(f"Memory capacity: {MAX_MEMORY_MESSAGES} messages")
    logger.info(f"Memory items per group: {memory.MAX_MEMORY_ITEMS_PER_GROUP}")
    logger.info(f"Using model for analysis: {memory.MODEL_FOR_ANALYSIS}")
    
    # Create the Application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dollar", dollar_command))
    application.add_handler(CommandHandler("toman", toman_command))
    application.add_handler(CommandHandler("currency", currency_command))
    application.add_handler(CommandHandler("gold", gold_command))
    application.add_handler(CommandHandler("crypto", crypto_command))
    # Process all messages to check for mentions
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Log startup
    logger.info("Bot started, waiting for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 