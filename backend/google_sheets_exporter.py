from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict
import json
import os


class GoogleSheetsExporter:
    """Export transaction data to Google Sheets"""
    
    # If you want to use service account authentication, set this path
    SERVICE_ACCOUNT_FILE = 'service_account.json'
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    def __init__(self, credentials_json: str = None):
        """
        Initialize with credentials
        
        Args:
            credentials_json: Path to service account JSON file or OAuth credentials
        """
        self.credentials_json = credentials_json or self.SERVICE_ACCOUNT_FILE
        self.service = None
    
    def _get_service(self):
        """Get or create Google Sheets API service"""
        if self.service:
            return self.service
        
        try:
            # Try to load service account credentials
            if os.path.exists(self.credentials_json):
                credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_json, scopes=self.SCOPES
                )
                self.service = build('sheets', 'v4', credentials=credentials)
                return self.service
            else:
                raise FileNotFoundError(
                    "Google Sheets credentials not found. "
                    "Please provide a service account JSON file."
                )
        except Exception as e:
            raise Exception(f"Failed to authenticate with Google Sheets API: {str(e)}")
    
    def create_spreadsheet(self, title: str = "Bank Transactions") -> tuple:
        """
        Create a new Google Spreadsheet
        
        Returns:
            tuple: (spreadsheet_id, spreadsheet_url)
        """
        service = self._get_service()
        
        spreadsheet = {
            'properties': {
                'title': title
            },
            'sheets': [{
                'properties': {
                    'title': 'Transactions',
                    'gridProperties': {
                        'frozenRowCount': 1
                    }
                }
            }]
        }
        
        try:
            spreadsheet = service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId,spreadsheetUrl'
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            
            return spreadsheet_id, spreadsheet_url
            
        except HttpError as error:
            raise Exception(f"Failed to create spreadsheet: {error}")
    
    def export_transactions(self, transactions: List[Dict], spreadsheet_title: str = None) -> str:
        """
        Export transactions to a new Google Sheet
        
        Args:
            transactions: List of transaction dictionaries
            spreadsheet_title: Optional custom title for the spreadsheet
        
        Returns:
            str: URL to the created Google Sheet
        """
        from datetime import datetime
        
        # Create spreadsheet with timestamp
        if not spreadsheet_title:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            spreadsheet_title = f"Bank Transactions - {timestamp}"
        
        spreadsheet_id, spreadsheet_url = self.create_spreadsheet(spreadsheet_title)
        
        # Prepare data
        headers = [["Date", "Description", "Reference", "Debit", "Credit", "Balance"]]
        
        rows = []
        for transaction in transactions:
            row = [
                transaction.get('date', ''),
                transaction.get('description', ''),
                transaction.get('reference', ''),
                transaction.get('debit', ''),
                transaction.get('credit', ''),
                transaction.get('balance', '')
            ]
            rows.append(row)
        
        # Combine headers and data
        values = headers + rows
        
        # Write data to sheet
        body = {
            'values': values
        }
        
        service = self._get_service()
        
        try:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='Transactions!A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Format the sheet
            self._format_sheet(spreadsheet_id)
            
            return spreadsheet_url
            
        except HttpError as error:
            raise Exception(f"Failed to write data to spreadsheet: {error}")
    
    def _format_sheet(self, spreadsheet_id: str):
        """Apply formatting to the spreadsheet"""
        service = self._get_service()
        
        requests = [
            # Format header row
            {
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red': 0.267,
                                'green': 0.447,
                                'blue': 0.769
                            },
                            'textFormat': {
                                'foregroundColor': {
                                    'red': 1.0,
                                    'green': 1.0,
                                    'blue': 1.0
                                },
                                'fontSize': 11,
                                'bold': True
                            },
                            'horizontalAlignment': 'CENTER'
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
                }
            },
            # Auto-resize columns
            {
                'autoResizeDimensions': {
                    'dimensions': {
                        'sheetId': 0,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,
                        'endIndex': 6
                    }
                }
            },
            # Set column widths
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': 0,
                        'dimension': 'COLUMNS',
                        'startIndex': 1,  # Description column
                        'endIndex': 2
                    },
                    'properties': {
                        'pixelSize': 400
                    },
                    'fields': 'pixelSize'
                }
            }
        ]
        
        body = {
            'requests': requests
        }
        
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
        except HttpError as error:
            # Formatting is optional, don't fail if it errors
            print(f"Warning: Failed to format spreadsheet: {error}")
    
    def export_to_existing_sheet(self, transactions: List[Dict], spreadsheet_id: str, range_name: str = "Transactions!A1") -> bool:
        """
        Export transactions to an existing Google Sheet
        
        Args:
            transactions: List of transaction dictionaries
            spreadsheet_id: ID of the existing spreadsheet
            range_name: Range to write to (e.g., "Sheet1!A1")
        
        Returns:
            bool: True if successful
        """
        service = self._get_service()
        
        # Prepare data
        headers = [["Date", "Description", "Reference", "Debit", "Credit", "Balance"]]
        
        rows = []
        for transaction in transactions:
            row = [
                transaction.get('date', ''),
                transaction.get('description', ''),
                transaction.get('reference', ''),
                transaction.get('debit', ''),
                transaction.get('credit', ''),
                transaction.get('balance', '')
            ]
            rows.append(row)
        
        values = headers + rows
        body = {'values': values}
        
        try:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            return True
            
        except HttpError as error:
            raise Exception(f"Failed to update spreadsheet: {error}")
