import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from app.analyzers.ocr import _locate_yellow_plate_rois, _crop_plate_patch, _run_easyocr

INPUT_DIR = r"C:\Users\munta\Downloads\regingermediagroupvirtualpreplacementtalk8augu"
import app.analyzers.ocr as ocr_mod

reader = ocr_mod._get_easyocr_reader()


def variants(patch):
    out = {"color": patch}
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    out["gray"] = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    out["clahe"] = cv2.cvtColor(cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray), cv2.COLOR_GRAY2BGR)
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    out["thresh"] = cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)
    edge = cv2.Canny(gray, 60, 180)
    out["edges"] = cv2.cvtColor(edge, cv2.COLOR_GRAY2BGR)
    return out


def main():
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "*")))
    for path in files:
        fname = os.path.basename(path)
        img = cv2.imread(path)
        print(f"\n===== {fname} ({img.shape[1]}x{img.shape[0]}) =====")
        for idx, roi in enumerate(_locate_yellow_plate_rois(img, top_n=5)):
            x, y, w, h = roi
            patch = _crop_plate_patch(img, roi)
            if patch is None:
                print(f"  ROI{idx} {w}x{h} at ({x},{y}) -> patch too small")
                continue
            print(f"  ROI{idx} {w}x{h} at ({x},{y}) dens-check")
            for name, var_img in variants(patch).items():
                res = _run_easyocr(reader, var_img, min_chars=2)
                txt = (res or {}).get("text", "")
                print(f"    [{name:7}] {txt[:80]}")
                for det in (res or {}).get("detections", [])[:6]:
                    print(f"              - {det['text']}  ({round(det['confidence'],2)})")
        sys.stdout.flush()


if __name__ == "__main__":
    main()