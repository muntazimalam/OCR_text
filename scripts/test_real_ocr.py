import cv2
import numpy as np
import os
import re
from PIL import Image, ImageDraw, ImageFont

_CHAR_TEMPLATES = None


def get_char_templates():
    global _CHAR_TEMPLATES
    if _CHAR_TEMPLATES is not None:
        return _CHAR_TEMPLATES

    _CHAR_TEMPLATES = {}
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    font_paths = [
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf",
        "C:\\Windows\\Fonts\\impact.ttf",
    ]

    available_fonts = []
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                available_fonts.append(ImageFont.truetype(fp, 32))
            except Exception:
                pass

    for char in chars:
        char_tmpl_list = []

        # Render PIL font templates
        for font in available_fonts:
            pil_img = Image.new("L", (28, 36), color=0)
            draw = ImageDraw.Draw(pil_img)
            draw.text((2, 0), char, fill=255, font=font)
            char_tmpl_list.append(np.array(pil_img))

        # Render OpenCV Hershey font template
        cv_img = np.zeros((36, 28), dtype=np.uint8)
        cv2.putText(cv_img, char, (2, 30), cv2.FONT_HERSHEY_DUPLEX, 0.95, 255, 2, cv2.LINE_AA)
        char_tmpl_list.append(cv_img)

        _CHAR_TEMPLATES[char] = char_tmpl_list

    return _CHAR_TEMPLATES


def ocr_crop(char_crop: np.ndarray) -> str:
    if char_crop is None or char_crop.size == 0:
        return ""

    h, w = char_crop.shape[:2]
    if h < 4 or w < 2:
        return ""

    # Resize crop to 36x28 template size
    resized = cv2.resize(char_crop, (28, 36), interpolation=cv2.INTER_AREA)

    templates_dict = get_char_templates()
    best_char = ""
    best_score = -1.0

    for char, tmpl_list in templates_dict.items():
        for tmpl in tmpl_list:
            res = cv2.matchTemplate(resized, tmpl, cv2.TM_CCOEFF_NORMED)
            score = float(res[0][0])
            if score > best_score:
                best_score = score
                best_char = char

    return best_char if best_score >= 0.20 else ""


def extract_plate_text_dynamic(img_bgr: np.ndarray) -> str:
    h_img, w_img = img_bgr.shape[:2]
    scale = 800.0 / max(h_img, w_img)
    img = cv2.resize(img_bgr, (int(w_img * scale), int(h_img * scale)))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h_s, w_s = gray.shape[:2]

    # Binary Canny Edges
    edges = cv2.Canny(gray, 30, 150)
    cnts, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    rois = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        aspect = w / float(h) if h > 0 else 0
        if 1.2 <= aspect <= 7.0 and 35 <= w <= (w_s * 0.85) and 12 <= h <= (h_s * 0.45):
            rois.append((x, y, w, h))

    best_text = ""
    max_chars = 0

    for (px, py, pw, ph) in rois:
        roi = gray[py:py+ph, px:px+pw]
        if roi.size == 0:
            continue

        # Binarize plate ROI using Otsu + Adaptive
        roi_blur = cv2.GaussianBlur(roi, (3, 3), 0)
        thresh = cv2.adaptiveThreshold(roi_blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 8)
        
        c_cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        char_boxes = []
        for cc in c_cnts:
            cx, cy, cw, ch = cv2.boundingRect(cc)
            caspect = cw / float(ch) if ch > 0 else 0
            if 0.12 <= caspect <= 1.5 and (ph * 0.20) <= ch <= (ph * 0.95) and cw >= 2:
                crop = thresh[cy:cy+ch, cx:cx+cw]
                char_boxes.append((cx, cy, cw, ch, crop))

        if len(char_boxes) >= 4:
            # Sort by line (Y) then position (X)
            char_boxes.sort(key=lambda b: (b[1] // 16, b[0]))
            recognized = [ocr_crop(crop) for _, _, _, _, crop in char_boxes]
            text = "".join(ch for ch in recognized if ch)
            if len(text) > max_chars:
                max_chars = len(text)
                best_text = text

    return best_text


if __name__ == "__main__":
    tn_path = r"C:\Users\munta\.gemini\antigravity-ide\brain\1fdd01d3-96e0-4fea-ad03-6ee1539a0642\media__1786274970193.jpg"
    if os.path.exists(tn_path):
        tn_img = cv2.imread(tn_path)
        print("Tamil Nadu Rickshaw OCR:", extract_plate_text_dynamic(tn_img))

    mh_path = r"C:\Users\munta\.gemini\antigravity-ide\brain\1fdd01d3-96e0-4fea-ad03-6ee1539a0642\media__1786274970292.jpg"
    if os.path.exists(mh_path):
        mh_img = cv2.imread(mh_path)
        print("Maharashtra Rickshaw OCR:", extract_plate_text_dynamic(mh_img))

    sample_path = os.path.expanduser("~/Downloads/perfect_vehicle_pass_sample.jpg")
    if os.path.exists(sample_path):
        s_img = cv2.imread(sample_path)
        print("Perfect Sample OCR:", extract_plate_text_dynamic(s_img))
