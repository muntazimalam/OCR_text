import os
import sys
import cv2
import numpy as np
from PIL import Image as PILImage

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

SAMPLES_DIR = os.path.join(REPO_ROOT, "uploads", "samples")


def create_sample_images():
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    # 1. Clean Vehicle Image with Plate KA01AB1234
    clean_img = np.zeros((480, 640, 3), dtype=np.uint8)
    clean_img[:] = (180, 180, 180)  # Neutral grey background
    # Draw car body
    cv2.rectangle(clean_img, (100, 200), (540, 380), (50, 50, 200), -1)
    # Draw license plate box
    cv2.rectangle(clean_img, (220, 300), (420, 350), (255, 255, 255), -1)
    cv2.rectangle(clean_img, (220, 300), (420, 350), (0, 0, 0), 2)
    # Draw plate text KA01AB1234
    cv2.putText(clean_img, "KA01AB1234", (230, 338), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    clean_path = os.path.join(SAMPLES_DIR, "clean_plate.jpg")
    cv2.imwrite(clean_path, clean_img)

    # 2. Blurry Image
    blurry_img = cv2.GaussianBlur(clean_img, (31, 31), 15)
    blurry_path = os.path.join(SAMPLES_DIR, "blurry_plate.jpg")
    cv2.imwrite(blurry_path, blurry_img)

    # 3. Dark Image
    dark_img = (clean_img * 0.15).astype(np.uint8)
    dark_path = os.path.join(SAMPLES_DIR, "dark_vehicle.jpg")
    cv2.imwrite(dark_path, dark_img)

    # 4. Screenshot Image (1080x2340 resolution)
    screenshot = PILImage.new("RGB", (1080, 2340), color=(240, 240, 240))
    screenshot_path = os.path.join(SAMPLES_DIR, "screenshot_sample.png")
    screenshot.save(screenshot_path)

    print(f"Sample images created successfully in {SAMPLES_DIR}")


if __name__ == "__main__":
    create_sample_images()
