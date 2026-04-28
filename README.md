# bAIsed

<p align="center">
  <img src="https://img.shields.io/badge/AI%20Fairness-Workbench-blueviolet?style=for-the-badge" alt="AI Fairness Workbench">
  <img src="https://img.shields.io/badge/Bias%20Detection-Enabled-ff6f61?style=for-the-badge" alt="Bias Detection">
  <img src="https://img.shields.io/badge/Full%20Stack-Flask%20%2B%20Frontend-2ea44f?style=for-the-badge" alt="Full Stack">
</p>

<p align="center">
  AI fairness workbench for dataset bias auditing, disparity diagnostics, simulation, and actionable remediation guidance.
</p>

---

## Overview

**bAIsed** is a full-stack application built to help teams evaluate fairness in machine learning systems and understand where bias comes from. It supports quick fairness checks, deeper dataset analysis, what-if simulation, and AI-generated reporting so users can move from detection to remediation in one workflow.

The project combines deterministic fairness metrics with a modern interface and Gemini-powered analysis to provide both technical depth and practical insight.

---

## What This Project Does

bAIsed helps teams to:

- run fairness checks using either simple percentage inputs or real datasets (`.csv`, `.xlsx`)
- compute core parity metrics such as **DIR**, **SPD**, **EOD**, and **AOD**
- detect root-cause feature impact and subgroup hotspots
- generate counterfactual repair suggestions and what-if simulation outputs
- produce AI-written analysis reports using **Google Gemini**

---

## Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white" alt="NumPy">
  <img src="https://img.shields.io/badge/OpenPyXL-107C10?style=for-the-badge&logo=microsoft-excel&logoColor=white" alt="OpenPyXL">
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5">
  <img src="https://img.shields.io/badge/TailwindCSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="TailwindCSS">
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript">
  <img src="https://img.shields.io/badge/Firebase-FFCA28?style=for-the-badge&logo=firebase&logoColor=black" alt="Firebase">
  <img src="https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Gemini">
  <img src="https://img.shields.io/badge/Google%20App%20Engine-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white" alt="Google App Engine">
</p>

---

## Key Features

### Fairness Evaluation
- Instant fairness checks using manual group inputs
- Dataset-based bias analysis for uploaded `.csv` and `.xlsx` files
- Structured metric output for clear interpretation

### Deep Dataset Diagnostics
- Group statistics and disparity detection
- Feature impact ranking
- Bias hotspot identification
- Suggested remediation paths

### AI-Assisted Reporting
- Gemini-powered report synthesis
- Plain-language summaries of metrics and findings
- Faster analysis for technical and non-technical users

### Simulation and Exploration
- What-if simulation for fairness improvement
- Estimated changes in parity and accuracy
- Interactive trade-off analysis

### Authentication and Product UI
- Firebase-based sign-in flow
- Email/password login support
- Google sign-in support
- Clean multi-page frontend experience

---

## Metrics Implemented

bAIsed computes the following fairness signals:

- **DIR (Disparate Impact Ratio)**: minimum selection rate divided by maximum selection rate
- **SPD (Statistical Parity Difference)**: difference between the highest and lowest group rates
- **EOD (Equal Opportunity Difference)**: disparity inside the qualified subset
- **AOD (Average Odds Difference)**: combined disparity signal
- **Bias Score (0–100)**: weighted aggregate of DIR gap, SPD, EOD, and AOD

### Severity Thresholds

- **HIGH**: DIR < 0.5
- **MODERATE**: 0.5 ≤ DIR < 0.8
- **LOW**: DIR ≥ 0.8

---

## Project Structure

```text
bAIsed/
├─ backend/
│  ├─ app.py
│  ├─ api.py
│  ├─ analysis.py
│  ├─ simulator.py
│  ├─ preprocessor.py
│  ├─ auth.py
│  ├─ fb_admin.py
│  ├─ requirements.txt
│  ├─ .env
│  └─ temp_datasets/
├─ frontend/
│  ├─ pages/
│  │  ├─ workbench.html
│  │  ├─ landing.html
│  │  ├─ about.html
│  │  ├─ solutions.html
│  │  ├─ methodology.html
│  │  ├─ case_study.html
│  │  ├─ pricing.html
│  │  ├─ login.html
│  │  ├─ signup.html
│  │  ├─ dashboard.html
│  │  └─ 404.html
│  ├─ js/
│  │  ├─ workbench.js
│  │  ├─ site.js
│  │  ├─ auth.js
│  │  └─ firebase-config.js
│  └─ css/
│     └─ custom.css
├─ run.py
├─ app.yaml
├─ .env.example
├─ test_data.csv
└─ .gitignore
```

---

## How It Works

1. The user opens the **Workbench**.
2. The frontend sends requests for either quick analysis or dataset analysis.
3. The backend processes the data and computes fairness metrics.
4. Results are returned as structured JSON.
5. The UI renders metrics, hotspots, feature analysis, and repair suggestions.
6. The simulator estimates how fairness and accuracy change under alternative settings.
7. The AI analyzer generates a readable fairness report with Gemini.

---

## API Overview

### Site and Utility Endpoints
- `GET /api/health`
- `GET /api/site-content/<page_name>`
- `GET /api/search?query=...`
- `POST /api/actions/resolve`
- `POST /api/demo-request`
- `GET /api/downloads/whitepaper`

### Workbench Endpoints
- `POST /analyze`
- `POST /scan`
- `POST /upload`
- `POST /simulate`
- `POST /ai-analyze`
- `POST /reset`

### Authentication Endpoints
- `POST /api/auth/verify`
- `GET /api/auth/profile`
- `POST /api/auth/profile`

> Note: Firebase admin profile operations are scaffolded and not fully implemented yet.

---

## Local Setup

### Prerequisites
- Python 3.11 or higher
- pip

### Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### Configure Environment Variables
Create `backend/.env` or export the variables in your environment:

```env
GEMINI_API_KEY=your_google_ai_key
GEMINI_MODEL=gemini-1.5-flash

FLASK_ENV=development
FLASK_SECRET_KEY=change-me

GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
```

Reference `.env.example` for additional client and server placeholders.

### Run the Application
```bash
python run.py
```

Open:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/workbench`

---

## Deployment

This repository includes Google App Engine configuration in `app.yaml`:

```yaml
runtime: python311
entrypoint: gunicorn -b :$PORT run:app
```

### Deploy Steps
1. Create or select a Google Cloud project.
2. Enable App Engine and the Generative Language API.
3. Set the required environment variables, especially `GEMINI_API_KEY`.
4. Deploy the application:
   ```bash
   gcloud app deploy
   ```
5. Open the deployed service:
   ```bash
   gcloud app browse
   ```

---

## Important Notes

- Uploaded standardized files are stored temporarily in `backend/temp_datasets/`.
- The `/reset` endpoint clears temporary uploads.
- Do not hardcode API keys or secrets in source files.
- Keep Firebase admin credentials server-side only.
- The auth backend is scaffolded and should be completed before production enforcement.

---

## Troubleshooting

- **Gemini errors**: Verify `GEMINI_API_KEY` and API enablement in Google Cloud.
- **Upload parsing issues**: Make sure the file is a valid `.csv` or `.xlsx`.
- **Unexpected fairness output**: Use at least two valid groups and a binary or derivable outcome signal.
- **Auth failures**: Check Firebase configuration and credential wiring.

---

## Suggested Documentation Split

For cleaner maintenance, this README can be split into:

- `README.md` for overview and quickstart
- `docs/ARCHITECTURE.md` for system internals
- `docs/API.md` for request and response schemas

---

## License

Add your preferred license here before publishing the repository.
