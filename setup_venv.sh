#!/bin/bash

set -e

VENV_NAME=".venv"

echo "Creating virtual environment..."
python -m venv $VENV_NAME

echo "Activating virtual environment..."
source $VENV_NAME/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo "Virtual environment setup complete."
echo "Activate it anytime using: $VENV_NAME/bin/activate"
