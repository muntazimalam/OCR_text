import csv
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from app.analyzers.ocr import OCRAnalyzer
from app.analyzers.number_plate import NumberPlateAnalyzer
from app.utils.file_utils import load_image_auto_orient

OCR = OCRAnalyzer()
PLATE = NumberPlateAnalyzer()

INPUT_DIR = r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\uploads\2026\08"


def find_yellow_plate_roi(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (20, 80, 80), (40, 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    h_img, w_img = img_bgr.shape[:2]
    img_area = h_img * w_img
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        aspect = w / float(h) if h > 0 else 0
        frac = area / img_area
        if aspect >= 1.8 and h >= 12 and frac >= 0.0008 and area > best_area:
            best = (x, y, w, h)
            best_area = area
    return best


def analyze_one(path):
    with open(path, "rb") as f:
        raw = f.read()
    file_bytes, _, _, _ = load_image_auto_orient(raw)
    img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h_img, w_img = img.shape[:2]

    roi = find_yellow_plate_roi(img)
    roi_info = None
    if roi:
        x, y, w, h = roi
        # Crop with padding, upscale 3x, run OCR on the crop
        pad = int(h * 0.25)
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w_img, x + w + pad)
        y1 = min(h_img, y + h + pad)
        crop = img[y0:y1, x0:x1]
        if crop.size > 0:
            scale = 600.0 / max(crop.shape[0], crop.shape[1])
            crop_up = cv2.resize(crop, None, fx=max(scale, 2.0), fy=max(scale, 2.0), interpolation=cv2.INTER_CUBIC)
            ok, enc = cv2.imencode(".png", crop_up)
            if ok:
                crop_ocr = OCR.analyze(None, enc.tobytes())
                crop_plate = PLATE.analyze(None, enc.tobytes(), ocr_result=crop_ocr)
                full_ocr = OCR.analyze(None, file_bytes)
                full_plate = PLATE.analyze(None, file_bytes, ocr_result=full_ocr)
                roi_info = {
                    "w": w, "h": h,
                    "aspect": round(w / float(h), 2),
                    "frac": round(w * h / (h_img * w_img), 4),
                    "crop_ocr": (crop_ocr.get("text") or "").replace(" ", "|"),
                    "crop_plate": crop_plate.get("plate_text"),
                    "full_ocr": (full_ocr.get("text") or "").replace(" ", "|"),
                    "full_plate": full_plate.get("plate_text"),
                }

    return roi_info


def main():
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.jpg")))
    images_have_yellow = 0
    images_no_roi = []
    rows = []
    for i, path in enumerate(files, 1):
        fname = os.path.basename(path)
        info = analyze_one(path)
        if info:
            images_have_yellow += 1
            rows.append({"file": fname, **info})
            print(f"[{i:3}] YELLOW {info['w']}x{info['h']} aspect={info['aspect']} frac={info['frac']}")
            print(f"      full : ocr={info['full_ocr'][:50]:50} plate={info['full_plate']}")
            print(f"      crop : ocr={info['crop_ocr'][:50]:50} plate={info['crop_plate']}")
        else:
            images_no_roi.append(fname)
            print(f"[{i:3}] NO-YELLOW-ROI {fname[:45]}")
        sys.stdout.flush()

    print(f"\n===== YELLOW PLATE SUMMARY =====")
    print(f"Images with yellow plate ROI : {images_have_yellow}/{len(files)}")
    print(f"Images WITHOUT yellow ROI    : {len(images_no_roi)}")
    for f in images_no_roi:
        print(f"   - {f}")

    with open(r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\scripts\yellow_roi_report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["file"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()