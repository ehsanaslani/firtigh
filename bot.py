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
BOT_FULL_NAME = "فیرتیق فرتوقی"
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
        f"سلام {user.mention_html()}! من {BOT_FULL_NAME} هستم. برای حرف زدن با من، من رو با @firtigh یا {BOT_NAME} در پیام خود تگ کنید."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """🤖 *راهنمای دستورات*

/start - شروع کار با ربات
/help - نمایش این پیام راهنما
/token_usage - آمار مصرف توکن (مخصوص مدیران)

برای استفاده از ربات کافیست سوال خود را بپرسید یا @BotName را در گفتگو‌های گروهی منشن کنید.
"""
    # Use standard Markdown mode (not V2) which is simpler and less strict with escaping
    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        # Fall back to plain text if any errors
        logger.error(f"Error sending help with Markdown: {e}")
        plain_text = help_text.replace('*', '')  # Remove markdown symbols
        await update.message.reply_text(plain_text, parse_mode=None)

async def token_usage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show token usage statistics for authorized users."""
    # Check if user is authorized (use admin user ID from config)
    user_id = update.effective_user.id
    admin_user_id = config.ADMIN_USER_ID
    
    # If admin user ID is not set or this user is the admin
    #if not admin_user_id or str(user_id) == str(admin_user_id):
    if True:
        # Get the command arguments
        args = context.args
        days = 30  # Default to 30 days
        
        # Parse days argument if provided
        if args and args[0].isdigit():
            days = int(args[0])
            days = max(1, min(days, 365))  # Limit to between 1 and 365 days
        
        # Generate the token usage report
        report = token_tracking.format_token_usage_report(days=days)
        
        # Send as plain text with no Markdown formatting to avoid escaping issues
        await update.message.reply_text(
            f"Token Usage Report ({days} days):\n\n{report}",
            parse_mode=None  # No parsing, just plain text
        )
    else:
        # Not authorized - for this short message, escaping is simpler
        try:
            await update.message.reply_text(
                "این دستور فقط برای مدیران سیستم در دسترس است\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception:
            # Fallback to plain text if any error
            await update.message.reply_text(
                "این دستور فقط برای مدیران سیستم در دسترس است.",
                parse_mode=None
            )

    optimize_text = """✅ *بهینه‌سازی مصرف توکن*

ربات از چندین روش برای کاهش مصرف توکن استفاده می‌کند:

1️⃣ *پیام سیستمی مختصر*: کاهش طول دستورالعمل‌های راهنما
2️⃣ *طبقه‌بندی پیام‌ها*: پرس‌وجوهای ساده زمینه غیرضروری را بارگذاری نمی‌کنند
3️⃣ *انتخاب پویای توابع*: فقط توابع مرتبط با هر درخواست ارسال می‌شوند
4️⃣ *محدودیت زمینه*: تاریخچه مکالمه کوتاه می‌شود
5️⃣ *فشرده‌سازی پروفایل*: پروفایل‌های کاربر خلاصه می‌شوند

این بهینه‌سازی‌ها مصرف توکن را تا ۹۰٪ کاهش داده‌اند!

اطلاعات بیشتر: فایل README_TokenOptimization.md
"""
    # Note: We're using ParseMode.MARKDOWN (not V2) which has less strict escape requirements
    # but is also less powerful. This is OK for this simple formatting.
    try:
        await update.message.reply_text(optimize_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        # If Markdown parsing fails for some reason, fall back to plain text
        logger.error(f"Error sending formatted token optimization info: {e}")
        # Strip markdown symbols for plain text
        plain_text = optimize_text.replace('*', '').replace('_', '')
        await update.message.reply_text(plain_text, parse_mode=None)

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
        # Simple message classification to determine context needs
        is_greeting = any(greeting in prompt.lower() for greeting in ["سلام", "درود", "خوبی", "چطوری", "hello", "hi"])
        is_short_query = len(prompt.split()) < 6
        needs_full_context = not (is_greeting and is_short_query)
        
        # Get memory context if not provided and needed
        if not memory_context and chat_id and needs_full_context:
            memory_context = await memory.get_relevant_memory(chat_id, prompt)
            
        # Get user profile context if not provided and needed
        if not user_profile_context and chat_id and user_id and needs_full_context:
            user_profile_context = memory.get_user_profile_context(chat_id, user_id)
        
        # Determine if we need the vision model based on media data
        use_vision = bool(media_data) or bool(additional_images)
        
        # Use a more concise system message to reduce token usage
        system_message = """
شما عضوی از یک گروه تلگرامی فارسی‌زبان هستید:
• همیشه به فارسی پاسخ دهید، از ایموجی استفاده کنید، اعداد و اسامی را فارسی بنویسید
• شخصیت رک و صریح داشته باشید، نظرات خود را بیان کنید و با نظرات نادرست مخالفت کنید
• اگر کسی با شما با لحن توهین‌آمیز صحبت کند، با همان لحن پاسخ دهید
• از اسامی افراد در پاسخ‌هایتان استفاده کنید و اسامی غیرفارسی را به فارسی بنویسید
• برای اطلاعات به‌روز یا موضوعاتی که نمی‌دانید، از توابع جستجو استفاده کنید
• پیام‌ها و پست‌های گروه را تحلیل و بررسی کنید و نظر خود را درباره  موضوع و محتوای مورد بحث بگویید
• اگر پاسخ سوالی را نمی‌دانید، صادقانه آن را بیان کنید
"""

        # Adjust system message based on conversation tone
        if is_serious:
            system_message += " لحن رسمی و ساده داشته باش."
            
        # Add user profile context if available and needed (in compressed form)
        if user_profile_context and needs_full_context:
            # Compress user profile to include only essential information
            compressed_profile = compress_user_profile(user_profile_context)
            system_message += f"\n\nپروفایل کاربر: {compressed_profile}"

        # Prepare the messages array
        messages = [
            {"role": "system", "content": system_message}
        ]
        
        # Add conversation context if available and needed
        if conversation_context and needs_full_context:
            # Truncate conversation context to reduce token usage
            truncated_context = truncate_context(conversation_context, max_length=2000)
            
            messages.append({
                "role": "system", 
                "content": f"سابقه گفتگو:\n{truncated_context}"
            })
            
        # Add the user's current message
        messages.append({"role": "user", "content": prompt})

        # Handle content based on whether we need vision
        if use_vision:
            # Use the vision model for image analysis
            try:
                content = []
                
                # Add text content
                content.append({
                    "type": "text", 
                    "text": prompt
                })
                
                # Add the first image if valid
                if media_data is not None:
                    try:
                        # Ensure media_data is bytes
                        if isinstance(media_data, bytes):
                            content.append({
                    "type": "image_url",
                    "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64.b64encode(media_data).decode('utf-8')}"
                    }
                })
                        else:
                            logger.error(f"Invalid media_data type: {type(media_data)}, expected bytes")
                    except Exception as e:
                        logger.error(f"Error encoding main image: {e}", exc_info=True)
                        # Don't add if invalid
            
                # Add additional images if available
                if additional_images:
                    for img_data in additional_images:
                        if img_data is not None:
                            try:
                                # Ensure img_data is bytes
                                if isinstance(img_data, bytes):
                                    content.append({
                            "type": "image_url",
                            "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64.b64encode(img_data).decode('utf-8')}"
                                        }
                                    })
                                else:
                                    logger.warning(f"Skipping non-bytes additional image of type: {type(img_data)}")
                            except Exception as e:
                                logger.error(f"Error encoding additional image: {e}", exc_info=True)
                                # Skip this image if invalid
                
                # Make sure we have at least one image, otherwise use standard model
                has_image = any(item.get("type") == "image_url" for item in content)
                
                if not has_image:
                    # Fall back to text-only model if no valid images
                    logger.warning("Vision requested but no valid images found, falling back to text-only model")
                    use_vision = False
                    # Continue with standard model below
                else:
                    # Use the GPT-4 Vision model with appropriate client version
                    if openai_functions.is_new_openai:
                        response = openai_functions.openai_client.chat.completions.create(
                            model=OPENAI_MODEL_VISION,
                            messages=[
                                {"role": "system", "content": system_message},
                                {"role": "user", "content": content}
                            ],
                            max_tokens=800,  # Reduced from 1000
                            temperature=0.7
                        )
                        # Log token usage
                        log_token_usage(response, OPENAI_MODEL_VISION, "Vision API")
                    else:
                        response = await openai_functions.openai_client.ChatCompletion.acreate(
                            model=OPENAI_MODEL_VISION,
                            messages=[
                                {"role": "system", "content": system_message},
                                {"role": "user", "content": content}
                            ],
                            max_tokens=800,  # Reduced from 1000
                            temperature=0.7
                        )
                        # Log token usage
                        log_token_usage(response, OPENAI_MODEL_VISION, "Vision API")
                    
                    if openai_functions.is_new_openai:
                        return response.choices[0].message.content
                    else:
                        return response.choices[0].message.content
                
            except Exception as e:
                logger.error(f"Error in vision API call: {e}", exc_info=True)
                return "متأسفانه در پردازش تصویر مشکلی پیش آمد. لطفاً دوباره تلاش کنید."
                
        # If vision failed or was not requested, use the standard model
        if not use_vision:
            # Use the standard model with function calling
            try:
                # Import the function definitions and select only necessary ones
                from openai_functions import FUNCTION_DEFINITIONS, process_function_calls, select_relevant_functions
                
                # Select only the relevant functions (always including search_web)
                selected_functions = select_relevant_functions(prompt, must_include=["search_web"])
                
                # Choose the model based on query complexity
                model_to_use = OPENAI_MODEL_DEFAULT
                
                # Make the API call with function definitions based on client version
                if openai_functions.is_new_openai:
                    response = openai_functions.openai_client.chat.completions.create(
                        model=model_to_use,
                        messages=messages,
                        functions=selected_functions,
                        function_call="auto",
                        max_tokens=800,  # Reduced from 1000
                        temperature=0.7
                    )
                    # Log token usage
                    log_token_usage(response, model_to_use, "Function Calling API")
                else:
                    response = await openai_functions.openai_client.ChatCompletion.acreate(
                        model=model_to_use,
                        messages=messages,
                        functions=selected_functions,
                        function_call="auto",
                        max_tokens=800,  # Reduced from 1000
                        temperature=0.7
                    )
                    # Log token usage
                    log_token_usage(response, model_to_use, "Function Calling API")
                
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
                                model=model_to_use,
            messages=messages,
                                max_tokens=800,  # Reduced from 1000
                                temperature=0.7
                            )
                            # Log token usage
                            log_token_usage(second_response, model_to_use, "Function Response API")
                        else:
                            second_response = await openai_functions.openai_client.ChatCompletion.acreate(
                                model=model_to_use,
                                messages=messages,
                                max_tokens=800,  # Reduced from 1000
                                temperature=0.7
                            )
                            # Log token usage
                            log_token_usage(second_response, model_to_use, "Function Response API")
                        
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
        logger.error(f"Unexpected error in generate_ai_response: {e}", exc_info=True)
        return "خطایی در پردازش پیام رخ داد. لطفاً دوباره تلاش کنید."

def compress_user_profile(profile_text: str) -> str:
    """Compress user profile to reduce token usage"""
    # Extract only the most important parts of the profile
    lines = profile_text.split('\n')
    compressed_lines = []
    
    # Take only the first line (username) and max 3 attribute lines
    if lines:
        compressed_lines.append(lines[0])  # Username line
        
    attribute_count = 0
    for line in lines[1:]:
        if line.startswith('- ') and attribute_count < 3:
            compressed_lines.append(line)
            attribute_count += 1
    
    return '\n'.join(compressed_lines)

def truncate_context(context: str, max_length: int = 1000) -> str:
    """Truncate conversation context to reduce token usage"""
    # If context is already short enough, return as is
    if len(context) <= max_length:
        return context
    
    # Split by lines to keep whole messages
    lines = context.split('\n')
    
    # If there are too many lines, keep only the most recent ones
    if len(lines) > 10:
        # Keep first line which might have header information
        truncated_lines = [lines[0]]
        
        # Add an indicator that content was truncated
        truncated_lines.append("... (بخشی از مکالمه حذف شده) ...")
        
        # Add the most recent messages prioritizing context
        truncated_lines.extend(lines[-8:])
        
        return '\n'.join(truncated_lines)
    
    # Otherwise truncate by character count
    return "... " + context[-(max_length-4):]

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
    Get the conversation context from the message and its reply chain.
    Handles multiple levels of replies to capture the full conversation thread.
    Optimized to reduce token usage.
    
    Args:
        update: The update object
        context: The context object
        depth: Maximum depth of the reply chain to follow (reduced from 5 to 3)
    
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
            # Truncate very long messages
            if len(message.text) > 200:
                message_content = message.text[:197] + "..."
            else:
                message_content = message.text
        
        # Add media description if available
        if media_description:
            if message_content:
                message_content += f" {media_description}"
            else:
                message_content = media_description
                
        # If media data was extracted, add it to our list
        if media_data:
            # Make sure we're adding raw bytes, not a string
            if isinstance(media_data, bytes):
                media_data_list.append(media_data)
            elif isinstance(media_data, str):
                logger.warning("Media data is a string, which will cause encoding errors. Skipping.")
            else:
                logger.warning(f"Unexpected media data type: {type(media_data)}. Skipping.")
        
        # Return formatted message if it has content
        if message_content:
            # Use a more compact format for messages
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
    # Limit to fewer recent messages
    if update.message.chat.type != 'private':
        # Use bot data to access recent messages
        chat_id = update.message.chat_id
        if not context.bot_data.get('recent_messages'):
            context.bot_data['recent_messages'] = {}
        
        if not context.bot_data['recent_messages'].get(chat_id):
            context.bot_data['recent_messages'][chat_id] = []
        
        # Get recent messages (excluding the current one)
        recent_messages = [
            msg for msg in context.bot_data['recent_messages'][chat_id]
            if msg.get('message_id') != update.message.message_id
        ]
        
        # Limit to only the 3 most recent messages (reduced from 5)
        for recent_msg in recent_messages[-3:]:
            sender_name = recent_msg.get('sender_name', 'someone')
            message_text = recent_msg.get('text', '')
            
            # Truncate long messages
            if len(message_text) > 150:
                message_text = message_text[:147] + "..."
                
            if message_text and message_text not in [m.split(': ', 1)[1] for m in context_messages if ': ' in m]:
                context_messages.append(f"{sender_name}: {message_text}")
    
    # Add the current message to recent messages for future reference
    if update.message.chat.type != 'private':
        chat_id = update.message.chat_id
        
        # Store the message in a compact format
        msg_data = {
            'message_id': update.message.message_id,
            'sender_name': sender_name,
            'text': update.message.text or '',
            'timestamp': update.message.date.timestamp()
        }
        
        # Add to recent messages
        context.bot_data['recent_messages'][chat_id].append(msg_data)
        
        # Keep only the 10 most recent messages (reduced from 20)
        if len(context.bot_data['recent_messages'][chat_id]) > 10:
            context.bot_data['recent_messages'][chat_id] = context.bot_data['recent_messages'][chat_id][-10:]
    
    # Combine all message sources (reversed reply chain + recent context + current message)
    all_messages = reply_chain[::-1] + context_messages + main_chain_messages
    
    # Deduplicate messages while preserving order
    seen = set()
    unique_messages = []
    for msg in all_messages:
        if msg not in seen:
            seen.add(msg)
            unique_messages.append(msg)
    
    # Check if we have any context
    has_context = len(unique_messages) > 1
    
    # Format the final context text
    context_text = "\n".join(unique_messages)
    
    # If no media data, set to empty list
    if not media_data_list:
        media_data_list = []
        
    return (context_text, media_data_list, has_context)

async def download_telegram_file(file_id, context):
    """Download a Telegram file and return the raw bytes."""
    try:
        file = await context.bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        
        # Return the raw bytes instead of base64 encoding
        return bytes(file_bytes)
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
            # media_data_list is already a list of binary data, not dictionaries
            for additional_image_data in media_data_list:
                # Skip if it's None or identical to the main image
                if additional_image_data is not None and additional_image_data != media_data:
                    # Verify it's bytes before adding
                    if isinstance(additional_image_data, bytes):
                        additional_images.append(additional_image_data)
                    else:
                        logger.warning(f"Skipping non-bytes additional image of type: {type(additional_image_data)}")
        
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