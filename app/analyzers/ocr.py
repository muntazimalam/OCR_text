import gc
import os
import re
import cv2
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from app.analyzers.base import BaseAnalyzer
from app.core.logging import logger

_CHAR_TEMPLATES = None
_easyocr_reader = None

# HSV bounds for yellow/amber commercial license plates (India yellow plates,
# EU yellow rear plates, taxi plates). Tolerances widened for shadows/compression.
_YELLOW_HSV_LO = (14, 35, 55)
_YELLOW_HSV_MID = (45, 35, 55)
_YELLOW_HSV_HI = (62, 255, 255)

_MAX_CROP_OCR_CALLS = 8


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    try:
        import easyocr
        _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        return _easyocr_reader
    except Exception as e:
        logger.warning("easyocr_init_failed", error=str(e))
        return None


def _locate_plate_rois(img_bgr: np.ndarray, top_n: int = 6) -> List[Tuple[int, int, int, int]]:
    """
    Extracts candidate license plate ROIs regardless of plate color (White, Yellow, Green, Silver, Black)
    using edge and contour shape analysis.
    """
    h_img, w_img = img_bgr.shape[:2]
    if h_img < 40 or w_img < 40:
        return []

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 180)
    cnts, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    img_area = float(h_img * w_img)
    rois = []

    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        aspect = bw / float(bh) if bh > 0 else 0
        area_frac = (bw * bh) / img_area
        if 1.2 <= aspect <= 7.5 and 0.0002 <= area_frac <= 0.30 and bw >= 20 and bh >= 8:
            rois.append((x, y, bw, bh))

    # Deduplicate heavily overlapping bounding boxes
    picks = []
    for r in sorted(rois, key=lambda b: b[2] * b[3], reverse=True):
        x, y, bw, bh = r
        if not any(abs(x - px) < pw * 0.5 and abs(y - py) < ph * 0.5 for (px, py, pw, ph) in picks):
            picks.append(r)
            if len(picks) >= top_n:
                break
    return picks


def _crop_and_enhance_patch(img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """Crops candidate plate patch with padding, upscales, and enhances contrast using CLAHE."""
    x, y, pw, ph = roi
    h_img, w_img = img_bgr.shape[:2]
    pad_x = int(pw * 0.15)
    pad_y = int(ph * 0.35)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w_img, x + pw + pad_x), min(h_img, y + ph + pad_y)
    patch = img_bgr[y0:y1, x0:x1]

    if patch.size == 0 or patch.shape[0] < 6 or patch.shape[1] < 18:
        return None

    target_h = 160
    scale = max(target_h / float(patch.shape[0]), 2.0)
    patch_up = cv2.resize(patch, (int(patch.shape[1] * scale), int(patch.shape[0] * scale)), interpolation=cv2.INTER_CUBIC)

    lab = cv2.cvtColor(patch_up, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    patch_enhanced = cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2BGR)
    return patch_enhanced


def _run_easyocr(
    reader,
    img_bgr: np.ndarray,
    min_chars: int = 2,
    with_boxes: bool = False,
) -> Optional[Dict[str, Any]]:
    """Runs EasyOCR on an image and returns normalized detections (or None)."""
    try:
        results = reader.readtext(img_bgr)
        detections = []
        for res in results:
            if len(res) >= 3:
                quad, text, conf = res[:3]
                text_str = str(text).strip().upper()
                cleaned_str = re.sub(r'[^A-Z0-9]', '', text_str)
                if len(cleaned_str) < min_chars:
                    continue
                det = {"text": cleaned_str, "confidence": float(conf)}
                if with_boxes and quad is not None and len(quad) > 0:
                    xs = [pt[0] for pt in quad if len(pt) >= 2]
                    ys = [pt[1] for pt in quad if len(pt) >= 2]
                    if xs and ys:
                        x0, y0 = float(min(xs)), float(min(ys))
                        x1, y1 = float(max(xs)), float(max(ys))
                        det["box"] = (int(x0), int(y0), int(max(x1 - x0, 1)), int(max(y1 - y0, 1)))
                detections.append(det)
        if detections:
            confs = [d["confidence"] for d in detections]
            return {
                "text": " ".join(d["text"] for d in detections),
                "confidence": round(sum(confs) / len(confs), 2),
                "detections": detections,
            }
        return None
    except Exception as e:
        logger.warning("easyocr_execution_failed", error=str(e))
        return None


def _merge_ocr_results(*results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merges multiple OCR results, keeping distinct unique detections."""
    merged_dets: List[Dict[str, Any]] = []
    seen_texts = set()

    for res in results:
        if not res:
            continue
        for det in res.get("detections", []):
            txt = det.get("text")
            if txt and txt not in seen_texts:
                seen_texts.add(txt)
                merged_dets.append(det)

    if not merged_dets:
        return {"text": "", "confidence": 0.0, "detections": []}

    confs = [d["confidence"] for d in merged_dets if d.get("confidence") is not None]
    return {
        "text": " ".join(d["text"] for d in merged_dets),
        "confidence": round(sum(confs) / len(confs), 2) if confs else 0.0,
        "detections": merged_dets,
    }


class OCRAnalyzer(BaseAnalyzer):
    """
    Universal High-Accuracy License Plate OCR Engine:
    Processes full image at high resolution + crops candidate plate ROIs (white, yellow, green, silver)
    for maximum recognition accuracy across cars, motorcycles, scooters, and trucks.
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"text": None, "confidence": None, "error": "Image decode failed"}

            h, w = img.shape[:2]
            # Maintain high resolution for OCR (up to 1920px max dimension)
            if max(h, w) > 1920:
                scale = 1920.0 / max(h, w)
                img_work = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                img_work = img

            reader = _get_easyocr_reader()
            if reader is None:
                tess_result = _tesseract_extract(img_work)
                if tess_result:
                    return tess_result
                return {"text": "", "confidence": 0.0, "detections": []}

            # 1. Full-image EasyOCR at high resolution
            full_result = _run_easyocr(reader, img_work, min_chars=2, with_boxes=True)

            # 2. Extract candidate plate ROIs (color-agnostic: white, yellow, green, silver)
            crop_results: List[Dict[str, Any]] = []
            plate_rois = _locate_plate_rois(img_work, top_n=6)

            for roi in plate_rois:
                patch = _crop_and_enhance_patch(img_work, roi)
                if patch is not None:
                    c_res = _run_easyocr(reader, patch, min_chars=2, with_boxes=False)
                    if c_res:
                        crop_results.append(c_res)

            combined = _merge_ocr_results(full_result, *crop_results)
            gc.collect()
            return combined

        except Exception as e:
            gc.collect()
            return {"text": None, "confidence": None, "error": str(e)}