from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime
import traceback

from pdf_parser import PDFParser
from transaction_processor import TransactionProcessor
from excel_generator import ExcelGenerator
from google_sheets_exporter import GoogleSheetsExporter

# Update Flask to serve frontend static files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')

app = Flask(__name__, 
            static_folder=FRONTEND_DIR, 
            static_url_path='')
CORS(app)

@app.route('/')
def index():
    """Serve the frontend index.html"""
    return send_file(os.path.join(FRONTEND_DIR, 'index.html'))

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Store job data in memory (in production, use Redis or database)
jobs = {}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/convert', methods=['POST'])
def convert_pdf():
    """
    Convert uploaded PDF to Excel/Google Sheets
    
    Expected form data:
    - file: PDF file
    - output_format: 'excel' or 'google_sheets' (optional, defaults to 'excel')
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024)}MB'}), 400
        
        # Check file type
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400
        
        # Get output format
        output_format = request.form.get('output_format', 'excel')
        
        if output_format not in ['excel', 'google_sheets']:
            return jsonify({'error': 'Invalid output format. Must be "excel" or "google_sheets"'}), 400
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{job_id}_{timestamp}_{filename}"
        upload_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(upload_path)
        
        # Process PDF
        print(f"Processing PDF: {upload_path}")
        
        # Step 1: Extract text and parse transactions
        parser = PDFParser(upload_path)
        raw_transactions = parser.parse_transactions()
        
        if not raw_transactions:
            # Clean up uploaded file
            if os.path.exists(upload_path):
                os.remove(upload_path)
            return jsonify({
                'error': 'No transactions found in PDF. Please ensure the PDF contains a bank statement with transaction data.'
            }), 400
        
        print(f"Found {len(raw_transactions)} raw transactions")
        
        # Step 2: Process and normalize transactions
        processor = TransactionProcessor(raw_transactions)
        transactions = processor.process()
        
        if not transactions:
            # Clean up uploaded file
            if os.path.exists(upload_path):
                os.remove(upload_path)
            return jsonify({
                'error': 'Failed to process transactions. The PDF format may not be supported.'
            }), 400
        
        print(f"Processed {len(transactions)} transactions")
        
        # Get summary
        summary = processor.get_summary()
        
        # Step 3: Generate output based on format
        result = {
            'job_id': job_id,
            'status': 'success',
            'transaction_count': len(transactions),
            'summary': summary,
            'output_format': output_format
        }
        
        if output_format == 'excel':
            # Generate Excel file
            excel_gen = ExcelGenerator(transactions, OUTPUT_FOLDER)
            excel_path = excel_gen.generate(f"{job_id}_transactions.xlsx")
            
            result['download_url'] = f"/api/download/{job_id}"
            result['filename'] = f"{job_id}_transactions.xlsx"
            
            # Store job data
            jobs[job_id] = {
                'upload_path': upload_path,
                'output_path': excel_path,
                'format': 'excel',
                'created_at': datetime.now().isoformat()
            }
            
        elif output_format == 'google_sheets':
            # Export to Google Sheets
            try:
                sheets_exporter = GoogleSheetsExporter()
                sheet_title = f"Bank Transactions - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                sheet_url = sheets_exporter.export_transactions(transactions, sheet_title)
                
                result['sheet_url'] = sheet_url
                result['message'] = 'Successfully exported to Google Sheets'
                
                # Clean up immediately for Google Sheets
                if os.path.exists(upload_path):
                    os.remove(upload_path)
                    
            except FileNotFoundError:
                # Google Sheets credentials not found
                # Fall back to Excel
                excel_gen = ExcelGenerator(transactions, OUTPUT_FOLDER)
                excel_path = excel_gen.generate(f"{job_id}_transactions.xlsx")
                
                result['download_url'] = f"/api/download/{job_id}"
                result['filename'] = f"{job_id}_transactions.xlsx"
                result['output_format'] = 'excel'
                result['warning'] = 'Google Sheets credentials not configured. Generated Excel file instead.'
                
                # Store job data
                jobs[job_id] = {
                    'upload_path': upload_path,
                    'output_path': excel_path,
                    'format': 'excel',
                    'created_at': datetime.now().isoformat()
                }
        
        return jsonify(result), 200
        
    except Exception as e:
        # Clean up on error
        if 'upload_path' in locals() and os.path.exists(upload_path):
            os.remove(upload_path)
        
        print(f"Error processing PDF: {str(e)}")
        print(traceback.format_exc())
        
        return jsonify({
            'error': f'Failed to process PDF: {str(e)}',
            'details': 'Please ensure the PDF is a valid bank statement.'
        }), 500


@app.route('/api/download/<job_id>', methods=['GET'])
def download_file(job_id):
    """Download generated Excel file and clean up"""
    try:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found or expired'}), 404
        
        job_data = jobs[job_id]
        output_path = job_data['output_path']
        
        if not os.path.exists(output_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Send file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=os.path.basename(output_path),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Schedule cleanup after download
        # In a production environment, you'd use a background task
        # For now, we'll add a cleanup endpoint
        
        return response
        
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        return jsonify({'error': 'Failed to download file'}), 500


@app.route('/api/cleanup/<job_id>', methods=['POST'])
def cleanup_job(job_id):
    """Clean up job files after download"""
    try:
        if job_id not in jobs:
            return jsonify({'message': 'Job already cleaned up or not found'}), 200
        
        job_data = jobs[job_id]
        
        # Delete uploaded PDF
        if os.path.exists(job_data['upload_path']):
            os.remove(job_data['upload_path'])
            print(f"Deleted upload: {job_data['upload_path']}")
        
        # Delete output file
        if os.path.exists(job_data['output_path']):
            os.remove(job_data['output_path'])
            print(f"Deleted output: {job_data['output_path']}")
        
        # Remove job from memory
        del jobs[job_id]
        
        return jsonify({'message': 'Files cleaned up successfully'}), 200
        
    except Exception as e:
        print(f"Error cleaning up job: {str(e)}")
        return jsonify({'error': 'Failed to clean up files'}), 500


@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Test endpoint to verify API is working"""
    return jsonify({
        'message': 'Bank Statement Converter API is running',
        'version': '1.0.0',
        'endpoints': {
            'convert': '/api/convert',
            'download': '/api/download/<job_id>',
            'cleanup': '/api/cleanup/<job_id>',
            'health': '/api/health'
        }
    })


if __name__ == '__main__':
    print("Starting Bank Statement Converter API...")
    print("Upload folder:", os.path.abspath(UPLOAD_FOLDER))
    print("Output folder:", os.path.abspath(OUTPUT_FOLDER))
    app.run(debug=True, host='0.0.0.0', port=5000)
