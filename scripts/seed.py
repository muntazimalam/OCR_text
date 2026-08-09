import os
import sys
import shutil
import uuid

# Ensure repository root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal, Base, engine
from app.models.image import Image, ImageStatus
from app.services.image_service import ImageService
from app.services.storage_service import StorageService
from app.utils.file_utils import calculate_sha256
from app.workers.tasks import process_image
from scripts.generate_samples import create_sample_images, SAMPLES_DIR


def seed_database():
    print("Creating database tables if not present...")
    Base.metadata.create_all(bind=engine)
    create_sample_images()

    sample_files = [
        ("clean_plate.jpg", "image/jpeg"),
        ("blurry_plate.jpg", "image/jpeg"),
        ("dark_vehicle.jpg", "image/jpeg"),
        ("screenshot_sample.png", "image/png"),
    ]

    db = SessionLocal()
    try:
        for filename, content_type in sample_files:
            source_path = os.path.join(SAMPLES_DIR, filename)
            if not os.path.exists(source_path):
                continue

            with open(source_path, "rb") as f:
                file_bytes = f.read()

            sha256_hash = calculate_sha256(file_bytes)
            image_id = uuid.uuid4()
            stored_filename, file_path = StorageService.save_image(file_bytes, filename, image_id)

            img = ImageService.create_image(
                db=db,
                image_id=image_id,
                original_filename=filename,
                stored_filename=stored_filename,
                file_path=file_path,
                content_type=content_type,
                file_size=len(file_bytes),
                width=640 if "png" not in filename else 1080,
                height=480 if "png" not in filename else 2340,
                sha256_hash=sha256_hash,
            )

            print(f"Processing seeded image {filename} (ID: {image_id})...")
            process_image.run(str(image_id))

        print("Database successfully seeded with processed sample images.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
