# 🚗 Intelligent Media Processing Pipeline

Backend API for asynchronous vehicle image processing, media quality analysis, license plate format validation, and automated tampering detection.

---

## 📌 Architecture Overview

```text
                         CLIENT
                           │
                           │ POST /api/v1/images
                           ▼
                    ┌──────────────┐
                    │   FastAPI    │
                    │   API Server │
                    └──────┬───────┘
                           │
             ┌─────────────┴──────────────┐
             │                            │
             ▼                            ▼
      ┌─────────────┐              ┌─────────────┐
      │ PostgreSQL  │              │ File Storage │
      │             │              │   /uploads   │
      └──────┬──────┘              └─────────────┘
             │
             │ create job
             ▼
        ┌───────────┐
        │   Redis   │
        │   Queue   │
        └─────┬─────┘
              │
              ▼
        ┌───────────┐
        │  Celery   │
        │  Worker   │
        └─────┬─────┘
              │
              ▼
      ┌─────────────────┐
      │ Image Pipeline  │
      ├─────────────────┤
      │ Blur            │
      │ Brightness      │
      │ Duplicate       │
      │ OCR             │
      │ Plate validation│
      │ EXIF            │
      │ Tampering       │
      └────────┬────────┘
               │
               ▼
        ┌─────────────┐
        │ PostgreSQL  │
        │ Results     │
        └──────┬──────┘
               │
               ▼
         Results API
```

---

## 🛠 Tech Stack

* **Framework:** FastAPI, Uvicorn
* **Database:** PostgreSQL 15, SQLAlchemy 2.0, Alembic
* **Task Queue & Broker:** Celery 5.3+, Redis 7
* **Computer Vision & ML:** OpenCV (`opencv-python-headless`), EasyOCR, ImageHash, Pillow
* **Logging & Validation:** Structlog, Pydantic V2, Pydantic Settings
* **Testing:** Pytest, HTTPX, Starlette TestClient
* **Containerization:** Docker, Docker Compose

---

## 📁 Project Structure

```text
media-processing-pipeline/
│
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI application entry point
│   ├── core/              # Global configs, database, and logging
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── api/               # REST API Endpoints
│   │   └── v1/
│   │       ├── health.py  # GET /api/v1/health
│   │       └── images.py  # POST /api/v1/images, GET status & results
│   ├── models/            # SQLAlchemy DB models (Image, AnalysisResult)
│   ├── schemas/           # Pydantic request/response schemas
│   ├── services/          # Business logic, storage, and analysis orchestration
│   ├── analyzers/         # CV & ML Image Analyzers
│   │   ├── base.py
│   │   ├── blur.py
│   │   ├── brightness.py
│   │   ├── duplicate.py
│   │   ├── ocr.py
│   │   ├── number_plate.py
│   │   ├── metadata.py
│   │   └── tampering.py
│   ├── workers/           # Celery application & asynchronous tasks
│   │   ├── celery_app.py
│   │   └── tasks.py
│   └── utils/             # File hashing, image decoding & validators
│
├── uploads/               # Storage directory hierarchy (/YYYY/MM/UUID.ext)
├── tests/                 # Pytest suite
├── scripts/               # Seed data script
├── .env                   # Environment variables
├── .env.example           # Example environment template
├── Dockerfile             # Multi-stage production container
├── docker-compose.yml     # Multi-service setup (api, worker, postgres, redis)
├── alembic.ini            # Database migration configuration
├── pytest.ini             # Pytest configuration
├── requirements.txt       # Python dependencies
└── README.md              # Documentation
```

---

## 🌐 API Endpoints

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | Root API information & docs link |
| `GET` | `/api/v1/health` | Health check endpoint |
| `POST` | `/api/v1/images` | Upload image for asynchronous processing |
| `GET` | `/api/v1/images/{id}/status` | Check image processing status |
| `GET` | `/api/v1/images/{id}/results` | Fetch complete analysis results & issues |

---

## 🔍 Image Analysis Methods & Heuristics

1. **Blur Detection (`blur.py`)**: Computes Laplacian variance on grayscale image. Variance `< 100` indicates a blurry image.
2. **Brightness Analysis (`brightness.py`)**: Computes mean intensity. Categorizes image into `very_dark` (<40), `low_light` (40-80), `acceptable` (80-180), `bright` (180-220), and `overexposed` (>220).
3. **Duplicate Detection (`duplicate.py`)**: Combines SHA-256 hash matching (exact duplicates) with perceptual hashing (`phash`) via ImageHash for near-duplicate identification.
4. **Text Extraction (`ocr.py`)**: Uses EasyOCR engine to extract scene text and bounding box confidence scores.
5. **Number Plate Format Validation (`number_plate.py`)**: Normalizes OCR text and applies regex pattern matching (`^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}$`). *Note: Format validation only.*
6. **Metadata & Screenshot Detection (`metadata.py`)**: Extracts EXIF camera/software attributes and computes screenshot probability based on missing EXIF and common resolution dimensions.
7. **Tampering Detection (`tampering.py`)**: Scans EXIF software metadata for image editing tools (Photoshop, GIMP, Canva, etc.) and flags suspicious editing.

---

## 🚀 Quickstart & Setup

### Option 1 — Local Development with Virtual Environment

1. Activate virtual environment:
   ```bash
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure PostgreSQL and Redis are running locally, then run migrations:
   ```bash
   alembic upgrade head
   ```

4. Start FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Start Celery worker in a separate terminal:
   ```bash
   celery -A app.workers.celery_app worker --loglevel=info
   ```

### Option 2 — Docker Compose (Recommended)

Run all services (`api`, `worker`, `postgres`, `redis`) with a single command:

```bash
docker compose up --build
```

Access Swagger UI documentation at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Running Tests

Execute pytest suite:
```bash
pytest
```

---

## 🤖 AI Usage Disclosure

AI tools were used during development for:
* Architecture brainstorming and plan structuring
* FastAPI boilerplate generation
* OpenCV and EasyOCR implementation patterns
* Test case generation
* Documentation assistance

AI-generated code was reviewed, refined, and tested locally. Image analysis thresholds, error recovery, and failure resilience were manually calibrated.

---

## ⚖️ Trade-offs & Limitations

* **Local Storage:** Chosen for local reproducibility. In production, `storage_service.py` should be backed by AWS S3 or Google Cloud Storage.
* **Format Validation vs Verification:** License plate checks validate structural regex format rather than querying external DMV databases.
* **Classical CV Heuristics:** Blur and brightness thresholds use classical computer vision heuristics for speed and low footprint rather than heavy neural networks.
