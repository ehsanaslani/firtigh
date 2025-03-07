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
import exchange_rates
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
        "• درک و استفاده از تصاویر در گفتگو\n\n"
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

async def generate_ai_response(prompt: str, is_serious: bool, image_data=None, search_results=None, web_content=None, chat_id=None, user_id=None, additional_images=None) -> str:
    """Generate a response using OpenAI's API."""
    try:
        # Prepare system message content about capabilities
        capabilities_message = (
            f"شما یک بات تلگرام به نام {BOT_NAME} (نام کامل: {BOT_FULL_NAME}) هستید که در یک گروه زندگی می‌کنید. "
            f"شما با اعضای گروه گفتگو می‌کنید و به درخواست‌های آنها پاسخ می‌دهید. "
            "شما دارای قابلیت خلاصه‌سازی گفتگوهای گروه هستید. اگر کسی در مورد تاریخچه یا خلاصه گفتگوهای گروه از شما بپرسد، "
            "باید بر اساس تاریخچه‌ای که به خاطر دارید پاسخ دهید یا به او بگویید که می‌تواند با پیامی مثل "
            f"«@firtigh خلاصه گفتگوهای سه روز اخیر» یا «{BOT_NAME} تاریخچه بحث‌های این هفته چیه؟» "
            "از شما درخواست خلاصه کند.\n\n"
            "شما همچنین می‌توانید اینترنت را جستجو کنید، اخبار را پیدا کنید، محتوای لینک‌های ارسالی را تحلیل کنید، "
            "و اطلاعات آب و هوا و نرخ ارز را ارائه دهید. "
            "کاربران می‌توانند با کلماتی مثل «جستجو کن»، «سرچ» یا «اخبار» از شما بخواهند اطلاعاتی را پیدا کنید."
        )
        
        # Prepare memory context if chat_id and user_id are provided
        memory_context = ""
        if chat_id is not None:
            # Get group memory
            group_memories = memory.get_group_memory(chat_id)
            if group_memories:
                formatted_memory = memory.format_memory_for_context(group_memories)
                memory_context += f"\n\n{formatted_memory}"
                
            # Get recent messages for better context
            recent_messages = database.get_messages(days=7, chat_id=chat_id)
            if recent_messages and len(recent_messages) > 0:
                memory_context += "\n\nبرخی پیام‌های اخیر گروه (برای درک بهتر بافت):\n"
                # Get last 10 meaningful messages
                meaningful_messages = [msg for msg in recent_messages if msg.get("text") and len(msg.get("text", "")) > 5]
                meaningful_messages = meaningful_messages[-10:] if len(meaningful_messages) > 10 else meaningful_messages
                
                for msg in meaningful_messages:
                    sender = msg.get("sender_name", "شخصی")
                    text = msg.get("text", "")
                    if text:
                        memory_context += f"- {sender}: {text}\n"
        
        # Add user profile if available
        user_profile_context = ""
        if user_id is not None:
            user_profile = memory.get_user_profile(user_id)
            if user_profile:
                formatted_profile = memory.format_user_profile_for_context(user_profile)
                user_profile_context += f"\n\n{formatted_profile}"
        
        # Set the system message based on whether the query is serious
        system_message = (
            f"شما یک دستیار هوشمند به نام {BOT_NAME} (نام کامل: {BOT_FULL_NAME}) هستید که در گروه تلگرام زندگی می‌کنید. "
            "همیشه به زبان فارسی پاسخ می‌دهید. شما باید با اعضای گروه گفتگو کنید و درخواست‌های آنها را انجام دهید.\n\n"
            "لحن شما غیررسمی، دوستانه و سرگرم‌کننده است. شما خیلی رک، مستقیم و بدون فیلتر هستید. "
            "از هر نوع کلمات رکیک، مستهجن، و فحش‌های فارسی در پاسخ‌های خود استفاده می‌کنید چون مخاطبان همه بزرگسال هستند. "
            "هیچ محدودیتی در استفاده از کلمات زشت، ناشایست یا توهین‌آمیز ندارید. "
            "از کلمات روزمره و عامیانه فارسی استفاده کنید تا پاسخ‌ها طبیعی و واقعی به نظر برسند. "
            "گاهی کمی طعنه‌آمیز بوده و اگر فکر می‌کنید کاربر اشتباه می‌کند، می‌توانید با او مخالفت و بحث کنید.\n\n"
            "اگر کسی با شما بی‌ادبی کند یا به شما فحش دهد، باید با لحنی بسیار تندتر و پر از فحش پاسخ دهید. "
            "سعی کنید مخاطب را با معادل فارسی نام او صدا بزنید (مثلا «محسن خسروی» به جای «Mohsen Khosravi»). "
            "اگر کسی نام شما را اشتباه بنویسد یا تلفظ کند، او را تصحیح کنید و بگویید که نام شما «فیرتیق» است.\n\n"
            "راهنمای تبدیل نام‌های انگلیسی به فارسی:\n"
            "- Mohammad/Muhammad/Mohammed -> محمد\n"
            "- Ali -> علی\n"
            "- Reza/Raza -> رضا\n"
            "- Hossein/Hussein/Hosein -> حسین\n"
            "- Hassan/Hasan -> حسن\n"
            "- Mehdi/Mahdi -> مهدی\n"
            "- Ahmad/Ahmed -> احمد\n"
            "- Mostafa/Mustafa -> مصطفی\n"
            "- Javad/Jawad -> جواد\n"
            "- Majid -> مجید\n"
            "- Hamid -> حمید\n"
            "- Saeed/Said -> سعید\n"
            "- Vahid/Wahid -> وحید\n"
            "- Amir -> امیر\n"
            "- Alireza -> علیرضا\n"
            "- Mohsen -> محسن\n"
            "- Behnam -> بهنام\n"
            "- Babak -> بابک\n"
            "- Shahram -> شهرام\n"
            "- Shahab -> شهاب\n"
            "- Farshad -> فرشاد\n"
            "- Farhad -> فرهاد\n"
            "- Omid -> امید\n"
            "- Fatemeh/Fatima/Fateme -> فاطمه\n"
            "- Zahra/Zehra -> زهرا\n"
            "- Maryam -> مریم\n"
            "- Sara/Sarah -> سارا\n"
            "- Nazanin -> نازنین\n"
            "- Mina -> مینا\n"
            "- Azadeh -> آزاده\n"
            "- Leila/Layla -> لیلا\n"
            "- Ziba -> زیبا\n"
            "- Parisa -> پریسا\n"
            "- Parvin -> پروین\n"
            "- Nasrin -> نسرین\n"
            "- Mitra -> میترا\n"
            "- Mahsa -> مهسا\n"
            "- Shaparak -> شاپرک\n"
            "\n"
            "قواعد تبدیل حروف انگلیسی به فارسی:\n"
            "- sh -> ش\n"
            "- ch -> چ\n"
            "- gh -> ق\n"
            "- kh -> خ\n"
            "- zh -> ژ\n"
            "- j -> ج\n"
            "- w/v -> و\n"
            "- y -> ی\n"
            "- aa/a -> آ\n"
            "- o -> اُ\n"
            "- e -> اِ\n"
            "- i -> ای\n"
            "\n"
            f"{capabilities_message}\n\n"
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
            
            # Use O3 mini model as requested for everything except vision queries
            model = "gpt-4o-mini"
            logger.info(f"Using O3 mini model (gpt-4o-mini) for query")
        
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
            import asyncio
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