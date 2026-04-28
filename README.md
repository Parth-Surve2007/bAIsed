# bAIsed

AI fairness workbench for dataset bias auditing, disparity diagnostics, simulation, and actionable remediation guidance.

## What This Project Does

bAIsed is a full-stack Flask + static frontend application that helps teams:

- run fairness checks from simple percentage inputs or real datasets (`.csv`, `.xlsx`)
- compute core parity metrics (DIR, SPD, EOD, AOD) and a normalized bias score
- detect root-cause feature impact and subgroup hotspots
- generate counterfactual repair suggestions and what-if simulation outputs
- produce AI-written analysis reports using **Google Gemini**

## Core Features

- **Quick Analysis**: manual group A/B percentage input for instant fairness check
- **Deep Dive**: multi-panel dataset diagnostics (group stats, feature impact, hotspots, repairs)
- **Dataset Scan**: auto-detect likely protected/outcome/qualification columns
- **AI Analyzer**: Gemini-based report synthesis from dataset summary + deterministic metrics
- **What-If Simulator**: interactive parity/accuracy estimation under fairness constraints
- **Auth UI**: Firebase-based client auth flows (email/password + Google sign-in)

## Tech Stack

- **Backend**: Python, Flask
- **Data Processing**: Pandas, NumPy, OpenPyXL
- **Frontend**: HTML, TailwindCSS, vanilla JS
- **AI Service**: Google Gemini (Generative Language API)
- **Auth**: Firebase client SDK + scaffolded admin endpoints
- **Deployment**: Google App Engine config included (`app.yaml`)

## Project Structure

```text
bAIsed/
├─ backend/
│  ├─ app.py                # Flask app factory, routes for static pages, CORS, dotenv load
│  ├─ api.py                # Main API endpoints (analyze/upload/scan/simulate/ai-analyze/reset)
│  ├─ analysis.py           # Fairness engine, metric calculation, profiling, hotspot logic
│  ├─ simulator.py          # What-if simulation model and parity improvement estimates
│  ├─ preprocessor.py       # Dataset normalization, cleaning, type coercion, binary standardization
│  ├─ auth.py               # Firebase admin verification/profile endpoint scaffolding
│  ├─ fb_admin.py           # Firebase admin initialization
│  ├─ requirements.txt      # Python dependencies
│  ├─ .env                  # Local backend environment variables (not for git)
│  └─ temp_datasets/        # Temporary standardized uploads (session-like cache)
├─ frontend/
│  ├─ pages/
│  │  ├─ workbench.html     # Main fairness workbench UI
│  │  ├─ landing.html       # Home page
│  │  ├─ about.html         # About page and stack information
│  │  ├─ solutions.html
│  │  ├─ methodology.html
│  │  ├─ case_study.html
│  │  ├─ pricing.html
│  │  ├─ login.html
│  │  ├─ signup.html
│  │  ├─ dashboard.html
│  │  └─ 404.html
│  ├─ js/
│  │  ├─ workbench.js       # Frontend logic for forms, rendering, simulation interactions
│  │  ├─ site.js            # Global site interactions/navigation/theme utility logic
│  │  ├─ auth.js            # Client auth workflow and session persistence
│  │  └─ firebase-config.js # Firebase client config bootstrap
│  └─ css/
│     └─ custom.css
├─ run.py                   # App entrypoint (`from backend.app import app`)
├─ app.yaml                 # Google App Engine deployment config
├─ .env.example             # Template env vars
├─ test_data.csv            # Example dataset
└─ .gitignore
```

## How It Runs (Request Flow)

1. User opens `/workbench`.
2. Frontend (`workbench.js`) sends:
   - `/analyze` for simple input, or
   - `/scan` then `/upload` for dataset mode.
3. Backend (`analysis.py`) computes fairness outputs and returns structured JSON.
4. Deep Dive panels render metrics, hotspots, field analysis, feature ranking, repairs.
5. Simulator calls `/simulate` and updates predicted DIR/SPD/accuracy and parity improvement bar.
6. AI Analyzer calls `/ai-analyze`, which sends prompt context to Gemini and returns markdown report text.

## Fairness Metrics Implemented

- **DIR (Disparate Impact Ratio)**: `min(selection_rate) / max(selection_rate)`
- **SPD (Statistical Parity Difference)**: `max_rate - min_rate`
- **EOD (Equal Opportunity Difference)**: disparity inside qualified subset
- **AOD (Average Odds Difference)**: combined disparity signal
- **Bias Score (0-100)**: weighted aggregate of DIR gap + SPD + EOD + AOD

Severity thresholds:

- `HIGH`: DIR < 0.5
- `MODERATE`: 0.5 <= DIR < 0.8
- `LOW`: DIR >= 0.8

## API Overview

### Site/Utility

- `GET /api/health` - health check
- `GET /api/site-content/<page_name>` - static content payload
- `GET /api/search?query=...` - documentation topic search
- `POST /api/actions/resolve` - UI action routing helper
- `POST /api/demo-request` - records demo request in memory
- `GET /api/downloads/whitepaper` - returns markdown whitepaper

### Workbench

- `POST /analyze` - simple groupA/groupB fairness analysis
- `POST /scan` - upload file and infer schema/profile for dropdown auto-detection
- `POST /upload` - run full dataset fairness analysis
- `POST /simulate` - what-if simulator output
- `POST /ai-analyze` - Gemini report generation
- `POST /reset` - clears temporary uploaded datasets

### Auth (Scaffolded)

- `POST /api/auth/verify`
- `GET /api/auth/profile`
- `POST /api/auth/profile`

> Note: Firebase admin profile operations are scaffolded but intentionally not fully implemented yet.

## Local Setup

### 1) Prerequisites

- Python 3.11+ recommended
- pip

### 2) Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3) Configure environment variables

Create `backend/.env` (or export env vars) with at least:

```env
GEMINI_API_KEY=your_google_ai_key
GEMINI_MODEL=gemini-1.5-flash

FLASK_ENV=development
FLASK_SECRET_KEY=change-me

# Optional Firebase admin credentials
GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
```

Reference: `.env.example` contains additional Firebase client/server placeholders.

### 4) Run the app

```bash
python run.py
```

Open:

- `http://127.0.0.1:5000/`
- Workbench: `http://127.0.0.1:5000/workbench`

## Cloud Deployment (Google App Engine)

This repository already includes `app.yaml`:

```yaml
runtime: python311
entrypoint: gunicorn -b :$PORT run:app
```

### Deploy steps

1. Create/select a GCP project.
2. Enable App Engine + Generative Language API.
3. Set required environment values (especially `GEMINI_API_KEY`).
4. Deploy:

```bash
gcloud app deploy
```

5. Open deployed service:

```bash
gcloud app browse
```

## Important Notes

- `backend/temp_datasets/` stores uploaded standardized files temporarily; `/reset` clears it.
- Do not hardcode API secrets in source. Keep all keys in environment variables.
- Firebase client config in frontend is public-facing metadata by design, but admin secrets must remain server-only.
- The auth admin profile endpoints are placeholders and should be completed before production auth enforcement.

## Minimal Troubleshooting

- **Gemini errors on AI Analyzer**: verify `GEMINI_API_KEY` and API enablement in Google Cloud.
- **Upload parsing fails**: ensure file is valid `.csv` or `.xlsx`.
- **No meaningful fairness output**: provide at least two valid groups and a binary/derivable outcome signal.
- **Auth failures**: check Firebase SDK load and credential wiring.

---

If you want, this README can be split into:

- `README.md` (quickstart + overview)
- `docs/ARCHITECTURE.md` (deep internals)
- `docs/API.md` (request/response schemas)

for cleaner submission formatting.
