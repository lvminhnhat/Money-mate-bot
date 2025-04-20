from datetime import date, datetime
import os
import logging
import google.generativeai as genai
import json

logger = logging.getLogger(__name__)

# --- Configuration ---
# Configuration logic removed. It should be done in main.py.

# --- Constants ---
MODEL_NAME = "gemini-2.0-flash" # Or another suitable model

# --- Core Function ---

def analyze_expense_message(message_text: str) -> dict | None:
    """
    Analyzes a user's message using Gemini to determine its type (transaction, analysis, or other)
    and extracts relevant details.

    Assumes genai library has been configured previously in main.py.

    Args:
        message_text: The raw text message from the user.

    Returns:
        A dictionary containing extracted data or None if analysis fails.
    """
    logger.debug("Entered analyze_expense_message function (updated version).") # Add entry log

    try:
        # This will raise an exception if genai is not configured in main.py
        model = genai.GenerativeModel(MODEL_NAME)

        # --- Updated Prompt ---
        prompt = f"""
Phân tích tin nhắn sau đây để xác định xem nó thuộc loại nào trong ba loại sau:
1.  **Ghi giao dịch:** Yêu cầu ghi lại một khoản thu (income) hoặc chi tiêu (expense).
2.  **Yêu cầu phân tích:** Yêu cầu thống kê, báo cáo, hoặc phân tích dữ liệu chi tiêu/thu nhập (ví dụ: "tháng này tiêu bao nhiêu", "thống kê chi tiêu theo danh mục", "thu nhập 3 tháng gần nhất").
3.  **Khác:** Các loại tin nhắn khác không liên quan.

**Kết quả trả về PHẢI là một đối tượng JSON duy nhất với các trường sau:**
- `request_type`: (string) Giá trị là một trong: "transaction", "analysis", "other".
- `is_income`: (boolean) True nếu là ghi khoản thu, False nếu không.
- `is_expense`: (boolean) True nếu là ghi khoản chi, False nếu không.
- `amount`: (number hoặc null) Số tiền nếu là ghi giao dịch.
- `category`: (string hoặc null) Danh mục nếu là ghi giao dịch (chọn từ danh sách: "Ăn uống & Đồ uống", "Đi lại", "Nhà ở", "Mua sắm", "Giải trí", "Sức khỏe", "Giáo dục", "Hóa đơn & Tiện ích", "Cá nhân", "Cho vay", "Vay tiền", "Khác").
- `description`: (string hoặc null) Mô tả nếu là ghi giao dịch.
- `analysis_query`: (string hoặc null) Câu truy vấn/yêu cầu phân tích của người dùng nếu `request_type` là "analysis". Giữ nguyên ý nghĩa của yêu cầu gốc.

**QUAN TRỌNG:**
- Nếu là `request_type: "transaction"`, các trường `is_income`, `is_expense`, `amount`, `category`, `description` phải được điền phù hợp. `analysis_query` là null.
- Nếu là `request_type: "analysis"`, trường `analysis_query` phải chứa yêu cầu phân tích. Các trường giao dịch (`is_income`, `is_expense`, `amount`, `category`, `description`) là null hoặc false.
- Nếu là `request_type: "other"`, tất cả các trường khác là null hoặc false.

**Chỉ trả về JSON, không giải thích gì thêm.**

Ví dụ:

Tin nhắn: "sáng nay ăn phở hết 50k ở quán gần nhà"
Kết quả:
```json
{{
  "request_type": "transaction",
  "is_income": false,
  "is_expense": true,
  "amount": 50000.0,
  "category": "Ăn uống & Đồ uống",
  "description": "Phở sáng ở quán gần nhà",
  "analysis_query": null
}}
```

Tin nhắn: "nhận lương tháng này 20 triệu"
Kết quả:
```json
{{
  "request_type": "transaction",
  "is_income": true,
  "is_expense": false,
  "amount": 20000000.0,
  "category": "Khác",
  "description": "Nhận lương tháng này",
  "analysis_query": null
}}
```

Tin nhắn: "thống kê chi tiêu tháng này theo danh mục"
Kết quả:
```json
{{
  "request_type": "analysis",
  "is_income": false,
  "is_expense": false,
  "amount": null,
  "category": null,
  "description": null,
  "analysis_query": "thống kê chi tiêu tháng này theo danh mục"
}}
```

Tin nhắn: "hôm nay trời đẹp quá"
Kết quả:
```json
{{
  "request_type": "other",
  "is_income": false,
  "is_expense": false,
  "amount": null,
  "category": null,
  "description": null,
  "analysis_query": null
}}
```

---
Bây giờ, phân tích tin nhắn sau:

Tin nhắn: "{message_text}"
Kết quả:
"""
        # --- End of Updated Prompt ---

        # Configure response to be JSON
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )

        logger.debug(f"Sending prompt to Gemini for message: '{message_text}'")
        response = model.generate_content(prompt, generation_config=generation_config)

        # Clean up potential markdown backticks if the model includes them
        cleaned_response_text = response.text.strip().strip('```json').strip('```').strip()
        logger.debug(f"Raw Gemini response text: {response.text}")
        logger.debug(f"Cleaned Gemini response text: {cleaned_response_text}")

        # Parse the JSON response
        try:
            result_json = json.loads(cleaned_response_text)
            # Basic validation of expected keys
            required_keys = ["request_type", "is_income", "is_expense", "amount", "category", "description", "analysis_query"]
            if not all(k in result_json for k in required_keys):
                 logger.warning(f"Gemini response missing expected keys: {result_json}")
                 # Return a default 'other' type if structure is wrong
                 return {"request_type": "other", "is_income": False, "is_expense": False, "amount": None, "category": None, "description": None, "analysis_query": None}

            request_type = result_json.get("request_type")

            # Validate based on request_type
            if request_type == "transaction":
                # Validate category if it's an expense or income
                if (result_json.get("is_expense") or result_json.get("is_income")) and result_json.get("category") not in [
                    "Ăn uống & Đồ uống", "Đi lại", "Nhà ở", "Mua sắm",
                    "Giải trí", "Sức khỏe", "Giáo dục", "Hóa đơn & Tiện ích",
                    "Cá nhân", "Cho vay", "Vay tiền", "Khác", None
                ]:
                    logger.warning(f"Gemini returned invalid category '{result_json.get('category')}' for transaction. Setting to 'Khác'.")
                    result_json["category"] = "Khác"
                # Ensure amount is float or None
                if result_json.get("amount") is not None:
                    try:
                        result_json["amount"] = float(result_json["amount"])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert amount '{result_json['amount']}' to float for transaction. Setting amount to None.")
                        result_json["amount"] = None
                else: # Amount is required for transaction
                     logger.warning(f"Gemini identified transaction but amount is null. Treating as 'other'.")
                     result_json["request_type"] = "other"

            elif request_type == "analysis":
                if not result_json.get("analysis_query"):
                    logger.warning(f"Gemini identified analysis but analysis_query is null. Treating as 'other'.")
                    result_json["request_type"] = "other"
            elif request_type == "other":
                pass # No specific validation needed
            else:
                logger.warning(f"Gemini returned unknown request_type: '{request_type}'. Treating as 'other'.")
                result_json["request_type"] = "other"

            logger.info(f"Successfully parsed Gemini response: {result_json}")
            return result_json

        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to decode JSON response from Gemini: {json_err}. Response text: '{cleaned_response_text}'", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred processing Gemini response: {e}. Response text: '{cleaned_response_text}'", exc_info=True)
            return None

    except Exception as e:
        # This will catch errors if genai wasn't configured or other API issues
        logger.error(f"An error occurred calling the Gemini API (check configuration in main.py?): {e}", exc_info=True)
        return None

def generate_expense_report(user_query: str, expense_data: list[dict]) -> tuple[str | None, str | None]:
    """Generates an expense analysis report using Gemini.

    Args:
        user_query: The user's natural language query for analysis.
        expense_data: A list of dictionaries representing expense records.

    Returns:
        A tuple containing:
        - str: Natural language summary of the analysis.
        - str: JSON string formatted for charting, or None if generation fails.
        Returns (None, None) if an error occurs.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set.")
        return None, None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') # Or your preferred model

        # Convert expense data to a JSON string for the prompt
        try:
            expense_data_json_str = json.dumps(expense_data, indent=2, ensure_ascii=False)
        except TypeError as e:
            logger.error(f"Error converting expense data to JSON: {e}")
            # Fallback: try converting problematic fields to string
            try:
                cleaned_data = [{k: str(v) if isinstance(v, (datetime, date)) else v for k, v in item.items()} for item in expense_data]
                expense_data_json_str = json.dumps(cleaned_data, indent=2, ensure_ascii=False)
            except Exception as inner_e:
                logger.error(f"Could not serialize expense data even after cleaning: {inner_e}")
                return "Error: Could not process expense data for analysis.", None

        # Construct the prompt for Gemini
        prompt = f"""
        Analyze the following transaction data (including income 'Thu' and expenses 'Chi') based on the user's request.

        User Request: "{user_query}"

        Transaction Data (JSON format):
        ```json
        {expense_data_json_str}
        ```

        Instructions:
        1. Provide a concise summary of the analysis in natural language (Vietnamese). Format the summary clearly using Markdown for readability (e.g., headings, bullet points, bold text). Include relevant emojis (like 💰, 💸, 📊, 🗓️) to make it visually appealing. Categorize information logically based on the user's request.
        2. Provide a JSON object suitable for creating charts. **Determine the most appropriate chart type (e.g., `line`, `bar`, `pie`) based on the user's request and the nature of the data.** Structure the JSON logically.
           - Use Vietnamese for labels.
           - **Crucially, label datasets clearly to distinguish between income ('Thu') and expenses ('Chi') (e.g., using "Tổng Thu", "Tổng Chi" in the dataset label). This is needed for correct color coding.**

        Output Format:
        Return your response as a single JSON object containing two keys:
        - "summary": (string) The Markdown-formatted natural language summary with emojis.
        - "chart_json": (object) The JSON data for the chosen chart type.

        Example chart_json for LINE chart (monthly income vs. expense):
        {{ "type": "line", "data": {{ "labels": ["2025-01", "2025-02", "2025-03"], "datasets": [{{ "label": "Tổng Thu", "data": [10000000, 12000000, 11500000] }}, {{ "label": "Tổng Chi", "data": [8000000, 9500000, 9200000] }}] }} }}
        Example chart_json for BAR chart (expenses by category):
        {{ "type": "bar", "data": {{ "labels": ["Ăn uống", "Đi lại", "Giải trí"], "datasets": [{{ "label": "Tổng Chi", "data": [500000, 150000, 200000] }}] }} }}
        Example chart_json for PIE chart (expense distribution):
        {{ "type": "pie", "data": {{ "labels": ["Ăn uống", "Đi lại", "Giải trí"], "datasets": [{{ "label": "Phân bổ chi tiêu", "data": [500000, 150000, 200000] }}] }} }}

        Ensure the entire output is a valid JSON object.
        """

        logger.info(f"Sending analysis request to Gemini for query: '{user_query}'")
        # logger.debug(f"Gemini Prompt:\n{prompt}") # Optional: log the full prompt

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                # candidate_count=1, # Already default
                # stop_sequences=['\n\n'], # Might stop too early
                # max_output_tokens=1024, # Adjust as needed
                temperature=0.7 # Adjust creativity/factuality
            ),
            # safety_settings=... # Optional: configure safety settings
        )

        # Debug: Log the raw response text
        try:
            raw_response_text = response.text
            logger.debug(f"Raw Gemini response text:\n{raw_response_text}")
        except Exception as e:
            logger.warning(f"Could not access response.text: {e}")
            logger.debug(f"Full Gemini response object: {response}")
            return "Error: Could not get text from Gemini response.", None

        # Attempt to parse the response as JSON
        try:
            # Clean the response text: remove potential markdown backticks
            cleaned_response_text = raw_response_text.strip().strip('```json').strip('```').strip()
            logger.debug(f"Cleaned Gemini response text for JSON parsing:\n{cleaned_response_text}")
            result_json = json.loads(cleaned_response_text)
            summary = result_json.get("summary")
            chart_data = result_json.get("chart_json")

            if not summary or not chart_data:
                logger.warning("Gemini response JSON is missing 'summary' or 'chart_json' key.")
                # Fallback: return the raw text as summary if parsing failed structurally
                return raw_response_text, None

            # Convert chart_data back to JSON string for return
            chart_json_str = json.dumps(chart_data, ensure_ascii=False)

            logger.info("Successfully received and parsed analysis from Gemini.")
            return summary, chart_json_str

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Gemini response as JSON: {e}")
            logger.error(f"Problematic response text: {cleaned_response_text}")
            # Return the raw text as the summary, indicating JSON failure
            return f"Received analysis summary (but failed to parse chart data):\n\n{raw_response_text}", None
        except Exception as e:
            logger.error(f"Error processing Gemini response: {e}", exc_info=True)
            return f"Error processing Gemini response: {e}", None

    except genai.types.generation_types.BlockedPromptException as e:
        logger.error(f"Gemini request blocked due to safety settings: {e}")
        return "Your request could not be processed due to safety filters.", None
    except Exception as e:
        logger.error(f"An unexpected error occurred during Gemini API call: {e}", exc_info=True)
        return f"An error occurred while contacting the analysis service: {e}", None

# --- NEW FUNCTION for General Conversation ---
def generate_general_response(message_text: str) -> str | None:
    """Generates a conversational response using Gemini for non-transaction/analysis messages."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set for general response.")
        return None

    try:
        # Ensure genai is configured (though it should be by main.py)
        # genai.configure(api_key=api_key) # Configuration should happen once in main.py
        model = genai.GenerativeModel('gemini-1.5-flash') # Use a suitable model

        prompt = f"""
        Bạn là một trợ lý hữu ích. Hãy trả lời tin nhắn sau đây của người dùng một cách tự nhiên và thân thiện bằng tiếng Việt. Sử dụng định dạng Markdown nếu phù hợp (ví dụ: danh sách, chữ đậm).

        Tin nhắn người dùng: "{message_text}"

        Câu trả lời của bạn:
        """

        logger.info(f"Sending general query to Gemini: '{message_text}'")
        response = model.generate_content(prompt)

        # Log the raw response for debugging
        try:
            raw_response_text = response.text
            logger.debug(f"Raw Gemini general response text:\n{raw_response_text}")
            return raw_response_text
        except Exception as e:
            logger.warning(f"Could not access response.text for general query: {e}")
            logger.debug(f"Full Gemini response object: {response}")
            # Attempt to access parts if available
            try:
                if response.parts:
                    return "\n".join(part.text for part in response.parts if hasattr(part, 'text'))
            except Exception as inner_e:
                 logger.error(f"Could not extract text from response parts either: {inner_e}")
            return "Xin lỗi, tôi không thể xử lý phản hồi từ dịch vụ AI."

    except genai.types.generation_types.BlockedPromptException as e:
        logger.error(f"Gemini general request blocked due to safety settings: {e}")
        return "Yêu cầu của bạn không thể được xử lý do bộ lọc an toàn."
    except Exception as e:
        logger.error(f"An unexpected error occurred during Gemini general API call: {e}", exc_info=True)
        return f"Đã xảy ra lỗi khi liên hệ dịch vụ AI: {e}"
