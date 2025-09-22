#!/bin/bash

echo "Installing required packages..."
pip3 install -r requirements.txt

echo "Initializing the database..."
python3 setup.py

echo "Starting the Flask application..."
python3 app.py
