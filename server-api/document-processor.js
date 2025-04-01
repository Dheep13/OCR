
const fs = require('fs');
const axios = require('axios');
const path = require('path');

// Replace with your actual credentials
const CLIENT_ID =  'sb-b8a7ae41-2697-4aa8-b7e0-77a0db961376!b537485|aicore!b540';
const CLIENT_SECRET = '14739ea1-4086-4d68-91cb-4ab17431570a$4-OXza2NtQiAOqr0ZUC0-6LHIiJlLq61Ch7DNAjbxK8=';
const IMAGE_PATH = './invoice.jpg'; // Path to your image

// Main function to process document
async function processDocument() {
  try {
    // Step 1: Get authorization token
    console.log('Getting token...');
    const tokenResponse = await axios({
      method: 'post',
      url: 'https://subdomainaicore.authentication.eu10.hana.ondemand.com/oauth/token',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      data: `grant_type=client_credentials&client_id=${CLIENT_ID}&client_secret=${CLIENT_SECRET}`
    });
    
    const token = tokenResponse.data.access_token;
    console.log('Token acquired successfully');
    
    // Step 2: Read and prepare the image
    const imageBuffer = fs.readFileSync(IMAGE_PATH);
    const base64Image = imageBuffer.toString('base64');
    const fileExt = path.extname(IMAGE_PATH).substring(1).toLowerCase();
    const mediaType = fileExt === 'jpg' ? 'image/jpeg' : `image/${fileExt}`;
    // Create enhanced base prompt
const basePrompt = `
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
`;
    
    // Step 3: Call the Claude API
    console.log('Sending image to API...');
    const aiResponse = await axios({
      method: 'post',
      url: 'https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d429c1c3626932c4/invoke',
      headers: {
        'Authorization': `Bearer ${token}`,
        'AI-Resource-Group': 'default',
        'Content-Type': 'application/json'
      },
      data: {
        anthropic_version: "bedrock-2023-05-31",
        max_tokens: 4000,
        temperature: 0.0,
        messages: [{
          role: "user",
          content: [
            {
              type: "text",
              text: basePrompt
            },
            {
              type: "image",
              source: {
                type: "base64",
                media_type: mediaType,
                data: base64Image
              }
            }
          ]
        }]
      }
    });
    
    // Step 4: Display and save the result
    console.log('Response received:');
    console.log(JSON.stringify(aiResponse.data, null, 2));
    
    fs.writeFileSync('result.json', JSON.stringify(aiResponse.data, null, 2));
    console.log('Result saved to result.json');
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
  }
}

// Run the script
processDocument();