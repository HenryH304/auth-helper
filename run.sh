#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Install or update dependencies
pip install -q -r requirements.txt

# Run the application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
