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


def _yellow_mask(img_bgr: np.ndarray) -> Optional[np.ndarray]:
    """Binary mask of yellow/amber pixels (0/255 uint8) or None if too small."""
    h, w = img_bgr.shape[:2]
    if h < 40 or w < 40:
        return None
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, _YELLOW_HSV_LO, _YELLOW_HSV_HI)
    mask2 = cv2.inRange(hsv, _YELLOW_HSV_MID, _YELLOW_HSV_HI)
    mask = cv2.bitwise_or(mask1, mask2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    return mask


def _locate_yellow_plate_roi(img_bgr: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Localizes the license plate by segmenting the yellow plate background
    (HSV color mask), then scoring hull ROIs by width/aspect ratio.
    Returns (x, y, w, h) of the best plate-like yellow region or None.
    """
    rois = _locate_yellow_plate_rois(img_bgr, top_n=1)
    return rois[0] if rois else None


def _dedupe_regions(rois: List[Tuple[int, int, int, int]], top_n: int) -> List[Tuple[int, int, int, int]]:
    """Collapse heavily overlapping boxes (keep highest score order) and cap count."""
    picks = []
    for roi in rois:
        x, y, w, h = roi
        if any(abs(x - px) < pw * 0.5 and abs(y - py) < ph * 0.5 for (px, py, pw, ph) in picks):
            continue
        picks.append(roi)
        if len(picks) >= top_n:
            break
    return picks


def _locate_yellow_plate_rois(img_bgr: np.ndarray, top_n: int = 5) -> List[Tuple[int, int, int, int]]:
    """
    Returns the top-N candidate yellow/license-plate regions, best first.
    Filters on plate-like aspect ratios and yellow pixel density.
    """
    mask = _yellow_mask(img_bgr)
    if mask is None:
        return []
    h, w = img_bgr.shape[:2]

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = float(h * w)
    scored: List[Tuple[float, Tuple[int, int, int, int]]] = []

    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        aspect = bw / float(bh) if bh > 0 else 0
        frac = area / img_area
        # License plates are wide strips: aspect 1.6-7, not full-frame, not tiny
        if aspect < 1.6 or aspect > 7.0 or bh < 10 or frac < 0.0005 or frac > 0.35:
            continue
        roi_mask = mask[y:y + bh, x:x + bw]
        density = float(cv2.countNonZero(roi_mask)) / max(area, 1)
        if density < 0.55:
            continue
        score = aspect * min(bh / 12.0, 6.0) * (0.6 + density) * (1.0 + frac * 2.0)
        scored.append((score, (x, y, bw, bh)))

    scored.sort(key=lambda s: s[0], reverse=True)
    return _dedupe_regions([roi for _, roi in scored], top_n)


def _ocr_guided_plate_rois(
    img_bgr: np.ndarray,
    ocr_dets: List[Dict[str, Any]],
    top_n: int = 4,
) -> List[Tuple[int, int, int, int]]:
    """
    Combines EasyOCR word boxes with yellow-color evidence to localize plates
    that color segmentation alone misses (small plates overlapping banners).
    """
    mask = _yellow_mask(img_bgr)
    if mask is None:
        return []
    h_img, w_img = img_bgr.shape[:2]

    scored: List[Tuple[float, Tuple[int, int, int, int]]] = []
    for det in ocr_dets:
        box = det.get("box") or det.get("bbox")
        if not box:
            continue
        x, y, w, h = box
        if w < 14 or h < 10:
            continue
        # Plate text boxes are wide and short
        aspect = w / float(h) if h > 0 else 0
        if not 1.5 <= aspect <= 8.0:
            continue
        # Restrict to reasonable box dimensions
        if w > w_img * 0.75 or h > h_img * 0.35:
            continue
        x1 = min(w_img, x + w)
        y1 = min(h_img, y + h)
        box_mask = mask[y:y1, x:x1]
        area = max((x1 - x) * (y1 - y), 1)
        density = float(cv2.countNonZero(box_mask)) / area

        token = det.get("text", "")
        plate_like = _is_plate_like(token)
        digit_run = len(token) >= 8 and sum(1 for c in token if c.isdigit()) == len(token)

        # Yellow density in the OCR box is the strongest plate signal
        if density < 0.20 and not plate_like:
            continue
        if digit_run and density < 0.35:
            # long pure-digit strings are usually phone numbers unless on yellow
            continue

        score = density * 100.0
        score += min(h / 10.0, 6.0) * 2.0
        score += 40.0 if plate_like else 0.0
        score += 80.0 if (density >= 0.45 and plate_like) else 0.0
        pad_x, pad_y = int(w * 0.12), int(h * 0.45)
        roi = (max(0, x - pad_x), max(0, y - pad_y),
               min(w_img, x + w + pad_x) - max(0, x - pad_x),
               min(h_img, y + h + pad_y) - max(0, y - pad_y))
        scored.append((score, roi))

    scored.sort(key=lambda s: s[0], reverse=True)
    return _dedupe_regions([roi for _, roi in scored], top_n)


def _crop_plate_patch(img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """Crops the plate region with padding, upscales, and enhances contrast."""
    x, y, pw, ph = roi
    h_img, w_img = img_bgr.shape[:2]
    pad_x = int(pw * 0.12)
    pad_y = int(ph * 0.45)
    x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
    x1, y1 = min(w_img, x + pw + pad_x), min(h_img, y + ph + pad_y)
    patch = img_bgr[y0:y1, x0:x1]
    if patch.size == 0 or patch.shape[0] < 8 or patch.shape[1] < 24:
        return None

    target_h = 150
    scale = max(target_h / float(patch.shape[0]), 2.0)
    patch = cv2.resize(patch, (int(patch.shape[1] * scale), int(patch.shape[0] * scale)),
                       interpolation=cv2.INTER_CUBIC)

    lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    patch = cv2.cvtColor(cv2.merge((l_ch, a_ch, b_ch)), cv2.COLOR_LAB2BGR)
    return patch


def _is_plate_like(text: str) -> bool:
    """Quick heuristic: 4-14 alphanumeric chars with both letters and digits present."""
    cleaned = re.sub(r"[^A-Z0-9]", "", text.upper())
    if not 4 <= len(cleaned) <= 14:
        return False
    has_alpha = sum(1 for c in cleaned if c.isalpha())
    has_digit = sum(1 for c in cleaned if c.isdigit())
    return has_alpha >= 2 and has_digit >= 2


def _tesseract_extract(img_bgr: np.ndarray, plate_rois: List[tuple] = None) -> Dict[str, Any]:
    """
    Runs Tesseract OCR on detected license plate cropped ROIs for accuracy.
    """
    try:
        import pytesseract
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h_img, w_img = gray.shape[:2]

        if not plate_rois:
            edges = cv2.Canny(gray, 30, 150)
            cnts, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            plate_rois = [(x, y, w, h) for (x, y, w, h) in [cv2.boundingRect(c) for c in cnts]
                          if 1.2 <= (w / float(h) if h > 0 else 0) <= 7.0 and 35 <= w <= (w_img * 0.85) and 12 <= h <= (h_img * 0.45)]

        for (px, py, pw, ph) in plate_rois[:5]:
            roi = gray[py:py+ph, px:px+pw]
            if roi.size == 0:
                continue

            roi_scaled = cv2.resize(roi, (pw * 2, ph * 2), interpolation=cv2.INTER_CUBIC)
            thresh = cv2.adaptiveThreshold(roi_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 31, 10)
            config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            text = pytesseract.image_to_string(thresh, config=config).strip()
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())

            if len(cleaned) >= 4:
                return {
                    "text": cleaned,
                    "confidence": 0.95,
                    "detections": [{"text": cleaned, "confidence": 0.95}]
                }

        return None
    except Exception:
        return None


def _run_easyocr(
    reader,
    img_bgr: np.ndarray,
    min_chars: int = 2,
    with_boxes: bool = False,
) -> Optional[Dict[str, Any]]:
    """Runs EasyOCR on an image and returns normalized detections (or None).

    When `with_boxes` is True, each detection carries an `box: (x, y, w, h)`
    tuple describing the word's bounding rectangle in the input image.
    """
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


def _best_variant_ocr(
    reader,
    patch: np.ndarray,
    min_chars: int = 3,
) -> Optional[Dict[str, Any]]:
    """Runs EasyOCR on multiple enhancements of a plate crop, returns the best.

    Prefers a reading that looks like a plate; otherwise highest total confidence.
    """
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    variants = {
        "color": patch,
        "clahe": cv2.cvtColor(cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray), cv2.COLOR_GRAY2BGR),
    }
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    variants["thresh"] = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)

    best, best_key = None, -1.0
    for img_var in variants.values():
        res = _run_easyocr(reader, img_var, min_chars=min_chars)
        if not res:
            continue
        text = res.get("text", "")
        conf_sum = sum(d.get("confidence", 0.0) for d in res.get("detections", []))
        key = conf_sum + (200.0 if _is_plate_like(text) else 0.0)
        if key > best_key:
            best, best_key = res, key
        if _is_plate_like(text):
            break
    return best


def _merge_ocr_results(*results: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merges multiple OCR results, keeping the better source first and deduplicating."""
    merged_dets: List[Dict[str, Any]] = []
    for res in results:
        if not res:
            continue
        try:
            for det in res.get("detections", []):
                key = det.get("text")
                if key and key not in [d["text"] for d in merged_dets]:
                    merged_dets.append(det)
        except Exception:
            continue

    if not merged_dets:
        for res in results:
            if res and res.get("text"):
                cleaned = re.sub(r'[^A-Z0-9]', '', str(res["text"]).upper())
                if cleaned:
                    merged_dets.append({"text": cleaned, "confidence": res.get("confidence", 0.8)})
                break

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
    License-plate-aware OCR engine:
      1. OCR the full image (gets word boxes)
      2. Score each word box as a plate candidate (yellow density × shape × text)
      3. Re-OCR the top plate candidate crops at high resolution (multi-variant)
      4. Fall back to pure yellow-region crops if nothing plate-like surfaced
      5. Merge plate-crop readings first, full-image context second
    """
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        try:
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return {"text": None, "confidence": None, "error": "Image decode failed"}

            h, w = img.shape[:2]
            if max(h, w) > 1024:
                scale = 1024.0 / max(h, w)
                img_small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                img_small = img

            reader = _get_easyocr_reader()
            if reader is None:
                tess_result = _tesseract_extract(img)
                if tess_result:
                    return tess_result
                return {"text": "", "confidence": 0.0, "detections": []}

            # 1. Full-image OCR with word boxes
            full_result = _run_easyocr(reader, img_small, min_chars=2, with_boxes=True)
            crop_results: List[Dict[str, Any]] = []
            calls = 0

            # 2. OCR-guided plate crops (primary)
            if full_result:
                guided_rois = _ocr_guided_plate_rois(img, full_result.get("detections", []), top_n=4)
                for roi in guided_rois:
                    if calls >= _MAX_CROP_OCR_CALLS:
                        break
                    patch = _crop_plate_patch(img, roi)
                    if patch is None:
                        continue
                    res = _best_variant_ocr(reader, patch, min_chars=3)
                    calls += 1
                    if res and _is_plate_like(res.get("text", "")):
                        crop_results.append(res)
                        break

            # 3. Pure yellow-region crops (secondary)
            if not crop_results:
                for roi in _locate_yellow_plate_rois(img, top_n=3):
                    if calls >= _MAX_CROP_OCR_CALLS:
                        break
                    patch = _crop_plate_patch(img, roi)
                    if patch is None:
                        continue
                    res = _best_variant_ocr(reader, patch, min_chars=3)
                    calls += 1
                    if res and _is_plate_like(res.get("text", "")):
                        crop_results.append(res)
                        break

            combined = _merge_ocr_results(*(crop_results + [full_result]))
            gc.collect()
            return combined

        except Exception as e:
            gc.collect()
            return {"text": None, "confidence": None, "error": str(e)}