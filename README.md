# MoneyMate Bot

A Telegram bot designed to help manage finances by interacting with Google Sheets and potentially leveraging the Gemini API for advanced features.

## Features (Inferred)

* Connects to Google Sheets to read/write financial data.
* Integrates with the Gemini API (purpose to be defined - e.g., analysis, insights).
* Provides bot commands via Telegram.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/lvminhnhat/Money-mate-bot.git
   cd Money-mate-bot
   ```
2. **Create and activate a virtual environment (Recommended):**

   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```
4. **Set up Credentials:**

   * **Google Sheets API:**
     * Follow the Google Cloud documentation to enable the Google Sheets API and create service account credentials.
     * Download the credentials JSON file.
     * Place the downloaded JSON file inside the `credentials/` directory (e.g., `credentials/your-google-credentials.json`).
     * **Important:** Ensure the `credentials/` directory and the specific `.json` file name match what's expected in `google_sheets_api.py` or are configured appropriately. The `.gitignore` file is set up to ignore `credentials/*.json`.
   * **Gemini API:**
     * Obtain an API key from Google AI Studio or Google Cloud.
     * Configure the API key as needed within the application (e.g., environment variable, configuration file - check `gemini_api.py` for details).
   * **Telegram Bot Token:**
     * Create a bot using BotFather on Telegram to get your bot token.
     * Configure the token within the application (e.g., environment variable, configuration file - check `main.py` or `bot_handlers.py`).
5. **Run the bot:**

   ```bash
   python main.py
   ```

## Running with Docker

1. **Build the Docker image:**
   Make sure you have Docker installed and running.

   ```bash
   docker build -t monymate-bot .
   ```

2. **Run the Docker container:**

    **Method 1: Passing environment variables directly**

    You need to pass your Telegram Bot Token, Gemini API Key, Master Sheet ID, and Service Account Email as environment variables. Replace the placeholder values with your actual credentials.
    ```bash
    docker run -d --name monymate-container \
        -e TELEGRAM_BOT_TOKEN=<YOUR_TELEGRAM_BOT_TOKEN> \
        -e GEMINI_API_KEY=<YOUR_GEMINI_API_KEY> \
        -e MASTER_SHEET_ID=<YOUR_MASTER_SHEET_ID> \
        -e SERVICE_ACCOUNT_EMAIL=<YOUR_SERVICE_ACCOUNT_EMAIL> \
        monymate-bot
    ```
    *   `-d`: Run the container in detached mode (in the background).
    *   `--name monymate-container`: Assign a name to the container for easier management.
    *   `-e VARIABLE=value`: Set environment variables required by the application.

    **Method 2: Using a `.env` file**

    a.  Create a file named `.env` in the root directory of the project.
    b.  Add your credentials to the `.env` file like this:

        ```dotenv
        # .env file
        TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
        GEMINI_API_KEY=YOUR_GEMINI_API_KEY
        MASTER_SHEET_ID=YOUR_MASTER_SHEET_ID
        SERVICE_ACCOUNT_EMAIL=YOUR_SERVICE_ACCOUNT_EMAIL
        ```
        **Important:** Make sure the `.env` file is added to your `.gitignore` to avoid committing sensitive information.

    c.  Run the container using the `--env-file` flag:
        ```bash
        docker run -d --name monymate-container --env-file .env monymate-bot
        ```

3. **View logs (Optional):**

   ```bash
   docker logs monymate-container -f
   ```

4. **Stop the container:**

   ```bash
   docker stop monymate-container
   ```

5. **Remove the container:**

   ```bash
   docker rm monymate-container
   ```

## Usage

Interact with the bot on Telegram using the defined commands (check `bot_handlers.py` for available commands).

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
