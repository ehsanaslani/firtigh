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
        f"Hi {user.mention_html()}! I'm Firtigh. Mention me with @@firtigh in a message to get a response."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Mention me with @@firtigh in a message to get a response.")

async def generate_ai_response(prompt: str) -> str:
    """Generate a response using OpenAI's API."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "Sorry, I couldn't generate a response at the moment."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages that mention the bot."""
    # Skip processing if there's no message text
    if not update.message or not update.message.text:
        return
        
    message_text = update.message.text
    bot_username = context.bot.username.lower()
    
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
            await update.message.reply_text("You mentioned me, but didn't ask anything. How can I help?")
            return
        
        # Generate and send AI response
        ai_response = await generate_ai_response(query)
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