import csv
import glob
import hashlib
import os
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
OUT_CSV = r"C:\Users\munta\OneDrive\Desktop\media-processing-pipeline\scripts\full_diagnosis.csv"


def find_yellow_plate_roi(img_bgr):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (15, 40, 60), (45, 255, 255))
    mask2 = cv2.inRange(hsv, (45, 40, 60), (60, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_area = None, 0
    h_img, w_img = img_bgr.shape[:2]
    img_area = h_img * w_img
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        aspect = w / float(h) if h > 0 else 0
        frac = area / img_area
        if aspect >= 1.8 and h >= 10 and frac >= 0.0006 and area > best_area:
            best, best_area = (x, y, w, h), area
    return best


def ocr_crop(img, roi):
    x, y, w, h = roi
    h_img, w_img = img.shape[:2]
    pad = int(h * 0.35)
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w_img, x + w + pad), min(h_img, y + h + pad)
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return ocr_full(img)
    scale = 800.0 / max(crop.shape[:2])
    crop_up = cv2.resize(crop, None, fx=max(scale, 2.5), fy=max(scale, 2.5), interpolation=cv2.INTER_CUBIC)
    ok, enc = cv2.imencode(".png", crop_up)
    if not ok:
        return ocr_full(img)
    r = OCR.analyze(None, enc.tobytes())
    return r


def ocr_full(img):
    ok, enc = cv2.imencode(".png", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        return {"text": "", "confidence": 0.0, "detections": []}
    return OCR.analyze(None, enc.tobytes())


def main():
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "*")))
    files = [f for f in files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    print(f"Files: {len(files)}")

    rows = []
    seen_hash = {}
    for i, path in enumerate(files, 1):
        fname = os.path.basename(path)
        with open(path, "rb") as fh:
            raw = fh.read()
        sha = hashlib.sha256(raw).hexdigest()[:12]
        dup_group = seen_hash.get(sha)
        fbytes = None
        try:
            fbytes, _, _, _ = load_image_auto_orient(raw)
            img = cv2.imdecode(np.frombuffer(fbytes, np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            img = None
        if img is None:
            rows.append({"file": fname, "sha": sha, "decode": "FAILED", "bytes": len(raw)})
            print(f"[{i:3}] DECODE-FAIL {fname} ({len(raw)} bytes)")
            sys.stdout.flush()
            continue
        seen_hash.setdefault(sha, fname)
        dup_note = "" if dup_group is None else f"=DUP-OF:{dup_group}"

        h_img, w_img = img.shape[:2]
        roi = find_yellow_plate_roi(img)
        rois = {
            "w": roi[2], "h": roi[3],
            "aspect": round(roi[2] / float(roi[3]), 2),
            "frac": round(roi[2] * roi[3] / (h_img * w_img), 4),
        } if roi else None
        if roi:
            roi = {"x": roi[0], "y": roi[1], "w": roi[2], "h": roi[3]}

        full = ocr_full(img) if not roi else {"text": "", "confidence": 0.0}
        full_plate = PLATE.analyze(None, fbytes, ocr_result=full)
        if roi:
            crop = ocr_crop(img, (roi["x"], roi["y"], roi["w"], roi["h"]))
            crop_plate = PLATE.analyze(None, fbytes, ocr_result=crop)
        else:
            crop, crop_plate = full, full_plate

        rows.append({
            "file": fname,
            "sha": sha,
            "dup": "" if dup_group is None else dup_group,
            "y_roi": "N" if roi is None else f"{roi['w']}x{roi['h']}",
            "frac": "" if roi is None else rois["frac"],
            "full_ocr": (full.get("text") or "").replace(" ", "|"),
            "full_plate": full_plate.get("plate_text"),
            "crop_ocr": (crop.get("text") or "").replace(" ", "|"),
            "crop_plate": crop_plate.get("plate_text"),
        })
        res = crop_plate.get("plate_text") or crop.get("text") or ""
        print(f"[{i:3}] {'ROI' if roi else 'no '} {fname[:45]:45} -> crop_plate={crop_plate.get('plate_text')} {dup_note}")
        print(f"      full_ocr={str(full.get('text'))[:45]:45} crop_ocr={str(crop.get('text'))[:45]}")
        sys.stdout.flush()

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        flds = ["file", "sha", "dup", "y_roi", "frac", "full_ocr", "full_plate", "crop_ocr", "crop_plate"]
        writer = csv.DictWriter(f, fieldnames=flds)
        writer.writeheader()
        writer.writerows(rows)

    unique = [r for r in rows if "decode" not in r]
    with_roi = [r for r in unique if r["y_roi"] != "N"]
    plate_hit_crop = [r for r in unique if r["crop_plate"]]
    plate_hit_full = [r for r in unique if r["full_plate"]]
    fix_gained = [r for r in unique if r["crop_plate"] and not r["full_plate"]]
    print(f"\n===== FINAL SUMMARY =====")
    print(f"Decodable               : {len(unique)}/{len(rows)}")
    print(f"Yellow plate ROI found  : {len(with_roi)}")
    print(f"Plate via FULL OCR      : {len(plate_hit_full)}")
    print(f"Plate via CROP OCR      : {len(plate_hit_crop)}")
    print(f"NEW plates only via crop: {len(fix_gained)}")
    for r in fix_gained:
        print(f"   + {r['file'][:40]:42} -> {r['crop_plate']}")
    print(f"CSV: {OUT_CSV}")


if __name__ == "__main__":
    main()