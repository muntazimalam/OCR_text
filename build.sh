#!/usr/bin/env bash
# Render Build Script
# Installs system dependencies (Tesseract OCR + OpenCV GUI libs) and Python packages

set -o errexit

# Install Tesseract OCR engine + OpenCV runtime libs
apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1
rm -rf /var/lib/apt/lists/*

# Install Python dependencies
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

# Pre-download RapidOCR ONNX models (~15MB) so workers never download at runtime
python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR(intra_op_num_threads=2)" || true
