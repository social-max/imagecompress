# Multi-Resolution Image Compressor

A web application built with Flask that takes uploaded images and generates 4 different resolution tiers (360p, 480p, 540p, 720p) using high-quality LANCZOS filtering and PSNR-based JPEG optimization.

## How to use
1. Upload your images.
2. Wait for processing.
3. Automatically download a ZIP file containing all optimized versions.

## Deployment
This app is ready to be deployed on **Render.com** or **PythonAnywhere**.
- **Start Command:** `gunicorn app:app`