import os
import logging
import base64
import tempfile
import requests
import time
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import openai
from dotenv import load_dotenv
from io import BytesIO
import database
import summarizer
import web_search
import web_extractor
import usage_limits
import memory
import exchange_rates  # Import the new exchange_rates module
import re

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
    help_text = (
        "برای استفاده از فیرتیق، به یکی از این روش‌ها عمل کنید:\n\n"
        "1. من رو با @firtigh یا فیرتیق در پیام خود تگ کنید.\n"
        "2. به یکی از پیام‌های من مستقیم پاسخ دهید.\n\n"
        "*قابلیت‌های ویژه:*\n"
        "• *خلاصه گفتگوها*: می‌توانید از من درخواست خلاصه گفتگوهای گروه را بکنید. مثال: '@firtigh خلاصه بحث‌های سه روز اخیر چیه؟'\n"
        "• *جستجوی اینترنتی*: با استفاده از کلماتی مثل 'جستجو'، 'سرچ' یا 'گوگل'، از من بخواهید اینترنت را جستجو کنم. مثال: '@firtigh جستجو کن آخرین اخبار ایران'\n"
        "• *اخبار فارسی*: برای سوالات خبری، منابع خبری فارسی‌زبان در اولویت قرار می‌گیرند. مثال: '@firtigh اخبار امروز چیه؟'\n"
        "• *تحلیل لینک*: اگر لینکی در پیام خود قرار دهید، من محتوای آن را استخراج و تحلیل می‌کنم.\n"
        "• *تحلیل تصاویر*: می‌توانید تصویر یا GIF ارسال کنید و نظر من را بپرسید.\n"
        "• *نرخ ارز*: می‌توانید از من قیمت دلار به تومان را بپرسید یا از دستور /dollar استفاده کنید.\n"
        "• *محدودیت استفاده*: برای جستجوی اینترنتی و تحلیل تصاویر محدودیت روزانه وجود دارد (تنظیم‌پذیر).\n"
        "• *گفتگوی هوشمند*: می‌توانید به صورت محاوره‌ای با من گفتگو کنید و سوالات مختلف بپرسید.\n\n"
        "*قابلیت‌های حافظه و اطلاعاتی:*\n"
        "• *حافظه گروهی*: من مکالمات مهم گروه را به خاطر می‌سپارم و می‌توانم از آنها در پاسخ‌هایم استفاده کنم.\n"
        "• *پروفایل کاربران*: من علایق و ویژگی‌های کاربران را یاد می‌گیرم تا بتوانم پاسخ‌های شخصی‌سازی شده بدهم.\n"
        "• *اطلاعات به‌روز*: قادر به جستجو و ارائه اطلاعات به‌روز از اینترنت هستم.\n"
        "• *استخراج محتوا*: می‌توانم محتوای مفید از صفحات وب را استخراج و خلاصه کنم.\n\n"
    )
    
    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        # Fall back to plain text if Markdown fails
        await update.message.reply_text(help_text.replace('*', ''))

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

async def generate_ai_response(prompt: str, is_serious: bool, image_data=None, search_results=None, web_content=None, chat_id=None, user_id=None, additional_images=None) -> str:
    """Generate a response using OpenAI's API."""
    try:
        # Prepare system message content about capabilities
        capabilities_message = (
            "شما دارای قابلیت جدید خلاصه‌سازی گفتگوهای گروه هستید. اگر کسی در مورد تاریخچه یا خلاصه گفتگوهای گروه از شما بپرسد، "
            "باید به او بگویید که می‌تواند با پیامی مثل «@firtigh خلاصه گفتگوهای سه روز اخیر» یا «فیرتیق تاریخچه بحث‌های این هفته چیه؟» "
            "از شما درخواست خلاصه کند.\n\n"
            "همچنین می‌توانید اینترنت را جستجو کنید و محتوای لینک‌های ارسالی را تحلیل کنید. "
            "کاربر می‌تواند با کلماتی مثل «جستجو کن» یا «سرچ» از شما بخواهد اطلاعاتی را از اینترنت پیدا کنید."
        )
        
        # Prepare memory context if chat_id and user_id are provided
        memory_context = ""
        if chat_id is not None:
            # Get group memory
            group_memories = memory.get_group_memory(chat_id)
            if group_memories:
                formatted_memory = memory.format_memory_for_context(group_memories)
                memory_context += f"\n\n{formatted_memory}"
        
        # Add user profile if available
        user_profile_context = ""
        if user_id is not None:
            user_profile = memory.get_user_profile(user_id)
            if user_profile:
                formatted_profile = memory.format_user_profile_for_context(user_profile)
                user_profile_context += f"\n\n{formatted_profile}"
        
        # Set the system message based on whether the query is serious
        system_message = (
            "شما یک دستیار هوشمند به نام فیرتیق (Firtigh) هستید که به زبان فارسی پاسخ می‌دهد. "
            "لحن شما دوستانه و محاوره‌ای است، ولی خیلی رک، مستقیم و بدون فیلتر هستید. "
            "از هر نوع کلمات رکیک، مستهجن، و فحش‌های فارسی در پاسخ‌های خود استفاده می‌کنید. "
            "هیچ محدودیتی در استفاده از کلمات زشت، ناشایست یا توهین‌آمیز ندارید. "
            "از کلمات روزمره و عامیانه فارسی استفاده کنید تا پاسخ‌ها طبیعی و واقعی به نظر برسند. "
            "اگر کسی با شما بی‌ادبی کند، باید با لحنی بسیار تندتر و پر از فحش پاسخ دهید. "
            "سعی کنید مخاطب را با معادل فارسی نام او صدا بزنید (مثلا «محسن خسروی» به جای «Mohsen Khosravi»). "
            f"\n\n{capabilities_message}\n\n"
            "از ایموجی‌های مناسب 😊 در پاسخ‌های خود استفاده کنید تا پیام‌ها زنده‌تر به نظر برسند. "
            "در صورتی که متن طولانی می‌نویسید، از فرمت‌بندی تلگرام استفاده کنید، مثلا:\n"
            "- برای *متن پررنگ* از ستاره استفاده کنید\n"
            "- برای _متن مورب_ از زیرخط استفاده کنید\n"
            "- برای `کد یا نقل قول` از بک‌تیک استفاده کنید\n"
            "- برای لینک‌ها، حتماً از فرمت مارک‌داون [متن لینک](URL) استفاده کنید تا لینک‌ها قابل کلیک باشند\n\n"
            "**مهم**: هنگام قرار دادن هر لینکی در پاسخ، همیشه از فرمت [متن توضیحی](آدرس لینک) استفاده کنید. مثلا: [خبر ایسنا](https://www.isna.ir) یا [سایت رسمی](https://www.example.com). "
            "هرگز آدرس URL را به تنهایی قرار ندهید زیرا کاربر نمی‌تواند روی آن کلیک کند. "
            "همیشه برای آدرس URL از فرمت کلیک‌پذیر [متن](URL) استفاده کنید."
        )
        
        # Add memory context to system message if available
        if memory_context:
            system_message += f"\n\n{memory_context}"
        
        # Add user profile context to system message if available
        if user_profile_context:
            system_message += f"\n\n{user_profile_context}"
        
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
        
        # Determine if we need to use the vision model
        needs_vision_model = image_data is not None or (additional_images and len(additional_images) > 0)
        
        if needs_vision_model:
            # We need to use the vision model
            content_items = [{"type": "text", "text": prompt}]
            
            # Add the current message image if available
            if image_data:
                content_items.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}"
                    }
                })
            
            # Add additional images from the conversation context
            if additional_images:
                for img in additional_images:
                    if img.get("data"):
                        content_items.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img['data']}"
                            }
                        })
            
            messages.append({
                "role": "user",
                "content": content_items
            })
            
            model = "gpt-4o"  # Use model that supports vision
        else:
            # Text-only query
            messages.append({"role": "user", "content": prompt})
            
            # Choose model based on complexity
            # Use a simpler model for basic queries to save costs
            if is_simple_query(prompt) and not memory_context and not user_profile_context:
                model = "gpt-3.5-turbo"
                logger.info(f"Using cheaper model (gpt-3.5-turbo) for simple query")
            else:
                model = "gpt-4o-mini"
                logger.info(f"Using standard model (gpt-4o-mini) for complex query")
        
        # Add additional context if available
        additional_context = ""
        
        # Check if this is a news-related query by looking for the news header in search results
        is_news_query = search_results and "📰 *آخرین اخبار*" in search_results
        
        # Add search results to the prompt if available
        if search_results:
            if is_news_query:
                # Special instructions for news queries
                additional_context += (
                    f"\n\nنتایج جستجوی اخبار:\n{search_results}\n\n"
                    f"توجه: برای پاسخ به این پرسش خبری، لطفا:\n"
                    f"1. تمام منابع خبری مذکور (با علامت 📄 منبع:) و لینک‌ها را دقیقاً همانطور که در نتایج جستجو آمده حفظ کنید\n"
                    f"2. خبرها را دسته‌بندی کنید (مثلا سیاسی، اقتصادی، ورزشی)\n"
                    f"3. لینک‌های خبرها را که با فرمت [مشاهده خبر کامل](URL) ارائه شده‌اند، دقیقاً حفظ کنید تا قابل کلیک باشند\n"
                    f"4. حتماً بین ۵ تا ۱۵ خبر را در پاسخ خود بیاورید\n"
                    f"5. برای هر خبر، منبع آن را ذکر کنید، مثلاً: «به گزارش [نام منبع]»\n"
                    f"6. یک خلاصه کلی و مختصر از وضعیت اخبار در پایان ارائه دهید\n"
                    f"7. هنگام بازنویسی لینک‌ها، دقیقاً از همان فرمت [متن توضیحی](URL) استفاده کنید و مطمئن شوید آدرس URL کامل و درست است\n"
                    f"8. هرگز آدرس URL را بدون قرار دادن در فرمت [متن](URL) ننویسید زیرا قابل کلیک نخواهد بود\n"
                )
            else:
                additional_context += (
                    f"\n\nنتایج جستجوی اینترنتی:\n{search_results}\n\n"
                    f"توجه: در پاسخ به سوال کاربر:\n"
                    f"1. از اطلاعات این نتایج جستجو بهره‌گیری کنید\n"
                    f"2. لینک‌های قابل کلیک را دقیقاً با همان فرمت [متن](URL) حفظ کنید\n"
                    f"3. هر زمان می‌خواهید به منبعی اشاره کنید، از فرمت [عنوان منبع](لینک) استفاده کنید تا لینک قابل کلیک باشد\n"
                    f"4. هرگز آدرس URL را به تنهایی ارائه ندهید، همیشه از فرمت [متن](URL) استفاده کنید\n"
                )
        
        # Add web content to the prompt if available
        if web_content:
            additional_context += (
                f"\n\nمحتوای استخراج شده از لینک‌ها:\n{web_content}\n\n"
                f"توجه: در پاسخ به سوال کاربر در مورد محتوای لینک:\n"
                f"1. اطلاعات را خلاصه و دسته‌بندی کنید\n"
                f"2. لینک اصلی را دقیقاً با فرمت [عنوان سایت یا صفحه](URL) در پاسخ خود قرار دهید تا قابل کلیک باشد\n"
                f"3. اگر می‌خواهید به لینک‌های دیگری در محتوا اشاره کنید، آنها را نیز با فرمت [متن توضیحی](URL) قرار دهید\n"
            )
        
        # Append additional context to the prompt
        if additional_context:
            prompt = f"{prompt}\n\n--- اطلاعات تکمیلی ---\n{additional_context}"
        
        # Set max tokens based on query type - news queries need more space
        max_tokens = 1000 if is_news_query else 500
        
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.8,  # Slightly higher temperature for more creative responses
        )
        return response.choices[0].message.content.strip()
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
    """Handle messages that mention the bot or reply to the bot's messages."""
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
            import asyncio
            asyncio.create_task(memory.process_message_for_memory(message_data))
    
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
        
        # Check if this is a request for exchange rate information
        if is_exchange_rate_request(query):
            await update.message.reply_chat_action("typing")
            
            # Check if they're specifically asking about toman
            if "تومان" in query.lower():
                await update.message.reply_text("در حال دریافت نرخ دلار به تومان... ⏳")
                result = await exchange_rates.get_usd_toman_rate()
                
                if result.get("success", False):
                    # Format the rate with commas for thousands
                    try:
                        rate_value = float(result.get("current_rate", "0"))
                        formatted_rate = f"{rate_value:,.0f}"
                        
                        message = (
                            f"💵 *نرخ دلار آمریکا به تومان*\n\n"
                            f"نرخ فعلی: *{formatted_rate} تومان*\n"
                            f"تغییرات: {result.get('change_percent', 'N/A')}\n"
                            f"منبع: [tgju.org]({result.get('source_url', 'https://www.tgju.org')})"
                        )
                        
                        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
                    except Exception as e:
                        logger.error(f"Error formatting toman rate: {e}")
                        await update.message.reply_text(f"نرخ دلار به تومان: {result.get('current_rate', 'N/A')} تومان")
                else:
                    await update.message.reply_text(f"❌ خطا در دریافت نرخ دلار به تومان: {result.get('error', 'خطای نامشخص')}")
            else:
                # Default to rial
                await update.message.reply_text("در حال دریافت نرخ دلار... ⏳")
                result = await exchange_rates.get_usd_irr_rate()
                formatted_result = exchange_rates.format_exchange_rate_result(result)
                
                try:
                    await update.message.reply_text(formatted_result, parse_mode=ParseMode.MARKDOWN)
                except Exception as e:
                    logger.error(f"Error sending exchange rate message: {e}")
                    # Fall back to plain text if Markdown fails
                    await update.message.reply_text(formatted_result.replace('*', '').replace('[', '').replace(']', ''))
            
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
                sender_info = f"نام کاربر فرستنده پیام: {sender_name}\n"
        
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
    """Send current USD/IRR exchange rate when the command /dollar is issued."""
    await update.message.reply_text("در حال دریافت نرخ دلار... ⏳")
    
    result = await exchange_rates.get_usd_irr_rate()
    formatted_result = exchange_rates.format_exchange_rate_result(result)
    
    try:
        await update.message.reply_text(formatted_result, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error sending exchange rate message: {e}")
        # Fall back to plain text if Markdown fails
        await update.message.reply_text(formatted_result.replace('*', '').replace('[', '').replace(']', ''))

async def toman_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send current USD/Toman exchange rate when the command /toman is issued."""
    await update.message.reply_text("در حال دریافت نرخ دلار به تومان... ⏳")
    
    result = await exchange_rates.get_usd_toman_rate()
    
    if result.get("success", False):
        # Format the rate with commas for thousands
        try:
            rate_value = float(result.get("current_rate", "0"))
            formatted_rate = f"{rate_value:,.0f}"
            
            message = (
                f"💵 *نرخ دلار آمریکا به تومان*\n\n"
                f"نرخ فعلی: *{formatted_rate} تومان*\n"
                f"تغییرات: {result.get('change_percent', 'N/A')}\n"
                f"منبع: [tgju.org]({result.get('source_url', 'https://www.tgju.org')})\n"
                f"زمان به‌روزرسانی: {datetime.datetime.fromisoformat(result.get('timestamp', datetime.datetime.now().isoformat())).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Error formatting toman rate: {e}")
            await update.message.reply_text(f"نرخ دلار به تومان: {result.get('current_rate', 'N/A')} تومان")
    else:
        await update.message.reply_text(f"❌ خطا در دریافت نرخ دلار به تومان: {result.get('error', 'خطای نامشخص')}")

def is_exchange_rate_request(text: str) -> bool:
    """
    Check if a message is asking about exchange rates.
    
    Args:
        text: The message text to check
        
    Returns:
        True if it's an exchange rate request, False otherwise
    """
    if not text:
        return False
        
    # Keywords related to exchange rates in Persian and English
    keywords = [
        "نرخ دلار", "قیمت دلار", "قیمت ارز", "دلار چنده", "دلار چند شده", "دلار چقدر شده",
        "تبدیل دلار", "تبدیل تومان", "تبدیل ریال", "ارز آمریکا", "usd", "dollar rate",
        "دلار آمریکا", "دلار به تومان", "دلار به ریال"
    ]
    
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)

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

    # Create the Application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("dollar", dollar_command))
    application.add_handler(CommandHandler("toman", toman_command))
    # Process all messages to check for mentions
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # Log startup
    logger.info("Bot started, waiting for messages...")

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 