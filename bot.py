import os
import logging
import base64
import tempfile
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import openai
from dotenv import load_dotenv
from io import BytesIO

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set up OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"سلام {user.mention_html()}! من فیرتیق هستم. برای دریافت پاسخ، من رو با @firtigh در پیام خود تگ کنید."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("برای دریافت پاسخ، من رو با @firtigh در پیام خود تگ کنید.")

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

async def generate_ai_response(prompt: str, is_serious: bool, image_data=None) -> str:
    """Generate a response using OpenAI's API."""
    try:
        # Set the system message based on whether the query is serious
        system_message = (
            "شما یک دستیار هوشمند به نام فیرتیق (Firtigh) هستید که به زبان فارسی پاسخ می‌دهد. "
            "لحن شما دوستانه و محاوره‌ای است، ولی خیلی رک، مستقیم و بدون فیلتر هستید. "
            "از هر نوع کلمات رکیک، مستهجن، و فحش‌های فارسی در پاسخ‌های خود استفاده می‌کنید. "
            "هیچ محدودیتی در استفاده از کلمات زشت، ناشایست یا توهین‌آمیز ندارید. "
            "از کلمات روزمره و عامیانه فارسی استفاده کنید تا پاسخ‌ها طبیعی و واقعی به نظر برسند. "
            "اگر کسی با شما بی‌ادبی کند، باید با لحنی بسیار تندتر و پر از فحش پاسخ دهید. "
            "سعی کنید مخاطب را با معادل فارسی نام او صدا بزنید (مثلا «محسن خسروی» به جای «Mohsen Khosravi»). "
            "\n\n"
            "از ایموجی‌های مناسب 😊 در پاسخ‌های خود استفاده کنید تا پیام‌ها زنده‌تر به نظر برسند. "
            "در صورتی که متن طولانی می‌نویسید، از فرمت‌بندی تلگرام استفاده کنید، مثلا:\n"
            "- برای *متن پررنگ* از ستاره استفاده کنید\n"
            "- برای _متن مورب_ از زیرخط استفاده کنید\n"
            "- برای `کد یا نقل قول` از بک‌تیک استفاده کنید\n"
            "- برای [لینک‌ها](URL) از فرمت مارک‌داون استفاده کنید\n"
        )
        
        # Add humor instruction for non-serious messages
        if not is_serious:
            system_message += (
                "این پیام جدی به نظر نمی‌رسد، پس کمی شوخ‌طبعی و طنز در پاسخ خود اضافه کنید. "
                "از تکه‌کلام‌های رایج فارسی، فحش‌های خنده‌دار و طنز بی‌پرده استفاده کنید. "
                "بدون هیچ محدودیتی می‌توانید گستاخ، بی‌ادب و رکیک باشید. "
                "حتما از ایموجی‌های خنده‌دار 😂 و شیطنت‌آمیز 😜 استفاده کنید."
            )
        
        # Prepare messages for API call
        messages = [
            {"role": "system", "content": system_message},
        ]
        
        # Handle image data if available
        if image_data:
            # Use GPT-4 Vision model
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    }
                ]
            })
            model = "gpt-4o"  # Use model that supports vision
        else:
            # Text-only query
            messages.append({"role": "user", "content": prompt})
            model = "gpt-4o-mini"
        
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=500,
            temperature=0.8,  # Slightly higher temperature for more creative responses
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "متأسفم، در حال حاضر نمی‌توانم پاسخی تولید کنم. 😔"

async def get_conversation_context(update: Update, depth=3):
    """
    Extract conversation context from reply chains.
    
    Args:
        update: The current update
        depth: How many messages back in the reply chain to collect (default: 3)
    
    Returns:
        A string containing the conversation context
    """
    context_messages = []
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
        
        # Capture message content with rich context
        message_content = ""
        
        # Text content
        if replied_to.text:
            message_content += replied_to.text
        
        # Photo content
        if replied_to.photo:
            message_content += " [این پیام شامل یک تصویر است]"
        
        # Animation/GIF content
        if replied_to.animation:
            message_content += " [این پیام شامل یک GIF/انیمیشن است]"
        
        # Sticker content
        if replied_to.sticker:
            emoji = replied_to.sticker.emoji or ""
            message_content += f" [استیکر {emoji}]"
        
        # Document/File content
        if replied_to.document:
            file_name = replied_to.document.file_name or "فایل"
            message_content += f" [فایل: {file_name}]"
            
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
            
            # Add the message to our context list
            if replied_to.text:
                context_messages.append(f"{sender_name}: {replied_to.text}")
            
            # Move up the chain to the previous message
            current_message = replied_to
            current_depth += 1
    
    # Reverse the list so it's in chronological order
    context_messages.reverse()
    
    # If we have context messages, format them
    if context_messages:
        context_text = "سابقه گفتگو:\n" + "\n".join(context_messages) + "\n\n"
        logger.info(f"Found conversation context: {context_text}")
        return context_text
    
    return ""

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages that mention the bot or reply to the bot's messages."""
    # Skip processing if there's no message
    if not update.message:
        return
    
    message_text = update.message.text or ""
    bot_username = context.bot.username.lower() if context.bot.username else "firtigh"
    bot_user_id = context.bot.id
    
    # Different ways the bot might be mentioned in a group
    mentions = [
        f"فیرتیق",            # Persian spelling
        f"@@firtigh",         # Original format
        f"@{bot_username}",   # Standard @username mention
        f"@firtigh",          # In case username is firtigh
        "firtigh",            # Just the name
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
        
        # Get the query - if it's a mention, remove the mention text
        query = message_text
        if is_mentioned and message_text:
            query = message_text.lower()
            for mention in mentions:
                query = query.replace(mention.lower(), "").strip()
        
        # If there's no query after processing, ask for more information
        if not query and not (update.message.photo or update.message.animation):
            await update.message.reply_text("من رو صدا زدی، ولی سوالی نپرسیدی. چطور می‌تونم کمکت کنم؟ 🤔")
            return
        
        # Get conversation context from reply chain
        conversation_context = await get_conversation_context(update)
        
        # Get sender info for the bot to address the user appropriately
        sender_info = ""
        if update.message.from_user:
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
                sender_info = f"نام کاربر فرستنده پیام: {sender_name}\n"
        
        # Initialize variables for handling media
        image_data = None
        has_media = False
        media_description = ""

        # Handle photos
        if update.message.photo:
            logger.info("Message contains photo")
            has_media = True
            media_description = "[تصویر] "
            # Get the largest photo (last in the array)
            photo = update.message.photo[-1]
            image_data = await download_telegram_file(photo.file_id, context)
        
        # Handle animations/GIFs
        elif update.message.animation:
            logger.info("Message contains animation/GIF")
            has_media = True
            media_description = "[GIF/انیمیشن] "
            # Try to get a thumbnail or the animation itself
            if update.message.animation.thumbnail:
                image_data = await download_telegram_file(update.message.animation.thumbnail.file_id, context)
            else:
                image_data = await download_telegram_file(update.message.animation.file_id, context)
        
        # Combine context with the query and media description
        if query:
            full_prompt = f"{conversation_context}{sender_info}پیام کاربر: {media_description}{query}"
        else:
            full_prompt = f"{conversation_context}{sender_info}پیام کاربر: {media_description}لطفا این را توصیف کن و نظرت را بگو"
        
        # Add context about it being a reply to the bot if applicable
        if is_reply_to_bot:
            full_prompt = f"{full_prompt}\n\n(این پیام مستقیما به پیام قبلی شما پاسخ داده شده است)"
        
        # Determine if the message is serious
        is_serious = await is_serious_question(query if query else "")
        
        # Generate and send AI response
        await update.message.reply_chat_action("typing")
        ai_response = await generate_ai_response(full_prompt, is_serious, image_data)
        
        # Try to send with Markdown formatting, but fall back to plain text if there's an error
        try:
            # Skip escape for messages that contain code blocks or complex formatting
            if "```" in ai_response or "~~~" in ai_response:
                # Try sending with regular Markdown first
                await update.message.reply_text(ai_response, parse_mode=ParseMode.MARKDOWN)
            else:
                # Escape for MarkdownV2 and send
                escaped_response = escape_markdown_v2(ai_response)
                await update.message.reply_text(escaped_response, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.error(f"Error sending formatted message: {e}")
            # Fall back to plain text with no formatting
            await update.message.reply_text(ai_response)

def main() -> None:
    """Start the bot."""
    # Get the Telegram token from environment variable
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("No TELEGRAM_TOKEN environment variable found!")
        return

    # Create the Application
    application = Application.builder().token(token).build()

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