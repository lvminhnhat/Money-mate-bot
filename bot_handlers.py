import logging
import re
import os
from telegram import Update, error as telegram_error  # Import error submodule
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from telegram.helpers import escape_markdown  # Import escape_markdown
from googleapiclient.errors import HttpError
import io

from google_sheets_api import get_user_sheet_id, add_user_to_master_sheet, append_expense_to_sheet, get_all_expenses_for_analysis
from gemini_api import analyze_expense_message, generate_expense_report
from utils import generate_chart_from_json

logger = logging.getLogger(__name__)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    await update.message.reply_text(
        "Chào mừng bạn đến với Bot Quản lý Chi tiêu!\n"
        "Gửi /register <URL_Google_Sheet> để đăng ký.\n"
        "Sau khi đăng ký, bạn có thể nhắn tin chi tiêu tự nhiên để ghi lại.\n"
        "Gửi /help để xem hướng dẫn chi tiết."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    service_account_email = context.bot_data.get('service_account_email')

    if service_account_email:
        escaped_email = re.sub(r"([._\-+()<>!#])", r"\\\1", service_account_email)
        share_instruction = f"    \\- *QUAN TRỌNG:* Chia sẻ quyền 'Người chỉnh sửa' \\(Editor\\) cho Sheet của bạn với địa chỉ email: `{escaped_email}`\\. Nếu không, bot sẽ không thể ghi dữ liệu\\.\n\n"
    else:
        logger.warning("SERVICE_ACCOUNT_EMAIL not found in bot_data. Help message will not display the email.")
        share_instruction = f"    \\- *QUAN TRỌNG:* Chia sẻ quyền 'Người chỉnh sửa' \\(Editor\\) cho Sheet của bạn với địa chỉ email dịch vụ của bot \\(chưa được cấu hình trong bot\\)\\. Nếu không, bot sẽ không thể ghi dữ liệu\\.\n\n"

    help_text = (
        "*Hướng dẫn sử dụng Bot Quản lý Chi tiêu:*\n\n"
        "1\\.  *Đăng ký:*\n"
        "    \\- Tạo một Google Sheet mới cho riêng bạn\\.\n"
        "    \\- Lấy URL của Sheet đó\\.\n"
        f"    \\- Gửi lệnh: `/register <URL_Google_Sheet_Của_Bạn>`\n"
        f"{share_instruction}"
        "2\\.  *Ghi chi tiêu:*\n"
        "    \\- Sau khi đăng ký thành công và chia sẻ quyền, chỉ cần nhắn tin mô tả khoản chi tiêu của bạn một cách tự nhiên\\.\n"
        "    \\- Ví dụ: 'sáng ăn phở 50k', 'đổ xăng 100000 đồng', 'mua sách online hết 250 nghìn cho việc học'\n"
        "    \\- Bot sẽ tự động phân tích và ghi vào Google Sheet của bạn\\.\n\n"
        "3\\.  *Lưu ý:*\n"
        "    \\- Bot chỉ xử lý các tin nhắn văn bản thông thường, không phải lệnh\\.\n"
        "    \\- Nếu tin nhắn không được hiểu là một khoản chi tiêu, bot sẽ bỏ qua\\.\n"
        "    \\- Dữ liệu được ghi vào Sheet gồm: Ngày, Số tiền, Danh mục, Ghi chú \\(nếu có\\)\\."
    )
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True
    )

def extract_sheet_id_from_url(url: str) -> str | None:
    """Extracts the Google Sheet ID from a URL."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    return None

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registers the user by linking their Telegram ID to their Google Sheet ID."""
    logger.info(f"Entered REGISTER command handler for user {update.effective_user.id}")
    user = update.effective_user
    user_id = user.id
    logger.info(f"Received /register command from user {user_id} ({user.username or 'no_username'})")

    sheets_service = context.bot_data.get('sheets_service')
    master_sheet_id = context.bot_data.get('master_sheet_id')
    service_account_email = context.bot_data.get('service_account_email')

    if not context.args:
        logger.warning(f"User {user_id} called /register without arguments.")
        await update.message.reply_text("Vui lòng cung cấp URL Google Sheet của bạn sau lệnh /register.\nVí dụ: /register https://docs.google.com/spreadsheets/d/...")
        return

    sheet_url = context.args[0]
    logger.debug(f"User {user_id} provided URL: {sheet_url}")

    sheet_id = extract_sheet_id_from_url(sheet_url)
    logger.debug(f"Extracted Sheet ID for user {user_id}: {sheet_id}")

    if not sheet_id:
        logger.warning(f"Invalid Google Sheet URL provided by user {user_id}: {sheet_url}")
        await update.message.reply_text("URL Google Sheet không hợp lệ. Vui lòng kiểm tra lại.")
        return

    if not sheets_service or not master_sheet_id:
        logger.error(f"Sheets service or Master Sheet ID not found in bot_data for user {user_id} during registration.")
        await update.message.reply_text("Đã xảy ra lỗi cấu hình bot. Vui lòng liên hệ quản trị viên.")
        return

    if not service_account_email:
        logger.error(f"SERVICE_ACCOUNT_EMAIL not found in bot_data. Cannot provide email in registration success message for user {user_id}.")
        try:
            success = add_user_to_master_sheet(sheets_service, master_sheet_id, str(user_id), sheet_id)
            if success:
                 await update.message.reply_text(
                    "✅ Đăng ký/Cập nhật thành công\!\n"
                    "**QUAN TRỌNG:** Hãy nhớ chia sẻ quyền 'Người chỉnh sửa' \(Editor\) cho Google Sheet của bạn với địa chỉ email dịch vụ của bot \(chưa được cấu hình trong bot\)\.",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else:
                 await update.message.reply_text("Không thể cập nhật thông tin đăng ký. Vui lòng thử lại.")
        except Exception as e:
             logger.error(f"Error during registration after SERVICE_ACCOUNT_EMAIL check for user {user_id}: {e}", exc_info=True)
             await update.message.reply_text("Đã xảy ra lỗi trong quá trình đăng ký.")
        return

    logger.info(f"Attempting to register/update user {user_id} with Sheet ID {sheet_id} in Master Sheet {master_sheet_id}")
    try:
        success = add_user_to_master_sheet(sheets_service, master_sheet_id, str(user_id), sheet_id)
        logger.info(f"add_user_to_master_sheet call for user {user_id} returned: {success}")

        if success:
            logger.info(f"Successfully registered/updated user {user_id} with Sheet ID {sheet_id}")
            reply_text = (
                f"✅ Đăng ký/Cập nhật thành công\!\n"
                f"**QUAN TRỌNG:** Hãy nhớ chia sẻ quyền 'Người chỉnh sửa' \(Editor\) cho Google Sheet của bạn với địa chỉ email:\n"
                f"`{service_account_email}`\n"
                f"Nếu không, tôi sẽ không thể ghi chi tiêu giúp bạn\."
            )
            logger.debug(f"Sending success message to user {user_id}")
            await update.message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN_V2)
            logger.debug(f"Successfully sent success message to user {user_id}")
        else:
            logger.warning(f"add_user_to_master_sheet failed for user {user_id} (returned False).")
            reply_text = "Không thể cập nhật thông tin đăng ký vào Master Sheet. Có thể đã xảy ra lỗi API. Vui lòng thử lại hoặc kiểm tra log."
            logger.debug(f"Sending failure message to user {user_id}")
            await update.message.reply_text(reply_text)
            logger.debug(f"Successfully sent failure message to user {user_id}")

    except HttpError as http_err:
        logger.error(f"Google Sheets API error during registration for user {user_id}: {http_err}", exc_info=True)
        reply_text = f"Đã xảy ra lỗi API Google Sheets ({http_err.resp.status}) trong quá trình đăng ký. Vui lòng thử lại sau."
        if http_err.resp.status == 403:
            reply_text += f"\nLỗi 403 thường do bot không có quyền ghi vào Master Sheet."
        logger.debug(f"Sending API error message to user {user_id}")
        try:
            await update.message.reply_text(reply_text)
            logger.debug(f"Successfully sent API error message to user {user_id}")
        except Exception as send_error:
            logger.error(f"Failed to send API error message to user {user_id}: {send_error}")
    except Exception as e:
        logger.error(f"Unexpected error during registration for user {user_id}: {e}", exc_info=True)
        reply_text = "Đã xảy ra lỗi không mong muốn trong quá trình đăng ký. Vui lòng thử lại sau."
        logger.debug(f"Sending unexpected error message to user {user_id}")
        try:
            await update.message.reply_text(reply_text)
            logger.debug(f"Successfully sent unexpected error message to user {user_id}")
        except Exception as send_error:
            logger.error(f"Failed to send unexpected error message to user {user_id}: {send_error}")

# --- Message Handler ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles regular text messages for logging transactions OR triggering analysis."""
    user_id = str(update.effective_user.id)
    message_text = update.message.text

    logger.info(f"Received message from user {user_id}: '{message_text}'")

    # --- Get context data ---
    sheets_service = context.bot_data.get('sheets_service')
    master_sheet_id = context.bot_data.get('master_sheet_id')
    service_account_email = context.bot_data.get('service_account_email')

    if not sheets_service or not master_sheet_id:
        logger.error("Sheets service or Master Sheet ID not found in bot_data during message handling.")
        return

    # --- Check user registration ---
    try:
        user_sheet_id = get_user_sheet_id(sheets_service, master_sheet_id, user_id)
        if not user_sheet_id:
            logger.info(f"User {user_id} is not registered. Ignoring message.")
            return
    except Exception as e:
        logger.error(f"Error checking registration for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Đã xảy ra lỗi khi kiểm tra đăng ký của bạn.")
        return

    logger.info(f"User {user_id} is registered with Sheet ID {user_sheet_id}.")

    # --- Analyze message with Gemini ---
    try:
        analysis_result = analyze_expense_message(message_text)
        logger.debug(f"Gemini initial analysis result for user {user_id}: {analysis_result}")

        if not analysis_result:
             logger.warning(f"Gemini initial analysis returned None for user {user_id}. Message: '{message_text}'")
             return

        request_type = analysis_result.get("request_type")

        # --- Handle based on request type ---
        if request_type == "transaction":
            # --- Log Transaction ---
            amount = analysis_result.get("amount")
            category = analysis_result.get("category")
            description = analysis_result.get("description", "")
            transaction_type = "Thu" if analysis_result.get("is_income") else "Chi"

            if amount is not None and category:
                try:
                    success = append_expense_to_sheet(sheets_service, user_sheet_id, amount, category, description, transaction_type)
                    if success:
                        logger.info(f"Successfully appended {transaction_type} for user {user_id} to sheet {user_sheet_id}")
                        log_type_msg = "thu nhập" if transaction_type == "Thu" else "chi tiêu"
                        await update.message.reply_text(f"✅ Đã ghi {log_type_msg}: {amount:,.0f} - {category}")
                    else:
                        if service_account_email:
                             await update.message.reply_text(f"⚠️ Không thể ghi vào Google Sheet\. Bạn đã chia sẻ quyền Editor cho `{service_account_email}` chưa\?")
                        else:
                             await update.message.reply_text("⚠️ Không thể ghi vào Google Sheet\. Vui lòng kiểm tra quyền chia sẻ với email dịch vụ của bot \(chưa được cấu hình trong bot\)\.")

                except HttpError as http_err:
                    logger.error(f"Google Sheets API error appending transaction for user {user_id}: {http_err}", exc_info=True)
                    if http_err.resp.status == 403:
                         if service_account_email:
                              await update.message.reply_text(f"⚠️ Lỗi quyền truy cập\! Vui lòng kiểm tra lại bạn đã chia sẻ quyền 'Người chỉnh sửa' \(Editor\) cho Google Sheet với `{service_account_email}` chưa\.")
                         else:
                              await update.message.reply_text("⚠️ Lỗi quyền truy cập\! Vui lòng kiểm tra lại bạn đã chia sẻ quyền 'Người chỉnh sửa' \(Editor\) cho Google Sheet với email dịch vụ của bot \(chưa được cấu hình trong bot\)\.")
                    elif http_err.resp.status == 404:
                         await update.message.reply_text(f"⚠️ Không tìm thấy Google Sheet. URL bạn đăng ký có đúng không?")
                    else:
                        await update.message.reply_text(f"Đã xảy ra lỗi API ({http_err.resp.status}) khi ghi vào Google Sheet.")
                except Exception as e:
                    logger.error(f"Unexpected error appending transaction for user {user_id}: {e}", exc_info=True)
                    await update.message.reply_text("Đã xảy ra lỗi không mong muốn khi ghi vào Google Sheet.")
            else:
                logger.info(f"Gemini identified transaction, but missing amount or category for user {user_id}. Ignoring.")

        elif request_type == "analysis":
            # --- Perform Analysis ---
            user_query = analysis_result.get("analysis_query")
            if not user_query:
                logger.warning(f"Gemini identified analysis but query is missing for user {user_id}. Ignoring.")
                return

            logger.info(f"Performing analysis for user {user_id} based on query: '{user_query}'")
            await update.message.reply_text(f"Đang phân tích yêu cầu: \"{user_query}\"... 📊")

            try:
                all_transactions = get_all_expenses_for_analysis(sheets_service, user_sheet_id)
                if not all_transactions:
                    await update.message.reply_text("Không tìm thấy dữ liệu giao dịch nào để phân tích.")
                    return
                logger.info(f"Retrieved {len(all_transactions)} transactions for user {user_id} for analysis.")

                summary, chart_json = generate_expense_report(user_query, all_transactions)

                if summary:
                    # Escape Markdown characters in the summary from Gemini
                    escaped_summary = escape_markdown(summary, version=1)  # Use version 1 for ParseMode.MARKDOWN

                    response_message = f"**Kết quả phân tích cho:** \"{user_query}\"\n\n"
                    response_message += escaped_summary  # Use the escaped summary
                    # Ensure the response_message itself doesn't exceed Telegram limits
                    if len(response_message) > 4096:
                        logger.warning(f"Analysis summary for user {user_id} is too long after escaping. Truncating.")
                        response_message = response_message[:4090] + "..."  # Basic truncation

                    logger.debug(f"Sending analysis summary to user {user_id}: {response_message[:200]}...")  # Log beginning of message
                    try:
                        await update.message.reply_text(response_message, parse_mode=ParseMode.MARKDOWN)
                    except telegram_error.BadRequest as e:  # Use the imported error
                        logger.error(f"Still failed to send analysis summary after escaping for user {user_id}. Error: {e}. Message content: {response_message}", exc_info=True)
                        await update.message.reply_text("Đã có lỗi khi định dạng kết quả phân tích. Vui lòng thử lại.")
                    except Exception as send_err:
                        logger.error(f"Failed to send analysis summary for user {user_id}: {send_err}", exc_info=True)
                        await update.message.reply_text("Không thể gửi kết quả phân tích.")

                    if chart_json:
                        logger.info(f"Attempting to generate chart from JSON for user {user_id}.")
                        chart_image_buffer = generate_chart_from_json(chart_json)
                        if chart_image_buffer:
                            try:
                                await update.message.reply_photo(photo=chart_image_buffer, caption=f"Biểu đồ: {user_query}")
                                logger.info(f"Successfully sent chart image to user {user_id}.")
                            except Exception as e:
                                logger.error(f"Failed to send chart photo to user {user_id}: {e}", exc_info=True)
                                await update.message.reply_text("Đã tạo biểu đồ nhưng không thể gửi được.")
                            finally:
                                chart_image_buffer.close()
                        else:
                            logger.warning(f"Failed to generate chart image from JSON for user {user_id}.")
                    else:
                        logger.info(f"No chart JSON provided by Gemini analysis for user {user_id}.")

                else:
                    await update.message.reply_text("Xin lỗi, đã có lỗi xảy ra trong quá trình phân tích chi tiết.")

            except HttpError as e:
                logger.error(f"Google Sheets API error during analysis data retrieval for user {user_id}: {e}", exc_info=True)
                await update.message.reply_text("Lỗi: Không thể truy cập Google Sheet của bạn để lấy dữ liệu phân tích. Vui lòng kiểm tra quyền chia sẻ.")
            except Exception as e:
                logger.error(f"Unexpected error during analysis execution for user {user_id}: {e}", exc_info=True)
                await update.message.reply_text("Đã xảy ra lỗi không mong muốn khi thực hiện phân tích.")

        elif request_type == "other":
            logger.info(f"Message from user {user_id} identified as 'other' by Gemini. Ignoring.")

        else:
            logger.warning(f"Unknown request_type '{request_type}' received for user {user_id}. Ignoring.")

    except Exception as e:
        logger.error(f"Error in handle_message main try block for user {user_id}: {e}", exc_info=True)

if __name__ == '__main__':
    from telegram.ext import ApplicationBuilder

    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()
