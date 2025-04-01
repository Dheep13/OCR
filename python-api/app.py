import os
import uuid
import json
import base64
import logging
import socket
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import requests
from dotenv import load_dotenv
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)  # ⚠️ Safe only for local/dev
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5000,http://localhost:3000,http://127.0.0.1:5000').split(',')
CORS(app, origins=allowed_origins)

# Configuration
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['RESULTS_FOLDER'] = os.environ.get('RESULTS_FOLDER', 'results')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
app.config['ALLOWED_EXTENSIONS'] = {'jpg', 'jpeg', 'png', 'pdf'}

# AI Core configuration
AI_CORE_CONFIG = {
    'client_id': os.environ.get('AI_CORE_CLIENT_ID', 'sb-b8a7ae41-2697-4aa8-b7e0-77a0db961376!b537485|aicore!b540'),
    'client_secret': os.environ.get('AI_CORE_CLIENT_SECRET', '14739ea1-4086-4d68-91cb-4ab17431570a$4-OXza2NtQiAOqr0ZUC0-6LHIiJlLq61Ch7DNAjbxK8='),
    'token_url': os.environ.get('AI_CORE_TOKEN_URL', 'https://subdomainaicore.authentication.eu10.hana.ondemand.com/oauth/token'),
    'deployment_url': os.environ.get('AI_CORE_DEPLOYMENT_URL', 'https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d429c1c3626932c4/invoke'),
    'resource_group': os.environ.get('AI_CORE_RESOURCE_GROUP', 'default')
}

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Token cache
token_cache = {
    'token': None,
    'expiry': None
}

def allowed_file(filename):
    """Check if the file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_token():
    """Get authentication token with caching"""
    current_time = datetime.now()
    
    # Return cached token if still valid
    if token_cache['token'] and token_cache['expiry'] and token_cache['expiry'] > current_time:
        logger.info("Using cached token")
        return token_cache['token']
    
    try:
        logger.info("Requesting new token")
        response = requests.post(
            AI_CORE_CONFIG['token_url'],
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={
                'grant_type': 'client_credentials',
                'client_id': AI_CORE_CONFIG['client_id'],
                'client_secret': AI_CORE_CONFIG['client_secret']
            }
        )
        
        response.raise_for_status()
        data = response.json()
        
        # Cache the token
        token_cache['token'] = data['access_token']
        # Set expiry 5 minutes before actual expiry to be safe
        token_cache['expiry'] = current_time + timedelta(seconds=data['expires_in'] - 300)
        
        return token_cache['token']
    except Exception as e:
        logger.error(f"Error getting token: {str(e)}")
        raise Exception(f"Authentication failed: {str(e)}")

def process_document(file_path):
    """Process document using Claude API"""
    try:
        # Get token
        token = get_token()
        
        # Read and prepare the image
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        base64_image = base64.b64encode(file_content).decode('utf-8')
        file_ext = os.path.splitext(file_path)[1][1:].lower()
        
        # Handle jpg extension
        mime_type = f"image/jpeg" if file_ext == 'jpg' else f"image/{file_ext}"
        
        # Create enhanced base prompt
        base_prompt = """
        I have a business document that appears to be an invoice, purchase order, receipt, or similar document.
        
        Please extract all relevant information from this document and organize it into a structured JSON format with the following fields:
        - document_type: The type of document (invoice, purchase order, receipt, etc.)
        - document_number: Any reference or document numbers
        - date: Date on the document (convert to YYYY-MM-DD format)
        - vendor_information: Name, address, contact info of the vendor/supplier
        - customer_information: Name, address, contact info of the customer if present
        - amounts: All monetary amounts (subtotal, tax, total, etc.)
        - line_items: An array of items with these fields for each:
          * item_number: The exact item/product number as displayed. Be extremely precise with alphanumeric item codes - preserve exact characters. Beware of visual confusions: 8/B, 0/O, 5/S, 1/I, S/5, E/B, Z/2. Consecutive similar codes (like "HZ1048SS" followed by "HZ1048S8P") should be distinguished carefully.
          * quantity: The numerical quantity ordered
          * unit_measure: The unit of measure (e.g., EA, PCS, etc.)
          * description: The full item description exactly as shown
          * unit_cost: The cost per unit as a number
          * amount: The total amount for this line item as a number
        - payment_information: Terms, methods, etc.
        - shipping_information: Shipping method, carrier, tracking number, etc. if present
        - additional_references: PO numbers, requisition numbers, or other reference numbers
        - taxes_and_fees: Breakdown of taxes, fees, and other charges
        
        Additionally, include a confidence score for each extracted field. Add a parallel structure called "confidence" with the same hierarchy as the main data, where each field contains a value between 0.0 and 1.0 indicating your confidence in the extraction. For example:
        {
          "document_type": "Invoice",
          "document_number": "INV-12345", 
          "confidence": {
            "document_type": 0.95,
            "document_number": 0.85
          }
        }
        
        Important:
        - Pay extra attention to item numbers - they must be exact
        - Double-check all numerical values - ensure they match the document precisely
        - Ensure description fields capture full text exactly as shown
        - Do not omit any line items
        - Provide realistic confidence scores based on clarity/quality of the text in the document
        - For dates, ensure consistent YYYY-MM-DD format
        - Extract complete address information whenever possible
        - If you're unsure about categorizing information, include it in additional_references
        
        Format the response as clean, structured JSON only. No explanatory text.
        """
        
        # Call the Claude API
        logger.info(f"Calling Claude API for document: {file_path}")
        response = requests.post(
            AI_CORE_CONFIG['deployment_url'],
            headers={
                'Authorization': f"Bearer {token}",
                'AI-Resource-Group': AI_CORE_CONFIG['resource_group'],
                'Content-Type': 'application/json'
            },
            json={
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.0,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": base_prompt
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64_image
                            }
                        }
                    ]
                }]
            }
        )
        
        response.raise_for_status()
        return response.json()
    
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise Exception(f"Document processing failed: {str(e)}")

def extract_json_from_response(result):
    """Extract JSON from Claude's response"""
    if result.get('content') and len(result['content']) > 0 and result['content'][0].get('text'):
        content = result['content'][0]['text']
        
        try:
            # Try to find JSON pattern in response
            import re
            json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', content) or re.search(r'({[\s\S]*})', content)
            
            if json_match:
                return json.loads(json_match.group(1))
        except Exception as e:
            logger.warning(f"Could not parse JSON from response: {str(e)}")
    
    # Return the original result if we can't extract JSON
    return result

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Use platform-independent system info
    import platform
    
    return jsonify({
        'status': 'ok',
        'system': platform.system(),
        'hostname': socket.gethostname(),
        'timestamp': datetime.now().isoformat(),
        'ai_core_configured': bool(AI_CORE_CONFIG['client_secret'])
    })
@app.route('/upload', methods=['POST'])
@app.route('/document/upload', methods=['POST'])
def upload_document():
    """Upload a document"""
    try:
        # Check if file part exists in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file part in the request'
            }), 400
        
        file = request.files['file']
        
        # Check if file is empty
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected'
            }), 400
        
        # Check if file type is allowed
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'message': 'File type not allowed. Only PDF, JPEG, and PNG files are supported.'
            }), 400
        
        # Generate a unique ID and secure filename
        document_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        extension = os.path.splitext(original_filename)[1]
        filename = f"document_{document_id}{extension}"
        
        # Save the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        logger.info(f"File uploaded: {file_path}")
        
        return jsonify({
            'success': True,
            'message': 'Document uploaded successfully',
            'documentId': document_id,
            'fileName': filename,
            'fileDetails': {
                'originalName': original_filename,
                'mimetype': file.content_type,
                'size': os.path.getsize(file_path),
                'path': file_path
            }
        })
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Upload failed: {str(e)}"
        }), 500

@app.route('/process', methods=['POST'])
@app.route('/document/processDocument', methods=['POST'])
def process_document_route():
    """Process a document"""
    try:
        data = request.json
        
        if not data or 'documentId' not in data:
            return jsonify({
                'success': False,
                'message': 'No document ID provided'
            }), 400
        
        document_id = data['documentId']
        
        # Find the file in uploads directory
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if document_id in filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Process the document
                result = process_document(file_path)
                
                # Save the result
                timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
                result_filename = f"result_{document_id}_{timestamp}.json"
                result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
                
                with open(result_path, 'w') as f:
                    json.dump(result, f, indent=2)
                
                # Extract JSON from the response
                extracted_data = extract_json_from_response(result)
                
                return jsonify({
                    'success': True,
                    'message': 'Document processed successfully',
                    'result': extracted_data
                })
        
        # If no file found
        return jsonify({
            'success': False,
            'message': 'Document not found'
        }), 404
    
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Processing failed: {str(e)}"
        }), 500

@app.route('/document/direct-process', methods=['POST'])
def direct_process():
    """Upload and process a document in one step"""
    try:
        # Check if file part exists in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file part in the request'
            }), 400
        
        file = request.files['file']
        
        # Check if file is empty
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected'
            }), 400
        
        # Check if file type is allowed
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'message': 'File type not allowed. Only PDF, JPEG, and PNG files are supported.'
            }), 400
        
        # Generate a unique ID and secure filename
        document_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        extension = os.path.splitext(original_filename)[1]
        filename = f"document_{document_id}{extension}"
        
        # Save the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        logger.info(f"File uploaded for direct processing: {file_path}")
        
        # Process the document
        result = process_document(file_path)
        
        # Save the result
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        result_filename = f"result_{document_id}_{timestamp}.json"
        result_path = os.path.join(app.config['RESULTS_FOLDER'], result_filename)
        
        with open(result_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Extract JSON from the response
        extracted_data = extract_json_from_response(result)
        
        return jsonify({
            'success': True,
            'message': 'Document uploaded and processed successfully',
            'documentId': document_id,
            'fileName': filename,
            'result': extracted_data
        })
    
    except Exception as e:
        logger.error(f"Direct processing error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Processing failed: {str(e)}"
        }), 500

# Main entry point
if __name__ == '__main__':
    # Get port from CF environment variable or use 5000 as default
    port = int(os.environ.get('PORT', 5000))
    
    # Determine if we're in development mode
    is_dev = os.environ.get('FLASK_ENV') == 'development'
    
    # In development, use explicit localhost binding
    # In production or CF, bind to all interfaces with 0.0.0.0
    # This ensures the app can handle requests to localhost in all environments
    host = 'localhost' if is_dev else '0.0.0.0'
    
    logger.info(f"Starting server on {host}:{port}, development mode: {is_dev}")
    app.run(host=host, port=port, debug=is_dev)