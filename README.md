# 🚗 Intelligent Media Processing Pipeline & Web Dashboard

Backend API & interactive Web Application for vehicle image quality analysis, universal license plate recognition (Cars, Bikes, Trucks, International), automated tampering detection, and duplicate identification.

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
  - **Task Queue Resilience**: Automatically dispatches tasks to Celery/Redis if online, or executes processing in-process synchronously if Celery/Redis is unconfigured.
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
                 │ create job
                 ▼
       ┌───────────────────┐
       │   Celery Queue /  │
       │ Sync In-Process   │
       └─────────┬─────────┘
                 │
                 ▼
       ┌────────────────────────────────────────────────────────┐
       │                 Image Processing Pipeline              │
       ├────────────────────────────────────────────────────────┤
       │ 1. Clarity / Blur Detection (Laplacian Variance)       │
       │ 2. Brightness & Exposure Analysis                      │
       │ 3. Exact (SHA-256) & Perceptual (pHash) Duplicates     │
       │ 4. OCR Scene Text Extraction (EasyOCR)                 │
       │ 5. Universal License Plate Recognition (Cars/Bikes/EU)│
       │ 6. Metadata EXIF & Screenshot Detection                │
       │ 7. Automated Software Tampering Analysis               │
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
* **Task Queue & Broker:** Celery 5.3+, Redis 7 (with synchronous fallback)
* **Computer Vision & ML:** OpenCV (`opencv-python-headless`), EasyOCR, ImageHash, Pillow
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
│   │   └── tampering.py
│   ├── static/            # Web Dashboard UI Assets
│   │   ├── index.html     # Glassmorphism Dashboard Layout
│   │   ├── css/style.css  # Dark mode CSS design system
│   │   └── js/app.js      # Interactive upload, gallery & modal logic
│   └── workers/           # Celery application & asynchronous worker tasks
│
├── uploads/               # Storage directory hierarchy (/YYYY/MM/UUID.ext)
│   └── samples/           # Pre-generated vehicle test sample images
├── tests/                 # Unit & E2E integration test suite (16 tests)
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
| `POST` | `/api/v1/images` | Upload image for analysis |
| `GET` | `/api/v1/images` | List all processed images with pagination (`skip`, `limit`) & status filter |
| `GET` | `/api/v1/images/{id}/status` | Check processing status (`pending`, `completed`, `failed`) |
| `GET` | `/api/v1/images/{id}/results` | Detailed quality score, heuristics & detected issues |
| `GET` | `/api/v1/images/{id}/file` | Serve raw uploaded image file |
| `DELETE` | `/api/v1/images/{id}` | Delete image database record and stored file |

---

## 🔍 Image Analysis Heuristics

1. **Clarity / Blur Detection**: Laplacian variance metric (`score < 100` flagged as blurry).
2. **Brightness & Lighting**: Mean intensity categorization (`very_dark`, `low_light`, `acceptable`, `bright`, `overexposed`).
3. **Duplicate Detection**: SHA-256 exact hash matching + Perceptual hashing (`pHash` hamming distance threshold `≤ 6`).
4. **OCR Text Extraction**: EasyOCR text detection & bounding box confidence scoring.
5. **Universal License Plate Recognition**: Multi-regex format matching + 2-line motorcycle plate token joining + vehicle brand noise exclusion.
6. **Metadata & Screenshot Detection**: EXIF camera attribute extraction + screenshot probability calculation.
7. **Tampering Detection**: EXIF software signature inspection for photo manipulation tools (Photoshop, Canva, GIMP, etc.).

---

## 🚀 Quickstart & Running the App

### Step 1: Activate Virtual Environment
```powershell
.\venv\Scripts\activate
```

### Step 2: Seed Demo Sample Data *(Optional)*
Generates synthetic test vehicle images (`Clean Plate`, `Blurry Image`, `Low Light`, `Screenshot`) and seeds the database:
```powershell
$env:PYTHONPATH="."; python scripts/seed.py
```

### Step 3: Run the Web Application
```powershell
$env:PYTHONPATH="."; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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

Run the complete unit & integration test suite (16 tests):

```powershell
$env:PYTHONPATH="."; python -m pytest
```

---

## 🤖 AI Usage Disclosure

AI tools were utilized during development for:
- Architecture design & design pattern planning
- FastAPI & SQLAlchemy boilerplate generation
- OpenCV & EasyOCR heuristic calibration
- Unit test suite expansion
- Interactive Web Dashboard CSS glassmorphism styling
localhost:8000/docs)

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
