import os
import sys
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import cv2
import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageFont
from app.analyzers.ocr import OCRAnalyzer
from app.analyzers.number_plate import NumberPlateAnalyzer
from app.services.analysis_service import AnalysisService
from app.core.database import SessionLocal
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
import uuid

def generate_perfect_sample():
    user_home = os.path.expanduser("~")
    downloads_dir = os.path.join(user_home, "Downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    out_path = os.path.join(downloads_dir, "perfect_vehicle_pass_sample.jpg")

    # Create high quality 1024x768 image with sharp contrast
    pil_img = PILImage.new("RGB", (1024, 768), color=(200, 205, 210))
    draw = ImageDraw.Draw(pil_img)

    # Draw realistic vehicle body (Navy Blue SUV)
    draw.rectangle([120, 260, 904, 620], fill=(25, 45, 85), outline=(15, 25, 50), width=6)
    draw.rectangle([220, 160, 804, 300], fill=(40, 60, 105), outline=(15, 25, 50), width=4)
    # Windshield
    draw.polygon([(250, 175), (774, 175), (834, 280), (190, 280)], fill=(120, 150, 180), outline=(20, 30, 60), width=3)
    # Headlights
    draw.rectangle([150, 320, 260, 390], fill=(240, 240, 210), outline=(50, 50, 50), width=3)
    draw.rectangle([764, 320, 874, 390], fill=(240, 240, 210), outline=(50, 50, 50), width=3)

    # License Plate Box (Clean White plate with sharp black border)
    plate_x1, plate_y1, plate_x2, plate_y2 = 362, 440, 662, 530
    draw.rectangle([plate_x1, plate_y1, plate_x2, plate_y2], fill=(255, 255, 255), outline=(0, 0, 0), width=6)

    # Try loading bold system font (Arial/Arial Bold/Impact/Calibri)
    font = None
    for font_name in ["arialbd.ttf", "arial.ttf", "impact.ttf", "calibri.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            font = ImageFont.truetype(font_name, 52)
            break
        except Exception:
            continue
    
    if font is None:
        font = ImageFont.load_default()

    # Draw plate text: KA01AB1234
    draw.text((plate_x1 + 18, plate_y1 + 14), "KA01AB1234", fill=(0, 0, 0), font=font)

    pil_img.save(out_path, quality=95)
    print(f"Generated sample saved to: {out_path}")

    # Run analysis pipeline
    with open(out_path, "rb") as f:
        file_bytes = f.read()

    db = SessionLocal()
    img_id = uuid.uuid4()
    stored_name, stored_path = StorageService.save_image(file_bytes, "perfect_vehicle_pass_sample.jpg", img_id)
    ImageService.create_image(
        db, img_id, "perfect_vehicle_pass_sample.jpg", stored_name, stored_path,
        "image/jpeg", len(file_bytes), 1024, 768, "hash_perfect_sample"
    )

    result = AnalysisService().run_pipeline(db, img_id, stored_path, "hash_perfect_sample")
    db.close()

    print("\n--- Pipeline Verification Results ---")
    print(f"Overall Score: {result.get('overall_score') * 100}%")
    print(f"Is Failed: {result.get('is_failed')}")
    print(f"License Plate Valid: {result.get('plate_valid')} ({result.get('ocr_text')})")
    print(f"Is Blurry: {result.get('is_blurry')}")
    print(f"Brightness Status: {result.get('brightness_status')}")
    print(f"Issues Count: {len(result.get('issues'))}")

if __name__ == "__main__":
    generate_perfect_sample()
