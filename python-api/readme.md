# Document Extraction API (Python/Flask)

A Python API for extracting structured information from document images and PDFs using SAP AI Core and Claude.

## Setup

1. Clone this repository
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables in `.env` file (or copy from `.env.example`)
5. Start the development server:
   ```bash
   python app.py
   ```
   
For production deployment:
```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## API Endpoints

### Health Check
```
GET /health
```
Checks if the service is running properly.

### Upload Document
```
POST /upload
```
or
```
POST /document/upload
```

Uploads a document for processing.

**Request:**
- Content-Type: `multipart/form-data`
- Form field: `file` (JPG, JPEG, PNG, or PDF)

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded successfully",
  "documentId": "36d096ba-13c7-4f47-93f0-30d07430a87b",
  "fileName": "document_36d096ba-13c7-4f47-93f0-30d07430a87b.jpg",
  "fileDetails": {
    "originalName": "invoice.jpg",
    "mimetype": "image/jpeg",
    "size": 123456,
    "path": "uploads/document_36d096ba-13c7-4f47-93f0-30d07430a87b.jpg"
  }
}
```

### Process Document
```
POST /process
```
or
```
POST /document/processDocument
```

Processes an uploaded document to extract structured information.

**Request:**
- Content-Type: `application/json`
- Body:
```json
{
  "documentId": "36d096ba-13c7-4f47-93f0-30d07430a87b"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Document processed successfully",
  "result": {
    "document_type": "Invoice",
    "document_number": "INV-12345",
    "date": "2023-10-15",
    ...
  }
}
```

### Direct Processing (Upload and Process in One Step)
```
POST /document/direct-process
```

Uploads a document and processes it in one request.

**Request:**
- Content-Type: `multipart/form-data`
- Form field: `file` (JPG, JPEG, PNG, or PDF)

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded and processed successfully",
  "documentId": "36d096ba-13c7-4f47-93f0-30d07430a87b",
  "fileName": "document_36d096ba-13c7-4f47-93f0-30d07430a87b.jpg",
  "result": {
    "document_type": "Invoice",
    "document_number": "INV-12345",
    "date": "2023-10-15",
    ...
  }
}
```

## Environment Variables

- `PORT`: Server port (default: 5000)
- `UPLOAD_FOLDER`: Directory for uploaded files (default: "uploads")
- `RESULTS_FOLDER`: Directory for extraction results (default: "results")
- `AI_CORE_CLIENT_ID`: SAP AI Core client ID
- `AI_CORE_CLIENT_SECRET`: SAP AI Core client secret
- `AI_CORE_TOKEN_URL`: Token URL for authentication
- `AI_CORE_DEPLOYMENT_URL`: Deployment URL for the AI model
- `AI_CORE_RESOURCE_GROUP`: AI Core resource group (default: "default")
- `FLASK_ENV`: Set to "development" for debug mode

## File Structure

- `app.py`: Main Flask application
- `uploads/`: Directory for uploaded documents
- `results/`: Directory for extraction results
- `requirements.txt`: Python dependencies

## Error Handling

The API has comprehensive error handling for:
- Invalid file types
- Missing files
- Authentication failures
- Processing errors

All errors return a clear message and appropriate HTTP status code.