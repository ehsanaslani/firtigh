# Standard library imports
import os
import time
import traceback
import re
import asyncio
import logging
import base64
import json
from typing import List

# Third-party imports
import openai
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, 
    ContextTypes, 
    MessageHandler, 
    CommandHandler,
    filters
)
from dotenv import load_dotenv

# Import custom modules
import config
import memory
import database

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants for enhanced memory
MAX_MEMORY_MESSAGES = 1000  # Maximum number of messages to remember
BOT_NAME = "فیرتیق"
BOT_FULL_NAME = "فیرتیق الله باقرزاده"
BOT_DESCRIPTION = "یک بات هوشمند برای کمک به گروه‌های فارسی زبان"
OPENAI_MODEL_DEFAULT = config.OPENAI_MODEL_DEFAULT
OPENAI_MODEL_VISION = config.OPENAI_MODEL_VISION

# Configure OpenAI
from openai_functions import openai_client

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


async def generate_ai_response(
    prompt: str,
    chat_id: int = None,
    user_id: int = None,
    memory_context: str = None,
    user_profile_context: str = None,
    media_data: bytes = None,
    additional_images: List[bytes] = None
) -> str:
    """Generate an AI response using OpenAI's API."""
    try:
        # Check if we have memory context, if not, generate it
        if memory_context is None and chat_id is not None:
            memory_context = await memory.get_relevant_memory(chat_id, prompt)

        # Check if we have user profile context, if not, generate it
        if user_profile_context is None and chat_id is not None and user_id is not None:
            user_profile_context = memory.get_user_profile_context(chat_id, user_id)

        # Create the system message that initializes the bot's behavior
        system_message = (
            "شما یک ربات گپ تلگرام ایرانی به نام فیرتیق (firtigh)هستید که به گروه‌های فارسی زبان کمک می‌کند. "
            "هر زمان که یکی از کاربران شما را منشن کند یا به پیام شما پاسخ دهد، شما برای او یک پاسخ با لحن "
            ".ساده و دوستانه می‌نویسید"
            "اگر با لحن شوخی یا محاوره ای با شما مکالمه شد شما هم می‌تواند با لحن شوخ مانند طرف مقابل صحبت کنید"
            
            "\n\nدر پاسخ‌های خود:"
            "\n1. همیشه به فارسی پاسخ دهید."       
            "\n2. لحن شما باید ساده و صمیمی باشد - شما در یک گروه دوستانه صحبت می‌کنید."
            "\n3. مستقیماً با کاربران صحبت کنید، نگویید «من پاسخ می‌دهم...» یا «در پاسخ به سوال شما...» - فقط پاسخ دهید."
            "\n4. از فرمت‌بندی استفاده کنید - مارک‌داون، بولد، ایتالیک - برای پاسخ‌های بهتر."
            "\n5. از ایموجی‌ها به طور هوشمندانه استفاده کنید تا پاسخ‌ها دوستانه‌تر به نظر برسند."
            "\n6. اگر به منابع خاصی اشاره می‌کنید، حتماً نام منبع و لینک را ذکر کنید."
            
            # Persian writing instructions
            "\n\nراهنمای نگارش فارسی:"
            "\n1. فاصله‌گذاری صحیح: بین کلمات فاصله بگذارید، اما بین کلمات و علائم نگارشی مثل نقطه و ویرگول فاصله نگذارید."
            "\n2. «گیومه» را به شکل صحیح فارسی استفاده کنید."
            "\n3. از اعداد فارسی استفاده کنید: ۰۱۲۳۴۵۶۷۸۹ به جای 0123456789."
            "\n4. نیم‌فاصله را در ترکیبات مثل «می‌شود» یا «گفته‌اند» رعایت کنید."
            "\n5. از علامت‌های نگارشی فارسی استفاده کنید مثل «،» به جای «,»."
        )

        # Prepare messages for the API call
        messages = [{"role": "system", "content": system_message}]
        
        # Add memory context if available
        if memory_context:
            messages.append({"role": "system", "content": f"Memory context: {memory_context}"})
        
        # Add user profile if available
        if user_profile_context:
            messages.append({"role": "system", "content": f"User profile: {user_profile_context}"})
        
        # Add the current user message
        if media_data or additional_images:
            # Handle vision model request with images
            content = [{"type": "text", "text": prompt}]
            
            # Add primary media if available
            if media_data:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{media_data.decode('utf-8')}",
                        "detail": "high"
                    }
                })
            
            # Add any additional images
            if additional_images:
                for img_data in additional_images:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_data.decode('utf-8')}",
                            "detail": "high"
                        }
                    })
            
            messages.append({"role": "user", "content": content})
            
            # Use the vision model
            response = await openai_client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
            )
            
            return response.choices[0].message.content
        else:
            # Regular text request with function calling
            messages.append({"role": "user", "content": prompt})
            
            # Get function definitions from openai_functions module
            from openai_functions import get_openai_function_definitions, process_function_calls
            
            # Use the regular chat model with function calling
            response = await openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages,
                tools=[{"type": "function", "function": func} for func in get_openai_function_definitions()],
                tool_choice="auto",
                temperature=0.7,
                max_tokens=1000
            )
            
            # Process any function calls
            return await process_function_calls(response, chat_id=chat_id, user_id=user_id)
    
    except Exception as e:
        logging.error(f"Error generating response: {e}", exc_info=True)
        # Provide a fallback response in Persian
        return "متأسفانه در پردازش پیام شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید."

 
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

        # Get sender info for the bot to address the user appropriately
        user_id = None
        if update.message.from_user:
            user_id = update.message.from_user.id

        # Get conversation context from reply chain
        conversation_context, media_data_list = await get_conversation_context(update, context)
        
        # Initialize variables for handling media
        media_data = None
        additional_images = None
        
        # Handle photos - add usage limits
        if update.message.photo:
            try:
                # Get the highest resolution photo
                photo = update.message.photo[-1]
                
                # Download the photo
                media_data = await download_telegram_file(photo.file_id, context)
                if media_data:
                    logger.info(f"Downloaded image from message: {len(media_data)} bytes")
            except Exception as e:
                logger.error(f"Error downloading image: {e}")

        # Check if any media is available in the conversation context
        if media_data_list and len(media_data_list) > 0:
            additional_images = media_data_list

        # Send typing indicator
        await update.message.reply_chat_action("typing")
       
        # Get response from AI
        ai_response = await generate_ai_response(
            prompt=query,
            chat_id=chat_id,
            user_id=user_id,
            media_data=media_data,
            additional_images=additional_images
        )
        
        if not ai_response:
            ai_response = "متأسفم، در حال حاضر نمی‌توانم پاسخی تولید کنم. 😔"
        
        # Check if the response contains links (markdown format)
        contains_links = re.search(r'\[([^\]]+)\]\(([^)]+)\)', ai_response) is not None
        is_news_query = False  # No need to detect news queries anymore, handled by function calling
        
        # Special handling for responses with links to ensure links are clickable
        if contains_links:
            try:
                # Use standard Markdown for responses with links to ensure links work
                await update.message.reply_text(ai_response, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Error sending response with links using Markdown: {e}")
                # Try with HTML parsing instead which might handle links better
                try:
                    # Convert markdown links to HTML links first (before other conversions)
                    html_response = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', ai_response)
                    await update.message.reply_text(html_response, parse_mode=ParseMode.HTML)
                except Exception as e2:
                    logger.error(f"Error sending response with HTML links: {e2}")
                    # Fall back to plain text
                    await update.message.reply_text(ai_response)
        else:
            # For responses without links, just send as plain text
            await update.message.reply_text(ai_response)



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
    # Process all messages to check for mentions
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Log startup
    logger.info("Bot started, waiting for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 