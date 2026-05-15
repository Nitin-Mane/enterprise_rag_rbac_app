# Enterprise RAG RBAC App

Secure, context-aware RAG application for heterogeneous enterprise data with strict role-based access control.

## What Is Included

- Django REST API with SQLite metadata storage
- React + Vite frontend console
- Synthetic enterprise corpus: PDF, CSV, JSON, TXT, and SQLite data
- RBAC user/source policies with department, role, and clearance checks
- Hybrid retrieval using TF-IDF semantic scoring plus lexical overlap and query routing
- Grounded answers with citations, confidence, route trace, and blocked-source explanations
- Offline Hugging Face model loader from `models/qwen2.5-0.5b-instruct`
- Extractive fallback when the local model is not downloaded yet
- Custom file upload from the dashboard with per-source RBAC policy
- OCR-aware ingestion for images and scanned PDF pages when Tesseract is available
- Explainability indicators for routing, access filtering, candidate chunks, scores, parsers, and OCR usage

## Run Locally

Use the Anaconda `project` environment.

```powershell
conda activate project
python manage.py migrate
python manage.py seed_enterprise
python manage.py runserver 127.0.0.1:8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Offline Model

The app is wired for Qwen2.5 0.5B Instruct because it is practical for a local laptop while still being instruction-tuned. Download it into the project with:

```powershell
conda activate project
python scripts/download_model.py
```

The backend loads only from `models/qwen2.5-0.5b-instruct` with `local_files_only=True`. If the folder is absent, the API stays usable through an extractive fallback so the application does not crash during demos.

## Demo Users

- `aisha`: Security Analyst, clearance 3
- `marco`: Finance Manager, clearance 3
- `elen`: Ops Lead, clearance 2
- `nora`: Compliance Officer, clearance 4
- `devon`: Platform Engineer, clearance 2
- `sam`: HR Partner, clearance 1

## Good Test Questions

- "What happened in the April security incident and what actions were recommended?"
- "Which services are at SLA risk and what evidence supports that?"
- "Which vendors have high Q1 spend risk?"
- "What SOX evidence is pending?"
- "What platform architecture risk should engineering fix?"

Try the same question as different users to verify that restricted sources are not retrieved or exposed.

## Custom Sources And OCR

Use the dashboard's "Add custom source" panel to upload:

- PDF
- CSV
- JSON
- TXT/MD
- SQLite DB
- PNG/JPG/TIFF/BMP/WebP images

Each upload is stored under `enterprise_data/uploads/`, indexed immediately, and protected by the departments, roles, clearance, and sensitivity values entered in the form.

OCR uses `pytesseract` plus the native `tesseract` executable. The API health endpoint reports whether OCR is currently available:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health/
```

If OCR is unavailable, normal text PDFs, CSV, JSON, TXT, and SQLite files still ingest correctly. Image-only files and scanned PDF pages need a working Tesseract install in the active Anaconda environment or system PATH.
