# 🚗 Intelligent Media Processing Pipeline & Web Dashboard

Backend API & interactive Web Application for vehicle image quality analysis, universal license plate recognition (Cars, Bikes, Trucks, International), automated tampering detection, photo-of-photo heuristics, and duplicate identification.

---

## ✨ Features & Capabilities

- 🎨 **Modern Interactive Web Dashboard**: Dark glassmorphism UI with drag-and-drop file upload, live 1-click test sample buttons (`Clean Plate`, `Blurry Image`, `Low Light`, `Screenshot`), filterable media gallery, and interactive inspection report modal.
- 🏍️ **Universal License Plate Analyzer**:
  - **Multi-Vehicle Support**: Handles cars, motorcycles, scooters, trucks, and commercial vehicles.
  - **Multi-Line Bike Plate Joining**: Automatically merges stacked 2-line motorcycle plates (e.g. `KA05` + `EX5678` ➔ `KA05EX5678`).
  - **Multi-Country Formats**: Indian Standard (`KA01AB1234`), Indian BH Series (`22BH1234AB`), US/North America (`7ABC123`), European/UK (`AB12 CDE`), and Universal Alphanumeric patterns.
  - **Vehicle Brand Noise Filter**: Excludes vehicle logos & body text (`HONDA`, `TOYOTA`, `YAMAHA`, `ROYAL ENFIELD`, `HERO`, `TVS`, `KTM`, etc.).
- 🛡️ **Zero-Dependency Resilient Architecture**:
  - **Database Portability & Fallback**: Automatically connects to PostgreSQL if available, or seamlessly falls back to local SQLite (`media_pipeline.db`).
  - **Task Queue Resilience**: Automatically dispatches tasks to Celery/Redis if online, or executes processing asynchronously using FastAPI `BackgroundTasks` if Celery/Redis is offline or unconfigured.
- 🌐 **Extended REST API**: Complete CRUD endpoints with pagination, status filtering, raw image file serving, and health checks.

---

## 📌 Architecture Overview

```text
                                CLIENT / WEB DASHBOARD
                                         │
                        POST /api/v1/images (Drag & Drop / API)
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │   FastAPI    │
                                  │   API Server │
                                  └──────┬───────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
       ┌───────────────────┐                           ┌───────────────────┐
       │   Database Layer  │                           │   File Storage    │
       │ PostgreSQL /      │                           │  /uploads hierarchy│
       │ SQLite Fallback   │                           └───────────────────┘
       └─────────┬─────────┘
                 │
                 │ create job (returns HTTP 201 immediately with status: pending)
                 ▼
       ┌─────────────────────────┐
       │   Celery Queue /        │
       │ FastAPI BackgroundTasks │
       └─────────┬───────────────┘
                 │
                 ▼
       ┌────────────────────────────────────────────────────────┐
       │                 Image Processing Pipeline              │
       ├────────────────────────────────────────────────────────┤
       │ 1. Clarity / Blur Detection (Laplacian Variance)       │
       │ 2. Brightness & Exposure Analysis                      │
       │ 3. Exact (SHA-256) & Perceptual (pHash) Duplicates     │
        │ 4. OCR Scene Text Extraction (RapidOCR)                    │
       │ 5. Universal License Plate Recognition (Cars/Bikes/EU)│
       │ 6. Metadata EXIF & Screenshot Detection                │
       │ 7. Automated Software Tampering Analysis               │
       │ 8. Photo-of-Photo / 2D FFT Moiré Pattern Analysis      │
       └─────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
                       ┌───────────────────┐
                       │  Analysis Results │
                       └─────────┬─────────┘
                                 │
                                 ▼
                     GET /api/v1/images/{id}/results
```

---

## 🛠 Tech Stack

* **Framework:** FastAPI, Uvicorn, Starlette
* **Frontend Web Dashboard:** HTML5, Vanilla CSS3 (Glassmorphism), JavaScript (Fetch API)
* **Database:** SQLAlchemy 2.0 (Generic Uuid & Portable Enums), PostgreSQL / SQLite, Alembic
* **Task Queue & Broker:** Celery 5.3+, Redis 7 (with FastAPI `BackgroundTasks` fallback)
* **Computer Vision & ML:** OpenCV, RapidOCR (ONNX PP-OCRv4), Tesseract, ImageHash, Pillow, NumPy
* **Logging & Validation:** Structlog, Pydantic V2, Pydantic Settings
* **Testing:** Pytest, HTTPX, Starlette TestClient

---

## 📁 Project Structure

```text
media-processing-pipeline/
│
├── app/
│   ├── main.py            # FastAPI entry point & Web Dashboard router
│   ├── core/              # Config, Database (Postgres/SQLite fallback), Logging
│   ├── api/               # REST API Endpoints (v1)
│   │   └── v1/
│   │       ├── health.py  # Health check (DB dialect & Task mode)
│   │       └── images.py  # Upload, List, Results, File Serving & Delete
│   ├── models/            # SQLAlchemy DB models (Image, AnalysisResult)
│   ├── schemas/           # Pydantic V2 request & response schemas
│   ├── services/          # Storage, Image CRUD, Analysis orchestration
│   ├── analyzers/         # CV & ML Image Analyzers
│   │   ├── blur.py
│   │   ├── brightness.py
│   │   ├── duplicate.py
│   │   ├── ocr.py
│   │   ├── number_plate.py # Universal multi-vehicle & multi-country plate recognition
│   │   ├── metadata.py
│   │   ├── tampering.py
│   │   └── photo_of_photo.py # 2D FFT Moiré pattern & screen capture heuristics
│   ├── static/            # Web Dashboard UI Assets
│   │   ├── index.html     # Glassmorphism Dashboard Layout
│   │   ├── css/style.css  # Dark mode CSS design system
│   │   └── js/app.js      # Interactive upload, gallery & modal logic
│   └── workers/           # Celery application & asynchronous worker tasks
│
├── uploads/               # Storage directory hierarchy (/YYYY/MM/UUID.ext)
│   └── samples/           # Pre-generated vehicle test sample images
├── tests/                 # Unit & E2E integration test suite (17 tests)
├── scripts/               # Sample image generator & database seeder
├── .env                   # Environment variables
├── Dockerfile             # Multi-stage container definition
├── docker-compose.yml     # Full-stack orchestrator
├── pytest.ini             # Pytest configuration
├── requirements.txt       # Dependencies
└── README.md              # Documentation
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves Interactive Web Dashboard UI (`index.html`) |
| `GET` | `/api/info` | Application metadata & version information |
| `GET` | `/api/v1/health` | Health check (reports DB dialect & task queue mode) |
| `POST` | `/api/v1/images` | Upload image for analysis (returns immediately with status `pending`) |
| `GET` | `/api/v1/images` | List all processed images with pagination (`skip`, `limit`) & status filter |
| `GET` | `/api/v1/images/{id}/status` | Check processing status (`pending`, `processing`, `completed`, `failed`) |
| `GET` | `/api/v1/images/{id}/results` | Detailed quality score, heuristics & detected issues |
| `GET` | `/api/v1/images/{id}/file` | Serve raw uploaded image file |
| `DELETE` | `/api/v1/images/{id}` | Delete image database record and stored file |

---

## 🔍 Image Analysis Heuristics

1. **Clarity / Blur Detection**: Laplacian variance metric (`score < 100` flagged as blurry).
2. **Brightness & Lighting**: Mean intensity categorization (`very_dark`, `low_light`, `acceptable`, `bright`, `overexposed`).
3. **Duplicate Detection**: SHA-256 exact hash matching + Perceptual hashing (`pHash` hamming distance threshold `≤ 6`).
4. **OCR Text Extraction**: RapidOCR (PP-OCRv4 ONNX) text detection & bounding box confidence scoring, with Tesseract fallback.
5. **Universal License Plate Recognition**: Multi-regex format matching + 2-line motorcycle plate token joining + vehicle brand noise exclusion.
6. **Metadata & Screenshot Detection**: EXIF camera attribute extraction + screenshot probability calculation.
7. **Tampering Detection**: EXIF software signature inspection for photo manipulation tools (Photoshop, Canva, GIMP, etc.).
8. **Photo-of-Photo / Screen Capture**: 2D Fast Fourier Transform (FFT) high-frequency Moiré pattern spectrum analysis combined with EXIF camera indicators.

---

## 💻 Sample API Requests & Responses

### 1. Upload Image (`POST /api/v1/images`)

**Request:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/images" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@clean_plate.jpg;type=image/jpeg"
```

**Response (`HTTP 201 Created` - Immediate):**
```json
{
  "id": "7b90ae82-d25f-41c6-80bd-d0ab2385184e",
  "status": "pending",
  "created_at": "2026-08-09T15:04:40.123456",
  "error_message": null
}
```

---

### 2. Check Processing Status (`GET /api/v1/images/{id}/status`)

**Request:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/images/7b90ae82-d25f-41c6-80bd-d0ab2385184e/status"
```

**Response (`HTTP 200 OK`):**
```json
{
  "id": "7b90ae82-d25f-41c6-80bd-d0ab2385184e",
  "status": "completed",
  "created_at": "2026-08-09T15:04:40.123456",
  "error_message": null
}
```

---

### 3. Fetch Analysis Results (`GET /api/v1/images/{id}/results`)

**Request:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/images/7b90ae82-d25f-41c6-80bd-d0ab2385184e/results"
```

**Response (`HTTP 200 OK`):**
```json
{
  "image_id": "7b90ae82-d25f-41c6-80bd-d0ab2385184e",
  "status": "completed",
  "overall_score": 1.0,
  "issues": [],
  "error_message": null,
  "created_at": "2026-08-09T15:04:40.123456",
  "analysis": {
    "blur": {
      "score": 184.52,
      "is_blurry": false
    },
    "brightness": {
      "score": 142.18,
      "status": "acceptable"
    },
    "duplicate": {
      "is_duplicate": false,
      "duplicate_of": null
    },
    "ocr": {
      "text": "KA01AB1234",
      "confidence": 0.98
    },
    "number_plate": {
      "detected": true,
      "valid": true,
      "confidence": 0.95
    },
    "metadata": {
      "has_exif": false,
      "camera_make": null,
      "camera_model": null,
      "software": null,
      "screenshot_probability": 0.4
    },
    "tampering": {
      "suspicious_editing": false,
      "confidence": 0.0
    }
  }
}
```

---

## 🚀 Quickstart & Running the App

### Step 1: Activate Virtual Environment
```powershell
.\venv\Scripts\activate
```

### Step 2: Seed Demo Sample Data
Generates synthetic test vehicle images (`Clean Plate`, `Blurry Image`, `Low Light`, `Screenshot`) and seeds the database:
```powershell
python scripts/seed.py
```

### Step 3: Run the Web Application
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open in your browser:
- 🎨 **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- 📘 **Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### Docker Compose (Full Stack Option)

To run with PostgreSQL, Redis, and Celery worker services:
```bash
docker compose up --build
```

---

## 🧪 Running Automated Tests

Run the complete unit & integration test suite (17 tests):

```powershell
python -m pytest
```

---

## 📌 Assumptions Made

1. **Upload Constraints**: Max file size is set to 15 MB. Supported image MIME types are `image/jpeg`, `image/png`, `image/webp`.
2. **License Plate Verification**: Format validation uses structural pattern matching (regex + token joining) rather than querying live government DMV databases.
3. **Queue Fallback**: In environments without active Redis/Celery infrastructure, the API automatically falls back to FastAPI `BackgroundTasks` to guarantee non-blocking asynchronous execution.

---

## 🤖 AI Usage Disclosure (Mandatory)

### Where & How AI Tools Were Used
- **Architecture & Schema Design**: Used Claude & ChatGPT for designing the dual-fallback database model (SQLAlchemy 2.0 with PostgreSQL/SQLite compatibility) and task queue abstraction.
- **Computer Vision & Heuristics Calibration**: Used AI to explore OpenCV frequency domain formulas for Moiré grid detection and regular expressions for international license plates.
- **Boilerplate & Test Generation**: Generated initial FastAPI Pydantic V2 schemas, CRUD service wrappers, and extended `pytest` test cases.
- **Web UI Styling**: Assisted with CSS glassmorphism design tokens and HTML layout structure.

### Where AI Output Was Wrong or Inadequate
1. **Blocking Synchronous Image Decoding**: AI originally generated image upload endpoints that called OpenCV image decoding (`cv2.imdecode`) synchronously inside the HTTP handler thread, which would block API throughput during large batch uploads. Fixed by delegating analysis strictly to background queues.
2. **Motorcycle License Plate Recognition Failure**: Initial AI-suggested EasyOCR regex patterns failed on 2-line stacked motorcycle plates (e.g. `KA05` on top line, `EX5678` on bottom line). Fixed by writing custom candidate token-merging logic to join adjacent OCR tokens (`KA05` + `EX5678` ➔ `KA05EX5678`).
3. **Vehicle Brand Text False Positives**: OCR text extraction initially flagged brand emblems on vehicles (`HONDA`, `TOYOTA`, `YAMAHA`, `ROYAL ENFIELD`) as valid license plates. Fixed by introducing an explicit `VEHICLE_BRAND_KEYWORDS` filter.
4. **Celery Fallback Handling**: AI initially generated a Celery fallback that ran tasks synchronously in the API thread on failure. Updated to use FastAPI `BackgroundTasks` to preserve non-blocking immediate responses (`HTTP 201 Created`).

### How AI-Generated Code Was Validated
- **Automated Testing**: 100% of generated service logic and endpoints were covered by `pytest` integration tests (17 passing tests).
- **Synthetic Sample Verification**: Created `scripts/generate_samples.py` to generate controlled test images (clean plates, heavy Gaussian blur, low lighting, screenshots) and verified analyzer outputs against expected ground truth.
- **Manual UI Verification**: Tested interactive uploads and inspection reports across edge-case images via the Web Dashboard.

---

## ⚖️ Trade-offs & Limitations

### 1. What Was Intentionally Simplified
- **Local File System Storage**: Saved uploaded files in structured local directories (`/uploads/YYYY/MM/UUID.ext`) to ensure zero-dependency local reproducibility without requiring AWS S3 credentials.
- **Heuristic Quality Scoring**: Used weighted classical computer vision heuristics (Laplacian variance, grayscale intensity, pHash distance) instead of hosting heavy deep neural network quality assessment models.

### 2. What Would Be Improved With More Time
- **Dedicated Object Detection Models**: Replace heuristic OCR text extraction with YOLOv8/v10 fine-tuned on vehicle license plates for tighter bounding box localization before OCR.
- **Deep Moiré & Deepfake Neural Networks**: Implement specialized deep learning models for detecting AI-generated vehicle tampering and screen re-photography.
- **DMV / Vahan API Verification**: Add external API integrations (e.g. Parivahan / DMV APIs) to cross-reference extracted plate text against registered vehicle databases.

### 3. Scalability Concerns
- **Worker Concurrency & GPU Acceleration**: CPU-bound OCR and OpenCV processing can become a bottleneck at high throughput. Production deployments should utilize GPU-accelerated Celery workers with auto-scaling worker pools.
- **Distributed Shared Storage**: Local file storage does not scale horizontally across multiple web nodes. A production setup requires AWS S3 or Google Cloud Storage with CDN caching.

### 4. Failure Handling Concerns
- **Poison Pill Tasks & Dead-Letter Queues**: Unhandled image corruptions could crash workers. Added try-catch blocks per analyzer, but a production pipeline should introduce a Celery Dead-Letter Queue (DLQ) to isolate failing tasks after 3 retries.
