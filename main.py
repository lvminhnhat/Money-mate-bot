import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

from bot_handlers import start, help_command, register, handle_message
from google_sheets_api import init_google_sheets_client

# Load environment variables from .env file FIRST
load_dotenv()

# --- Configure Logging ---
# Setup logging format and level
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Set higher logging level for httpx to avoid excessive logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__) # Define logger after basicConfig

# --- Load Config and Configure Services ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.critical("Missing TELEGRAM_BOT_TOKEN in .env file. Bot cannot start.")
    exit() # Exit if token is missing

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CONFIGURED = False
if not GEMINI_API_KEY:
    logger.warning("Missing GEMINI_API_KEY in .env file. Gemini features will be disabled.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_CONFIGURED = True
        logger.info("Google Generative AI configured successfully.")
    except Exception as e:
        logger.error(f"Failed to configure Google Generative AI: {e}", exc_info=True)
        # Bot can continue but Gemini features won't work

# Initialize Google Sheets client
try:
    sheets_service = init_google_sheets_client()
    logger.info("Google Sheets client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Google Sheets client: {e}", exc_info=True)
    sheets_service = None # Handle cases where initialization fails

# --- Main Bot Function ---
def main() -> None:
    """Start the bot."""
    if not sheets_service:
        logger.critical("Google Sheets service not available. Bot cannot function properly. Exiting.")
        return

    if not GEMINI_CONFIGURED:
         logger.warning("Gemini API Key not configured or configuration failed. Expense analysis via message will not work.")
         # Consider disabling the message handler if Gemini is critical

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Pass config/services to handlers via bot_data
    application.bot_data['sheets_service'] = sheets_service
    application.bot_data['master_sheet_id'] = os.getenv("MASTER_SHEET_ID")
    application.bot_data['service_account_email'] = os.getenv("SERVICE_ACCOUNT_EMAIL")
    application.bot_data['gemini_configured'] = GEMINI_CONFIGURED # Pass status to handlers if needed

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("register", register))

    # Only add message handler if Gemini is configured (optional, but prevents errors)
    if GEMINI_CONFIGURED:
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("Message handler for expense analysis enabled.")
    else:
        logger.warning("Message handler for expense analysis disabled due to Gemini configuration issue.")


    # Run the bot
    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
