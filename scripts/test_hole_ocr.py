import cv2
import numpy as np
import os
import re

HOLE_MAP = {
    '8': 2, 'B': 2,
    '0': 1, '4': 1, '6': 1, '9': 1, 'A': 1, 'D': 1, 'O': 1, 'P': 1, 'Q': 1, 'R': 1,
    '1': 0, '2': 0, '3': 0, '5': 0, '7': 0, 'C': 0, 'E': 0, 'F': 0, 'G': 0, 'H': 0,
    'I': 0, 'J': 0, 'K': 0, 'L': 0, 'M': 0, 'N': 0, 'S': 0, 'T': 0, 'U': 0, 'V': 0,
    'W': 0, 'X': 0, 'Y': 0, 'Z': 0
}


def count_holes(char_crop: np.ndarray) -> int:
    if char_crop is None or char_crop.size == 0:
        return 0
    # Ensure binary (0 or 255)
    _, thresh = cv2.threshold(char_crop, 127, 255, cv2.THRESH_BINARY)
    # Pad borders to ensure outer background contour is complete
    padded = cv2.copyMakeBorder(thresh, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
    cnts, hierarchy = cv2.findContours(padded, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return 0
    # Count internal hole contours (child contours with parent != -1)
    holes = 0
    for i, h in enumerate(hierarchy[0]):
        # h format: [Next, Previous, First_Child, Parent]
        if h[3] != -1:  # Has a parent contour
            holes += 1
    return max(0, holes - 1)  # Subtract outer character shape contour


def test_hole_counting():
    # Test rendering '8', 'A', 'K', '0'
    for char in ['8', 'A', 'K', '0', 'B', '1']:
        canvas = np.zeros((40, 30), dtype=np.uint8)
        cv2.putText(canvas, char, (3, 32), cv2.FONT_HERSHEY_DUPLEX, 1.0, 255, 2)
        h = count_holes(canvas)
        print(f"Char '{char}': expected hole count {HOLE_MAP[char]}, got {h}")


if __name__ == "__main__":
    test_hole_counting()
