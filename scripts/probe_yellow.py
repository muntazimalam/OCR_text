import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

import app.analyzers.ocr as ocr_mod

reader = ocr_mod._get_easyocr_reader()
INPUT_DIR = r"C:\Users\munta\Downloads\regingermediagroupvirtualpreplacementtalk8augu"


def all_yellow_regions(img):
    mask = ocr_mod._yellow_mask(img)
    h, w = img.shape[:2]
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    img_area = h * w
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        aspect = bw / float(bh) if bh > 0 else 0
        frac = area / img_area
        out.append((x, y, bw, bh, aspect, frac))
    out.sort(key=lambda r: r[4], reverse=True)
    return out


def main():
    for path in sorted(glob.glob(os.path.join(INPUT_DIR, "*"))):
        fname = os.path.basename(path)
        img = cv2.imread(path)
        print(f"\n===== {fname} ({img.shape[1]}x{img.shape[0]}) =====")
        regions = all_yellow_regions(img)
        n_shown = 0
        for (x, y, w, h, aspect, frac) in regions:
            if h < 12 or w < 30 or frac < 0.0003:
                continue
            patch = ocr_mod._crop_plate_patch(img, (x, y, w, h))
            if patch is None:
                continue
            res = ocr_mod._run_easyocr(reader, patch, min_chars=2)
            text = (res or {}).get("text", "")
            plate_like = ocr_mod._is_plate_like(text or "")
            n_shown += 1
            print(f"  [{aspect:.1f}ar frac={frac:.4f} {w}x{h}@{x},{y}] {'PLATE!' if plate_like else '      '} {text[:70]}")
            if n_shown >= 14:
                break
        sys.stdout.flush()


if __name__ == "__main__":
    main()