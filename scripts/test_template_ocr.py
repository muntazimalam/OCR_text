import cv2
import numpy as np
import os
import re

# Generate 36 character templates (A-Z, 0-9)
_CHAR_TEMPLATES = {}

def _init_templates():
    global _CHAR_TEMPLATES
    if _CHAR_TEMPLATES:
        return _CHAR_TEMPLATES

    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    for char in chars:
        # Create 36x24 canvas
        img = np.zeros((36, 24), dtype=np.uint8)
        # Render character
        cv2.putText(img, char, (2, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 255, 2, cv2.LINE_AA)
        _CHAR_TEMPLATES[char] = img

    return _CHAR_TEMPLATES


def recognize_character(char_crop: np.ndarray) -> str:
    templates = _init_templates()
    if char_crop is None or char_crop.size == 0:
        return ""

    # Resize char crop to 36x24
    resized = cv2.resize(char_crop, (24, 36), interpolation=cv2.INTER_AREA)

    best_char = "?"
    best_score = -1.0

    for char, tmpl in templates.items():
        res = cv2.matchTemplate(resized, tmpl, cv2.TM_CCOEFF_NORMED)
        score = float(res[0][0])
        if score > best_score:
            best_score = score
            best_char = char

    return best_char if best_score >= 0.20 else ""


def test_ocr_on_rickshaw():
    img_path = r"C:\Users\munta\.gemini\antigravity-ide\brain\1fdd01d3-96e0-4fea-ad03-6ee1539a0642\media__1786274970193.jpg"
    img = cv2.imread(img_path)
    if img is None:
        print("Image not found")
        return

    h, w = img.shape[:2]
    scale = 800.0 / max(h, w)
    img_small = cv2.resize(img, (int(w * scale), int(h * scale)))
    gray = cv2.cvtColor(img_small, cv2.COLOR_BGR2GRAY)

    # Plate ROI on side of rickshaw: x=190..300, y=360..430
    roi = gray[360:440, 190:310]
    _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    char_crops = []
    for c in cnts:
        x, y, cw, ch = cv2.boundingRect(c)
        aspect = cw / float(ch) if ch > 0 else 0
        if 0.15 <= aspect <= 1.4 and 10 <= ch <= 50 and cw >= 3:
            char_crops.append((x, y, cw, ch, roi[y:y+ch, x:x+cw]))

    # Sort left-to-right, top-to-bottom
    char_crops.sort(key=lambda item: (item[1] // 15, item[0]))

    recognized = []
    for x, y, cw, ch, crop in char_crops:
        ch_str = recognize_character(crop)
        if ch_str:
            recognized.append(ch_str)

    print("Recognized Characters:", "".join(recognized))


if __name__ == "__main__":
    test_ocr_on_rickshaw()
