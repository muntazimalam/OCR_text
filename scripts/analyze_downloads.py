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

INPUT_DIR = r"C:\Users\munta\Downloads\regingermediagroupvirtualpreplacementtalk8augu"
OUT_CSV = r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\scripts\downloads_report.csv"


def main():
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "*")))
    files = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    print(f"Files: {len(files)}")

    rows = []
    for i, path in enumerate(files, 1):
        fname = os.path.basename(path)
        with open(path, "rb") as fh:
            raw = fh.read()
        fbytes, _, _, _ = load_image_auto_orient(raw)
        img = cv2.imdecode(np.frombuffer(fbytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"[{i}] DECODE-FAIL {fname}")
            rows.append({"file": fname, "note": "decode failed"})
            continue

        ocr = OCR.analyze(path, fbytes)
        plate = PLATE.analyze(path, fbytes, ocr_result=ocr)
        h_img, w_img = img.shape[:2]

        # yellow ROI info from OCR module internals for reporting
        roi = None
        try:
            from app.analyzers import ocr as ocr_mod
            roi = ocr_mod._locate_yellow_plate_roi(img)
        except Exception:
            roi = None

        rows.append({
            "file": fname,
            "size": f"{w_img}x{h_img}",
            "yellow_roi": "N" if roi is None else f"{roi[2]}x{roi[3]}",
            "ocr_text": (ocr.get("text") or "").replace(" ", "|"),
            "ocr_conf": ocr.get("confidence"),
            "plate_detected": plate.get("detected"),
            "plate_valid": plate.get("valid"),
            "plate_text": plate.get("plate_text"),
            "plate_format": plate.get("format_type"),
            "plate_conf": plate.get("confidence"),
        })
        print(f"[{i}] {fname:14} roi={'N' if roi is None else str(roi[2])+'x'+str(roi[3]):9} plate={plate.get('plate_text')}")
        print(f"      ocr: {str(ocr.get('text'))}")
        sys.stdout.flush()

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        flds = ["file", "size", "yellow_roi", "ocr_text", "ocr_conf", "plate_detected", "plate_valid", "plate_text", "plate_format", "plate_conf"]
        writer = csv.DictWriter(f, fieldnames=flds)
        writer.writeheader()
        writer.writerows(rows)

    valid = sum(1 for r in rows if r.get("plate_valid"))
    print(f"\n===== SUMMARY =====")
    print(f"Files analyzed : {len(rows)}")
    print(f"Plates valid   : {valid}/{len(rows)}")
    for r in rows:
        status = "OK " if r.get("plate_valid") else "MISS"
        print(f"   {status} {r['file']:14} -> {r.get('plate_text')}")
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()