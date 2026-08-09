import csv
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.analyzers.blur import BlurAnalyzer
from app.analyzers.brightness import BrightnessAnalyzer
from app.analyzers.ocr import OCRAnalyzer
from app.analyzers.number_plate import NumberPlateAnalyzer
from app.utils.file_utils import load_image_auto_orient

BLUR = BlurAnalyzer()
BRIGHTNESS = BrightnessAnalyzer()
OCR = OCRAnalyzer()
PLATE = NumberPlateAnalyzer()

INPUT_DIRS = [
    r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\uploads\2026\08",
    r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\uploads\samples",
]

RESULT_FILE = r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\scripts\analysis_report.csv"

def analyze_one(path):
    with open(path, "rb") as f:
        raw = f.read()
    file_bytes, _, _, _ = load_image_auto_orient(raw)
    try:
        blur = BLUR.analyze(path, file_bytes)
    except Exception as e:
        blur = {"score": None, "is_blurry": None, "error": str(e)}
    try:
        brightness = BRIGHTNESS.analyze(path, file_bytes)
    except Exception as e:
        brightness = {"score": None, "status": "error", "error": str(e)}
    try:
        ocr = OCR.analyze(path, file_bytes)
    except Exception as e:
        ocr = {"text": None, "confidence": None, "error": str(e)}
    try:
        plate = PLATE.analyze(path, file_bytes, ocr_result=ocr)
    except Exception as e:
        plate = {"detected": False, "valid": False, "confidence": 0.0, "plate_text": None, "error": str(e)}
    return blur, brightness, ocr, plate

def main():
    files = []
    for d in INPUT_DIRS:
        files.extend(sorted(glob.glob(os.path.join(d, "*.jpg"))))
        files.extend(sorted(glob.glob(os.path.join(d, "*.jpeg"))))
        files.extend(sorted(glob.glob(os.path.join(d, "*.png"))))

    print(f"Total images to analyze: {len(files)}")
    rows = []
    t0 = time.time()
    for i, path in enumerate(files, 1):
        fname = os.path.basename(path)
        blur, brightness, ocr, plate = analyze_one(path)
        rows.append({
            "file": fname,
            "plate_detected": plate.get("detected"),
            "plate_valid": plate.get("valid"),
            "plate_text": plate.get("plate_text"),
            "plate_format": plate.get("format_type"),
            "plate_conf": plate.get("confidence"),
            "ocr_text": (ocr.get("text") or "").replace(" ", "|"),
            "ocr_conf": ocr.get("confidence"),
            "blur_score": round(blur.get("score") or 0, 1),
            "is_blurry": blur.get("is_blurry"),
            "brightness": brightness.get("status"),
            "ocr_error": ocr.get("error"),
        })
        status = "OK " if plate.get("valid") else "MISS"
        print(f"[{i:3}/{len(files)}] {status} {fname[:45]:45} plate={plate.get('plate_text')}  ocr={str(ocr.get('text'))[:40]}")
        elapsed = time.time() - t0
        eta = (elapsed / i) * (len(files) - i)
        print(f"      ETA {eta/60:.1f} min")
        sys.stdout.flush()

    with open(RESULT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    valid = sum(1 for r in rows if r["plate_valid"])
    print(f"\n===== SUMMARY =====")
    print(f"Files analyzed   : {len(rows)}")
    print(f"Plates detected : {valid} ({valid/len(rows)*100:.1f}%)")
    print(f"CSV report      : {RESULT_FILE}")

if __name__ == "__main__":
    main()