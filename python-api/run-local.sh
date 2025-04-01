#!/bin/bash

# Set environment to development
export FLASK_ENV=development

# Force bind to localhost for local development
# This ensures the app will respond to localhost:5000 instead of just 127.0.0.1:5000
export FLASK_RUN_HOST=localhost
export FLASK_RUN_PORT=5000

# Run the Flask application
python -m flask run --host=localhost