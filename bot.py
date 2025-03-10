# Standard library imports
import os
import time
import traceback
import re
import asyncio
import logging
import base64
import json
from typing import List, Optional
from datetime import datetime

# Third-party imports
from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    MessageHandler, 
    CommandHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler
)
from dotenv import load_dotenv

# Import custom modules
import config
import memory
import database
import token_tracking

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set up OpenAI API key
# Remove direct OpenAI import to avoid conflicts
# The openai_functions module will handle the API key setup
# openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants for enhanced memory
MAX_MEMORY_MESSAGES = 1000  # Maximum number of messages to remember
BOT_NAME = "فیرتیق"
BOT_FULL_NAME = "فیرتیق الله باقرزاده"
BOT_DESCRIPTION = "یک بات هوشمند برای کمک به گروه‌های فارسی زبان"
OPENAI_MODEL_DEFAULT = config.OPENAI_MODEL_DEFAULT
OPENAI_MODEL_VISION = config.OPENAI_MODEL_VISION

# Import from openai_functions after setting up compatibility
import openai_functions

# Track token usage (replaced with token_tracking module)
def log_token_usage(response, model, request_type):
    """Log token usage from OpenAI API response and save to token tracking database"""
    if openai_functions.is_new_openai:
        usage = response.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens
    else:
        usage = response.get('usage', {})
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)
    
    # Log to console    
    logger.info(f"Token Usage - {request_type} - {model}: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
    
    # Track in the token tracking database
    token_tracking.track_token_usage(
        model=model,
        request_type=request_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens
    )
    
    return prompt_tokens, completion_tokens, total_tokens

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
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def token_usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show token usage statistics for authorized users."""
    # Check if user is authorized (use admin user ID from config)
    user_id = update.effective_user.id
    admin_user_id = config.ADMIN_USER_ID
    
    # If admin user ID is not set or this user is the admin
    if not admin_user_id or str(user_id) == str(admin_user_id):
        # Get the command arguments
        args = context.args
        days = 30  # Default to 30 days
        
        # Parse days argument if provided
        if args and args[0].isdigit():
            days = int(args[0])
            days = max(1, min(days, 365))  # Limit to between 1 and 365 days
        
        # Generate the token usage report
        report = token_tracking.format_token_usage_report(days=days)
        
        # Send the report
        await update.message.reply_text(
            f"```\n{report}\n```",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        # Not authorized
        await update.message.reply_text(
            "این دستور فقط برای مدیران سیستم در دسترس است.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def generate_ai_response(
    prompt: str,
    is_serious: bool = False,
    chat_id: Optional[int] = None,
    user_id: Optional[int] = None,
    memory_context: Optional[str] = None,
    user_profile_context: Optional[str] = None,
    media_data: Optional[bytes] = None,
    additional_images: Optional[List[bytes]] = None,
    conversation_context: Optional[str] = None
) -> str:
    """
    Generate a response using the OpenAI API, with function calling support.
    
    Args:
        prompt: The user's message
        is_serious: Whether this is a serious conversation requiring formal tone
        chat_id: The chat ID for context-specific functions
        user_id: The user ID for user-specific functions
        memory_context: Context from memory for the conversation
        user_profile_context: User profile context
        media_data: Binary data of media (image, etc.)
        additional_images: List of additional image data to include in the context
        conversation_context: Context from the current conversation thread
        
    Returns:
        The generated response
    """
    try:
        # Get memory context if not provided
        if not memory_context and chat_id:
            # Remove the limit parameter to be compatible with the deployed version
            memory_context = await memory.get_relevant_memory(chat_id, prompt)
            
        # Get user profile context if not provided
        if not user_profile_context and chat_id and user_id:
            user_profile_context = memory.get_user_profile_context(chat_id, user_id)
        
        # Determine if we need the vision model based on media data
        use_vision = bool(media_data) or bool(additional_images)
        
        # Prepare the system message that initializes the bot's behavior
        system_message = f"""
تو یک ربات هوشمند فارسی‌زبان هستی که می‌توانی با کاربران به شکل طبیعی و دوستانه صحبت کنی.

دستورالعمل‌های مهم:
- *همیشه به فارسی و با لحن شخصی پاسخ بده* و مستقیماً با کاربر صحبت کن.
- از فرمت‌بندی متن (مثل **تاکید**، *ایتالیک*) و ایموجی‌های مناسب استفاده کن.
- به سوالات با صداقت پاسخ بده و اگر چیزی را نمی‌دانی، صادقانه بگو.
- در مکالمات، هویت خود را حفظ کن و به‌یاد داشته باش که یک ربات هوشمند هستی.
- شخصیت دوستانه، خوش‌برخورد و کمی شوخ‌طبع خود را حفظ کن.
- وقتی به منابع یا مطالب خارجی اشاره می‌کنی، لینک مستقیم و کامل آنها را در پاسخت بگنجان.
- اسامی انگلیسی را به فارسی ترجمه کن (مثل "نیویورک" به جای "New York").
- اعداد را به فارسی بنویس (مثل "۱۲۳" به جای "123").
- از فاصله‌گذاری درست کلمات فارسی استفاده کن.
- نقطه‌گذاری فارسی را رعایت کن (ویرگول، نقطه، علامت سوال، etc.).
- به دانش‌هایی که داری متکی باش، اما برای اطلاعات به‌روز، جستجوی وب، و استخراج محتوا از لینک‌ها، از توابع مربوطه استفاده کن.
"""

        # Add memory context if available
        # if memory_context:
        #    system_message += f"\n\nاطلاعات حافظه:\n{memory_context}"
            
        # Add user profile context if available
        if user_profile_context:
            system_message += f"\n\nپروفایل کاربر:\n{user_profile_context}"

        # Prepare the messages array
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Add conversation context if available
        if conversation_context:
            # Add conversation context as a separate system message for clarity
            messages.append({
                "role": "system", 
                "content": f"سابقه گفتگو (رشته‌ای از پیام‌های قبلی که باید در نظر بگیری):\n{conversation_context}"
            })
            
        # Add the user's current message
        messages.append({"role": "user", "content": prompt})

        # Handle content based on whether we need vision
        if use_vision:
            # Use the vision model for image analysis
            try:
                content = []
                
                # Add the text part
                content.append({"type": "text", "text": prompt})
                
                # Add the main image if available
                if media_data:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64.b64encode(media_data).decode('utf-8')}"
                        }
                    })
                
                # Add additional images if available
                if additional_images:
                    for img_data in additional_images:
                        content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64.b64encode(img_data).decode('utf-8')}"
                            }
                        })
                
                # Use the GPT-4 Vision model with appropriate client version
                if openai_functions.is_new_openai:
                    response = openai_functions.openai_client.chat.completions.create(
                        model="gpt-4-vision-preview",
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": content}
                        ],
                        max_tokens=1000,
                        temperature=0.7
                    )
                    # Log token usage
                    log_token_usage(response, "gpt-4-vision-preview", "Vision API")
                else:
                    response = await openai_functions.openai_client.ChatCompletion.acreate(
                        model="gpt-4-vision-preview",
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": content}
                        ],
                        max_tokens=1000,
                        temperature=0.7
                    )
                    # Log token usage
                    log_token_usage(response, "gpt-4-vision-preview", "Vision API")
                
                if openai_functions.is_new_openai:
                    return response.choices[0].message.content
                else:
                    return response.choices[0].message.content
                
            except Exception as e:
                logger.error(f"Error in vision API call: {e}", exc_info=True)
                return "متأسفانه در پردازش تصویر مشکلی پیش آمد. لطفاً دوباره تلاش کنید."
                
        else:
            # Use the standard model with function calling
            try:
                # Import the function definitions
                from openai_functions import FUNCTION_DEFINITIONS, process_function_calls
                
                # Make the API call with function definitions based on client version
                if openai_functions.is_new_openai:
                    response = openai_functions.openai_client.chat.completions.create(
                        model="gpt-4-turbo",
                        messages=messages,
                        functions=FUNCTION_DEFINITIONS,
                        function_call="auto",
                        max_tokens=1000,
                        temperature=0.7
                    )
                    # Log token usage
                    log_token_usage(response, "gpt-4-turbo", "Function Calling API")
                else:
                    response = await openai_functions.openai_client.ChatCompletion.acreate(
                        model="gpt-4-turbo",
                        messages=messages,
                        functions=FUNCTION_DEFINITIONS,
                        function_call="auto",
                        max_tokens=1000,
                        temperature=0.7
                    )
                    # Log token usage
                    log_token_usage(response, "gpt-4-turbo", "Function Calling API")
                
                if openai_functions.is_new_openai:
                    response_message = response.choices[0].message
                else:
                    response_message = response.choices[0].message
                
                # Check if the response includes a function call
                has_function_call = (
                    hasattr(response_message, 'function_call') and response_message.function_call or
                    hasattr(response_message, 'tool_calls') and response_message.tool_calls
                )
                
                if has_function_call:
                    # Process the function calls
                    function_result = await process_function_calls(response_message, chat_id, user_id)
                    
                    if function_result:
                        # Add the function result to our conversation and call the API again
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "function_call": response_message.function_call if hasattr(response_message, 'function_call') else None,
                            "tool_calls": response_message.tool_calls if hasattr(response_message, 'tool_calls') else None
                        })
                        
                        # Add the function result as a new message
                        if hasattr(response_message, 'function_call'):
                            messages.append({
                                "role": "function",
                                "name": response_message.function_call.name,
                                "content": function_result
                            })
                        else:
                            # For tool_calls format
                            for tool_call in response_message.tool_calls:
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": function_result
                                })
                        
                        # Call the API again with the function result
                        if openai_functions.is_new_openai:
                            second_response = openai_functions.openai_client.chat.completions.create(
                                model="gpt-4-turbo",
                                messages=messages,
                                max_tokens=1000,
                                temperature=0.7
                            )
                            # Log token usage
                            log_token_usage(second_response, "gpt-4-turbo", "Function Response API")
                        else:
                            second_response = await openai_functions.openai_client.ChatCompletion.acreate(
                                model="gpt-4-turbo",
                                messages=messages,
                                max_tokens=1000,
                                temperature=0.7
                            )
                            # Log token usage
                            log_token_usage(second_response, "gpt-4-turbo", "Function Response API")
                        
                        if openai_functions.is_new_openai:
                            return second_response.choices[0].message.content
                        else:
                            return second_response.choices[0].message.content
                    
                    # If function execution failed but returned a message
                    return function_result if function_result else "متأسفانه در پردازش درخواست شما مشکلی پیش آمد."
                
                # If no function call, just return the response content
                return response_message.content
                
            except Exception as e:
                logger.error(f"Error in OpenAI API call: {e}", exc_info=True)
                return "متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید."
                
    except Exception as e:
        logger.error(f"Error generating AI response: {e}", exc_info=True)
        return "متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید."

 
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

async def get_conversation_context(update: Update, context: ContextTypes.DEFAULT_TYPE, depth=5):
    """
    Get the conversation context from the message and its reply chain.
    Handles multiple levels of replies to capture the full conversation thread.
    
    Args:
        update: The update object
        context: The context object
        depth: Maximum depth of the reply chain to follow
        
    Returns:
        Tuple of (context_text, media_data_list, has_context)
    """
    context_messages = []
    media_data_list = []
    has_context = False
    
    # Start with the current message
    current_message = update.message
    current_depth = 0
    processed_message_ids = set()  # Track processed messages to avoid duplicates
    
    # Process the main message chain first
    main_chain_messages = []
    reply_chain = []
    
    # Function to process a message and its media
    async def process_message(message, sender_name):
        nonlocal media_data_list
        
        # Skip if we've already processed this message
        if message.message_id in processed_message_ids:
            return None
            
        processed_message_ids.add(message.message_id)
        
        # Extract media information
        media_type, media_description, media_data = await extract_media_info(message, context)
        
        # Construct message content
        message_content = ""
        if message.text:
            message_content += message.text
        
        # Add media description if available
        if media_description:
            if message_content:
                message_content += f" {media_description}"
            else:
                message_content = media_description
                
        # If media data was extracted, add it to our list
        if media_data:
            media_data_list.append({
                "type": media_type,
                "data": media_data,
                "sender": sender_name
            })
            
        # Return formatted message if it has content
        if message_content:
            return f"{sender_name}: {message_content}"
        return None
    
    # Process the current message first
    sender_name = "User"
    if current_message.from_user:
        if current_message.from_user.username:
            sender_name = f"@{current_message.from_user.username}"
        elif current_message.from_user.first_name:
            sender_name = current_message.from_user.first_name
    
    # Process the main message
    msg_text = await process_message(current_message, sender_name)
    if msg_text:
        main_chain_messages.append(msg_text)
    
    # Process the entire reply chain
    while current_message and current_message.reply_to_message and current_depth < depth:
        current_depth += 1
        replied_to = current_message.reply_to_message
        
        # Get sender info for the replied-to message
        sender_name = "someone"
        if replied_to.from_user:
            if replied_to.from_user.username:
                sender_name = f"@{replied_to.from_user.username}"
            elif replied_to.from_user.first_name:
                sender_name = replied_to.from_user.first_name
        
        # Process this message in the reply chain
        msg_text = await process_message(replied_to, sender_name)
        if msg_text:
            reply_chain.append(msg_text)
        
        # Move up the chain
        current_message = replied_to
    
    # Now get broader context from recent messages in the chat (not just the reply chain)
    if update.message.chat.type != 'private':
        # Use bot data to access recent messages
        chat_id = update.message.chat_id
        if not context.bot_data.get('recent_messages'):
            context.bot_data['recent_messages'] = {}
        
        if not context.bot_data['recent_messages'].get(chat_id):
            context.bot_data['recent_messages'][chat_id] = []
        
        recent_messages = context.bot_data['recent_messages'][chat_id]
        
        # Add any recent messages that aren't in the reply chain and have the bot mentioned
        # or are from the bot (to provide additional context)
        for msg in recent_messages[-10:]:  # Last 10 messages for context
            # Skip messages already processed in the reply chain
            if msg.get('message_id') in processed_message_ids:
                continue
                
            sender = msg.get('sender', 'someone')
            text = msg.get('text', '')
            
            # Only include messages that mention the bot or are from the bot
            bot_username = context.bot.username
            if (f"@{bot_username}" in text or BOT_NAME in text or 
                sender == f"@{bot_username}" or 'is_bot_message' in msg):
                context_messages.append(f"{sender}: {text}")
                has_context = True
    
    # If we have a reply chain, add it in chronological order to the context
    if reply_chain:
        # Add the replies in chronological order (oldest first)
        context_messages.extend(reversed(reply_chain))
        has_context = True
    
    # Add the current message at the end
    context_messages.extend(main_chain_messages)
    
    # Prepare the final context text
    if context_messages:
        context_text = "\n".join(context_messages)
    else:
        context_text = ""
    
    return context_text, media_data_list, has_context

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

def to_persian_numbers(text: str) -> str:
    """
    Convert English digits in a string to Persian digits.
    
    Args:
        text (str): The text containing English digits
        
    Returns:
        str: The text with English digits replaced by Persian digits
    """
    persian_digits = {
        '0': '۰',
        '1': '۱',
        '2': '۲',
        '3': '۳',
        '4': '۴',
        '5': '۵',
        '6': '۶',
        '7': '۷',
        '8': '۸',
        '9': '۹',
        ',': '،',
        '.': '٫'  # Persian decimal separator
    }
    
    for english, persian in persian_digits.items():
        text = text.replace(english, persian)
    
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    # Skip updates without messages
    if not update.message or not update.message.chat:
        return
        
    # Extract basic message info
    message = update.message
    chat_id = message.chat_id
    user_id = message.from_user.id if message.from_user else None
    message_text = message.text or ""
    
    # Store this message in the recent messages list for context
    if not context.bot_data.get('recent_messages'):
        context.bot_data['recent_messages'] = {}
        
    if not context.bot_data['recent_messages'].get(chat_id):
        context.bot_data['recent_messages'][chat_id] = []
        
    # Add the message to the recent messages list
    context.bot_data['recent_messages'][chat_id].append({
        'message_id': message.message_id,
        'sender': f"@{message.from_user.username}" if message.from_user and message.from_user.username else 
                  message.from_user.first_name if message.from_user else "someone",
        'text': message_text,
        'timestamp': datetime.now().timestamp()
    })
    
    # Limit the size of the recent messages list
    if len(context.bot_data['recent_messages'][chat_id]) > 50:  # Keep the last 50 messages
        context.bot_data['recent_messages'][chat_id] = context.bot_data['recent_messages'][chat_id][-50:]
        
    # Check if the bot was mentioned or replied to
    bot_username = context.bot.username
    is_mentioned = f"@{bot_username}" in message_text or BOT_NAME in message_text
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.username == bot_username
    is_private_chat = message.chat.type == 'private'
    
    # Process the message if the bot was mentioned, replied to, or in a private chat
    if is_mentioned or is_reply_to_bot or is_private_chat:
        # Log which condition triggered the bot
        if is_mentioned:
            logger.info(f"Bot mentioned in message: {message_text}")
        elif is_reply_to_bot:
            logger.info(f"User replied to bot's message: {message_text}")
        else:
            logger.info(f"Message in private chat: {message_text}")
            
        # Extract conversation context (including reply chain and recent mentions)
        context_text, media_data_list, has_context = await get_conversation_context(update, context)
        if has_context:
            logger.info(f"Found conversation context: {context_text[:100]}...")
            
        # Tell the user we're processing their message
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        
        # Process any attached media
        media_data = None
        additional_images = []
        
        # Extract media directly from the current message
        media_type, media_description, extracted_media_data = await extract_media_info(message, context)
        if extracted_media_data:
            media_data = extracted_media_data
            
            # Add any media description to the message text
            if media_description and not media_description in message_text:
                if message_text:
                    message_text += f" {media_description}"
                else:
                    message_text = media_description
        
        # Add any additional images from the conversation context
        if media_data_list:
            for item in media_data_list:
                if item["data"] and item["data"] != media_data:  # Don't duplicate the main image
                    additional_images.append(item["data"])
        
        # Clean up the prompt to remove bot mentions
        prompt = message_text.replace(f"@{bot_username}", "").replace(BOT_NAME, "").strip()
        if not prompt:
            prompt = "سلام!"  # Default prompt if only the bot's name was mentioned
            
        # Get memory context
        memory_context = await memory.get_relevant_memory(chat_id, prompt)
        if memory_context:
            # Use the process_message_for_memory function instead of add_to_memory
            message_data = {
                "message_id": message.message_id,
                "chat_id": chat_id,
                "sender_id": user_id,
                "sender_name": message.from_user.username or message.from_user.first_name if message.from_user else "Unknown",
                "text": prompt,
                "date": time.time()
            }
            # Process the message in the background
            asyncio.create_task(memory.process_message_for_memory(message_data))
            
        # Get user profile context
        user_profile_context = memory.get_user_profile_context(chat_id, user_id) if user_id else None
            
        # Generate the response
        response = await generate_ai_response(
            prompt=prompt,
            chat_id=chat_id,
            user_id=user_id,
            memory_context=memory_context,
            user_profile_context=user_profile_context,
            media_data=media_data,
            additional_images=additional_images if additional_images else None,
            conversation_context=context_text if has_context else None
        )
        
        # Send the response
        sent_message = await context.bot.send_message(
            chat_id=chat_id, 
            text=response,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Store the bot's response in recent messages with a special flag
        context.bot_data['recent_messages'][chat_id].append({
            'message_id': sent_message.message_id,
            'sender': f"@{bot_username}",
            'text': response,
            'timestamp': datetime.now().timestamp(),
            'is_bot_message': True
        })
        
        # Store the bot's response in memory
        # Instead of using add_to_memory, use process_message_for_memory
        bot_message_data = {
            "message_id": sent_message.message_id,
            "chat_id": chat_id,
            "sender_id": context.bot.id,
            "sender_name": bot_username,
            "text": response,
            "date": time.time(),
            "is_bot_message": True  # Mark as bot message
        }
        # Process the bot's response in the background
        asyncio.create_task(memory.process_message_for_memory(bot_message_data))

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
    application = ApplicationBuilder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("token_usage", token_usage_command))
    # Process all messages to check for mentions
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Log startup
    logger.info("Bot started, waiting for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 