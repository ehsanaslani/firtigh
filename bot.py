import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
from dotenv import load_dotenv

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

async def generate_ai_response(prompt: str, is_serious: bool) -> str:
    """Generate a response using OpenAI's API."""
    try:
        # Set the system message based on whether the query is serious
        system_message = (
            "شما یک دستیار مفید و دوستانه هستید. همیشه به زبان فارسی و با لحنی صمیمی و محاوره‌ای پاسخ دهید. "
            "از کلمات روزمره و عامیانه استفاده کنید تا پاسخ‌ها طبیعی و دوستانه به نظر برسند. "
        )
        
        # Add humor instruction for non-serious messages
        if not is_serious:
            system_message += (
                "این پیام جدی به نظر نمی‌رسد، پس کمی شوخ‌طبعی و طنز در پاسخ خود اضافه کنید. "
                "از تکه‌کلام‌های رایج فارسی و طنز ملایم استفاده کنید."
            )
        
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Using a more capable model
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.8,  # Slightly higher temperature for more creative responses
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "متأسفم، در حال حاضر نمی‌توانم پاسخی تولید کنم."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages that mention the bot."""
    # Skip processing if there's no message text
    if not update.message or not update.message.text:
        return
        
    message_text = update.message.text
    bot_username = context.bot.username.lower() if context.bot.username else "firtigh"
    
    # Different ways the bot might be mentioned in a group
    mentions = [
        f"@@firtigh",           # Original format
        f"@{bot_username}",     # Standard @username mention
        f"@firtigh",            # In case username is firtigh
        "firtigh",              # Just the name
    ]
    
    # Check if any form of mention is in the message (case insensitive)
    mentioned = any(mention.lower() in message_text.lower() for mention in mentions)
    
    if mentioned:
        # Log that the bot was mentioned
        logger.info(f"Bot mentioned in message: {message_text}")
        
        # Remove all possible mentions to get the actual query
        query = message_text.lower()
        for mention in mentions:
            query = query.replace(mention.lower(), "").strip()
            
        # If there's no query after removing the mentions, ask for more information
        if not query:
            await update.message.reply_text("من رو صدا زدی، ولی سوالی نپرسیدی. چطور می‌تونم کمکت کنم؟")
            return
        
        # Determine if the message is serious
        is_serious = await is_serious_question(query)
        
        # Generate and send AI response
        ai_response = await generate_ai_response(query, is_serious)
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Log startup
    logger.info("Bot started, waiting for messages...")
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main() 