# Bank Statement Converter

A modern web application that converts PDF bank statements into structured Excel spreadsheets or Google Sheets. Supports both text-based and scanned PDFs from South African and international banks.

## Features

- 📄 **PDF Parsing**: Extract transaction data from any bank's PDF statement
- 🔍 **Smart OCR**: Cloud-based OCR for scanned PDFs (OCR.space API)
- 📊 **Excel Export**: Generate formatted .xlsx files
- 📑 **Google Sheets**: Direct export to Google Sheets
- 🏦 **Multi-Bank Support**: Works with Standard Bank, FNB, ABSA, Nedbank, Capitec, and international banks
- 🔒 **Privacy-First**: Files deleted immediately after download
- 📱 **Mobile-Friendly**: Responsive design works on all devices

## Quick Start

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd "e:\Google Antigravity\Bank statement converter"
   ```

2. **Install Python dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Start the backend server**
   ```bash
   python app.py
   ```
   The API will start on `http://localhost:5000`

4. **Open the frontend** (in a new terminal/command prompt)
   ```bash
   cd ../frontend
   ```
   Then open `index.html` in your web browser, or use a simple HTTP server:
   ```bash
   python -m http.server 8000
   ```
   Navigate to `http://localhost:8000`

## Usage

1. **Upload PDF**: Drag and drop or browse to select your bank statement PDF
2. **Choose Format**: Select Excel (.xlsx) or Google Sheets output
3. **Convert**: Click "Convert to Spreadsheet"
4. **Download**: Download your formatted spreadsheet or open in Google Sheets

## Output Format

Every spreadsheet includes the following columns:
- **Date**: Transaction date (DD/MM/YYYY)
- **Description**: Transaction description
- **Reference**: Reference number/code
- **Debit**: Debit amount
- **Credit**: Credit amount
- **Balance**: Account balance (if available)

## Supported Banks

### South African Banks
- Standard Bank
- FNB (First National Bank)
- ABSA
- Nedbank
- Capitec

### International Banks
- Most major international banks with standard statement formats

## Google Sheets Integration (Optional)

To enable Google Sheets export:

1. Create a Google Cloud Project
2. Enable the Google Sheets API
3. Create a Service Account and download the JSON key
4. Save the key as `service_account.json` in the `backend` folder

If Google Sheets credentials are not configured, the app will automatically fall back to Excel export.

## Project Structure

```
Bank statement converter/
├── backend/
│   ├── app.py                      # Flask API server
│   ├── pdf_parser.py               # PDF extraction & OCR
│   ├── transaction_processor.py    # Data normalization
│   ├── excel_generator.py          # Excel file creation
│   ├── google_sheets_exporter.py   # Google Sheets integration
│   ├── requirements.txt            #Python dependencies
│   ├── uploads/                    # Temporary PDF storage
│   └── outputs/                    # Generated Excel files
├── frontend/
│   ├── index.html                  # Main UI
│   ├── style.css                   # Styling
│   └── app.js                      # Frontend logic
└── README.md
```

## API Endpoints

- `GET /api/health` - Health check
- `POST /api/convert` - Upload and convert PDF
- `GET /api/download/<job_id>` - Download Excel file
- `POST /api/cleanup/<job_id>` - Delete uploaded files

## Troubleshooting

### PDF not parsing correctly
- Ensure the PDF is a bank statement with transaction tables
- Try with both text-based and scanned PDFs
- Check that the PDF is not password-protected

### OCR not working
- The app uses OCR.space cloud API (free tier)
- If you exceed the free tier limits (25,000 requests/month), you may need to sign up for a paid plan or use your own API key

### Google Sheets not working
- Ensure you have created and configured the `service_account.json` file
- The app will automatically fall back to Excel if credentials are missing

## Technologies Used

### Backend
- **Flask**: Web framework
- **pdfplumber**: PDF text extraction
- **OCR.space API**: Cloud OCR for scanned PDFs
- **openpyxl**: Excel file generation
- **Google Sheets API**: Google Sheets integration
- **pandas**: Data processing

### Frontend
- **HTML5**: Structure
- **CSS3**: Styling with modern gradients and animations
- **Vanilla JavaScript**: Logic and API communication

## Security & Privacy

- All uploaded PDFs are stored temporarily and deleted immediately after download
- No financial data is retained on the server
- Files are processed locally on your server
- For production deployment, ensure HTTPS is enabled

## License

This project is provided as-is for educational and personal use.

## Contributing

Contributions welcome! Please test thoroughly with various bank statement formats.
