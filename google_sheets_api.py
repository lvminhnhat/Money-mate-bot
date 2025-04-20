import os
import logging
import re
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = os.path.join('credentials', 'taikhoantienich-f9e079a3a774.json')
MASTER_SHEET_USER_ID_COL = 'A'
MASTER_SHEET_SHEET_ID_COL = 'B'
USER_SHEET_DATE_COL = 'A'
USER_SHEET_AMOUNT_COL = 'B'
USER_SHEET_CATEGORY_COL = 'C'
USER_SHEET_DESC_COL = 'D'
USER_SHEET_TYPE_COL = 'E' # New column for Type
HEADER_ROW = ["Date", "Amount", "Category", "Description", "Type"]  # Added "Type"

# --- Initialization ---
def init_google_sheets_client():
    """Initializes the Google Sheets API client using service account credentials."""
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        logger.info("Google Sheets API client initialized successfully.")
        return service.spreadsheets()
    except FileNotFoundError:
        logger.error(f"Service account file not found at {SERVICE_ACCOUNT_FILE}. Please ensure it exists and is correctly placed.")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets client: {e}", exc_info=True)
        raise

# --- Master Sheet Operations ---

def get_user_sheet_id(service, master_sheet_id: str, user_id: str) -> str | None:
    """Finds the Google Sheet ID associated with a given Telegram User ID in the Master Sheet."""
    try:
        # Define the range to search (columns A and B of the first sheet)
        range_name = f'{MASTER_SHEET_USER_ID_COL}:{MASTER_SHEET_SHEET_ID_COL}' # Removed 'Sheet1!'
        logger.debug(f"Reading range '{range_name}' from Master Sheet {master_sheet_id}")
        result = service.values().get(spreadsheetId=master_sheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            logger.info(f"Master sheet {master_sheet_id} appears to be empty or no data found in range {range_name}.")
            return None

        for row in values:
            # Ensure row has at least two columns before accessing indices
            if len(row) >= 2 and row[0] == user_id:
                logger.debug(f"Found Sheet ID {row[1]} for User ID {user_id} in Master Sheet.")
                return row[1] # Return the Sheet ID found in the second column

        logger.info(f"User ID {user_id} not found in Master Sheet {master_sheet_id}.")
        return None
    except HttpError as error:
        logger.error(f"An API error occurred while reading Master Sheet {master_sheet_id}: {error}", exc_info=True)
        # Handle specific errors like 403 (permissions) or 404 (not found) if needed
        raise # Re-raise the exception to be handled by the caller
    except Exception as e:
        logger.error(f"An unexpected error occurred while reading Master Sheet {master_sheet_id}: {e}", exc_info=True)
        raise # Re-raise for handling

def add_user_to_master_sheet(service, master_sheet_id: str, user_id: str, sheet_id: str) -> bool:
    """Adds or updates a user's mapping in the Master Sheet (operates on the first visible sheet)."""
    try:
        # 1. Check if user already exists (read columns A:B of the first sheet)
        # Range without sheet name defaults to the first visible sheet
        range_name_read = f'{MASTER_SHEET_USER_ID_COL}:{MASTER_SHEET_SHEET_ID_COL}'
        logger.debug(f"Reading range '{range_name_read}' from Master Sheet {master_sheet_id} to check for user {user_id}")
        result = service.values().get(spreadsheetId=master_sheet_id, range=range_name_read).execute()
        values = result.get('values', [])
        user_row_index = -1
        existing_sheet_id = None

        if values:
            for i, row in enumerate(values):
                 # Check if row has at least user_id column and it matches
                 if len(row) >= 1 and row[0] == user_id:
                    user_row_index = i + 1 # Sheets API is 1-based index
                    if len(row) >= 2:
                        existing_sheet_id = row[1] # Get current sheet_id if it exists
                    break

        # 2. Update or Append to the first visible sheet
        if user_row_index != -1:
            # Update existing row (specify range without sheet name)
            # Check if the sheet ID actually needs updating
            if existing_sheet_id == sheet_id:
                logger.info(f"User {user_id} already registered with the same Sheet ID {sheet_id}. No update needed.")
                return True # Indicate success, no change needed

            range_name_update = f'{MASTER_SHEET_USER_ID_COL}{user_row_index}:{MASTER_SHEET_SHEET_ID_COL}{user_row_index}'
            body = {'values': [[user_id, sheet_id]]}
            logger.info(f"Updating user {user_id} in Master Sheet at range {range_name_update} with new Sheet ID {sheet_id}.")
            service.values().update(
                spreadsheetId=master_sheet_id, range=range_name_update,
                valueInputOption='USER_ENTERED', body=body).execute()
            logger.info(f"Successfully updated user {user_id}.")
        else:
            # Append new row (specify range like 'A1' without sheet name for append)
            # This tells the API to append after the last row of the table starting in A1 of the first sheet.
            range_name_append = 'A1'
            body = {'values': [[user_id, sheet_id]]}
            logger.info(f"Appending new user {user_id} with Sheet ID {sheet_id} to the first sheet of Master Sheet {master_sheet_id}.")
            service.values().append(
                spreadsheetId=master_sheet_id, range=range_name_append,
                valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS', body=body).execute()
            logger.info(f"Successfully appended new user {user_id}.")

        return True # Indicate success

    except HttpError as error:
        logger.error(f"An API error occurred while writing to Master Sheet {master_sheet_id}: {error}", exc_info=True)
        # Handle specific errors (e.g., permissions)
        return False # Indicate failure
    except Exception as e:
        logger.error(f"An unexpected error occurred while writing to Master Sheet {master_sheet_id}: {e}", exc_info=True)
        return False # Indicate failure

# --- User Sheet Operations ---

def _get_or_create_monthly_sheet(service, user_sheet_id: str, sheet_name: str) -> bool:
    """Checks if a sheet exists, creates it with headers if not."""
    try:
        spreadsheet = service.get(spreadsheetId=user_sheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        sheet_exists = any(sheet['properties']['title'] == sheet_name for sheet in sheets)

        if not sheet_exists:
            logger.info(f"Sheet '{sheet_name}' not found in {user_sheet_id}. Creating it.")
            # Create the new sheet
            add_sheet_request = {
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }
            service.batchUpdate(
                spreadsheetId=user_sheet_id,
                body={'requests': [add_sheet_request]}
            ).execute()
            logger.info(f"Successfully created sheet '{sheet_name}'.")

            # Add header row to the new sheet
            header_range = f"{sheet_name}!A1" # Range for the header
            header_body = {'values': [HEADER_ROW]}
            service.values().update(
                spreadsheetId=user_sheet_id,
                range=header_range,
                valueInputOption='USER_ENTERED',
                body=header_body
            ).execute()
            logger.info(f"Added header row to sheet '{sheet_name}'.")
        else:
            logger.debug(f"Sheet '{sheet_name}' already exists in {user_sheet_id}.")

        return True # Indicate success (sheet exists or was created)

    except HttpError as error:
        logger.error(f"API error checking/creating sheet '{sheet_name}' in {user_sheet_id}: {error}", exc_info=True)
        # Re-raise specific errors if needed, e.g., permission denied
        if error.resp.status == 403:
             logger.error("Permission denied. Ensure the bot has editor access to the sheet.")
        return False # Indicate failure
    except Exception as e:
        logger.error(f"Unexpected error checking/creating sheet '{sheet_name}' in {user_sheet_id}: {e}", exc_info=True)
        return False # Indicate failure

def append_expense_to_sheet(service, user_sheet_id: str, amount: float, category: str, description: str, transaction_type: str) -> bool:
    """Appends a new transaction record to the user's sheet, organized by month."""
    try:
        # Get current month and year string (e.g., "2025-04")
        now = datetime.now()
        sheet_name = now.strftime('%Y-%m')
        date_str = now.strftime('%Y-%m-%d %H:%M:%S')

        # Ensure the target monthly sheet exists or create it
        if not _get_or_create_monthly_sheet(service, user_sheet_id, sheet_name):
            logger.error(f"Failed to get or create sheet '{sheet_name}' for user sheet {user_sheet_id}. Aborting append.")
            # Optionally raise an exception here to notify the calling handler more directly
            return False # Indicate failure

        # Prepare the row data
        row_data = [
            date_str,
            float(amount),
            category,
            description,
            transaction_type # Added transaction type
        ]

        # Define the range to append to the specific monthly sheet.
        # Appending to "SheetName!A1" finds the table and appends after it.
        range_name = f"{sheet_name}!A1"

        body = {
            'values': [row_data]
        }

        logger.info(f"Appending expense to sheet '{sheet_name}' in Sheet ID {user_sheet_id}: {row_data}")
        result = service.values().append(
            spreadsheetId=user_sheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()

        updated_range = result.get('updates', {}).get('updatedRange', 'N/A')
        logger.info(f"Append successful. Updated range: {updated_range}")
        return True

    except HttpError as error:
        # Log specific details from HttpError if available
        error_details = error.error_details if hasattr(error, 'error_details') else 'No details'
        logger.error(f"API error appending to sheet '{sheet_name}' in {user_sheet_id}: Status={error.resp.status}, Reason={error.resp.reason}, Details={error_details}", exc_info=True)
        # Re-raise to allow bot_handlers to potentially notify the user
        raise error
    except Exception as e:
        logger.error(f"Unexpected error appending to sheet '{sheet_name}' in {user_sheet_id}: {e}", exc_info=True)
        # Re-raise for generic error handling
        raise

# --- Analysis --- NEW SECTION

def get_all_expenses_for_analysis(service, user_sheet_id: str) -> list[dict]:
    """Reads all transaction data from monthly sheets (YYYY-MM) in a user's spreadsheet."""
    all_expenses = []
    monthly_sheet_pattern = re.compile(r"^\d{4}-\d{2}$") # Pattern for YYYY-MM

    try:
        # 1. Get all sheet names in the spreadsheet
        spreadsheet_metadata = service.get(spreadsheetId=user_sheet_id).execute()
        sheets = spreadsheet_metadata.get('sheets', [])
        logger.info(f"Found {len(sheets)} sheets in spreadsheet {user_sheet_id}.")

        # 2. Iterate through sheets and read data from monthly sheets
        for sheet in sheets:
            sheet_title = sheet.get('properties', {}).get('title')
            if sheet_title and monthly_sheet_pattern.match(sheet_title):
                logger.info(f"Reading data from monthly sheet: {sheet_title}")
                # Range A2:E reads all data starting from the second row in columns A to E
                range_name = f"{sheet_title}!A2:E"
                try:
                    result = service.values().get(spreadsheetId=user_sheet_id, range=range_name).execute()
                    values = result.get('values', [])
                    if not values:
                        logger.info(f"Sheet {sheet_title} has no data (or only headers).")
                        continue

                    # Convert rows to dictionaries
                    for row in values:
                        # Ensure row has enough columns, pad with None if necessary
                        row.extend([None] * (len(HEADER_ROW) - len(row)))
                        expense_record = {
                            HEADER_ROW[0]: row[0], # Date
                            HEADER_ROW[1]: row[1], # Amount
                            HEADER_ROW[2]: row[2], # Category
                            HEADER_ROW[3]: row[3], # Description
                            HEADER_ROW[4]: row[4]  # Type (Thu/Chi)
                        }
                        # Basic validation/cleaning (e.g., convert amount to float)
                        try:
                            if expense_record[HEADER_ROW[1]]:
                                expense_record[HEADER_ROW[1]] = float(str(expense_record[HEADER_ROW[1]]).replace(',', '.')) # Handle comma decimal separator
                            else:
                                expense_record[HEADER_ROW[1]] = 0.0 # Default amount if empty
                        except (ValueError, TypeError):
                            logger.warning(f"Could not convert amount '{row[1]}' to float in sheet {sheet_title}. Skipping amount field for this row.")
                            expense_record[HEADER_ROW[1]] = None # Or set to 0.0 or skip row

                        all_expenses.append(expense_record)
                    logger.info(f"Successfully read {len(values)} rows from {sheet_title}.")

                except HttpError as error:
                    logger.error(f"API error reading sheet '{sheet_title}' in {user_sheet_id}: {error}", exc_info=True)
                    # Decide whether to continue with other sheets or stop
                    continue # Continue processing other sheets
                except Exception as e:
                    logger.error(f"Unexpected error reading sheet '{sheet_title}' in {user_sheet_id}: {e}", exc_info=True)
                    continue # Continue processing other sheets
            # else: logger.debug(f"Skipping sheet '{sheet_title}' as it doesn't match YYYY-MM format.")

        logger.info(f"Finished reading data. Total expense records collected: {len(all_expenses)}")
        return all_expenses

    except HttpError as error:
        logger.error(f"API error getting spreadsheet metadata for {user_sheet_id}: {error}", exc_info=True)
        raise # Re-raise to be handled by the caller
    except Exception as e:
        logger.error(f"Unexpected error getting spreadsheet metadata for {user_sheet_id}: {e}", exc_info=True)
        raise # Re-raise
