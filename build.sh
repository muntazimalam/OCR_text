#!/usr/bin/env bash
# Render Build Script
# Installs system dependencies (Tesseract OCR) and Python packages

set -o errexit

# Install Tesseract OCR engine (lightweight: ~30MB vs PyTorch/EasyOCR at ~350MB)
apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng
rm -rf /var/lib/apt/lists/*

# Install Python dependencies
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
