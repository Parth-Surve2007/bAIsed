<p align="center">
  <img src="Screenshot%202026-06-09%20163702.png" alt="bAIsed logo" width="100" height="70" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/AI%20Fairness-Workbench-blueviolet?style=for-the-badge" alt="AI Fairness Workbench" />
  <img src="https://img.shields.io/badge/Bias%20Detection-Enabled-ff6f61?style=for-the-badge" alt="Bias Detection" />
  <img src="https://img.shields.io/badge/Stack-Flask%20%2B%20Frontend-2ea44f?style=for-the-badge" alt="Flask and frontend stack" />
</p>

<h1 align="center">bAIsed</h1>

<p align="center">
  A full-stack AI fairness workbench for dataset bias auditing, disparity diagnostics, scenario simulation, and actionable remediation guidance.
</p>

---

## Mentor Pitch

**bAIsed** is a browser-based fairness debugger for machine-learning datasets and models. It helps a user upload data, detect which groups are being treated unfairly, understand why the disparity is happening, test what-if fixes, and generate a human-readable audit report.

The project matters because fairness work is usually scattered across notebooks, scripts, metrics libraries, and manual reporting. bAIsed pulls that into one guided workflow: analyze, explain, simulate, export, and report.

### One-Line Pitch

> bAIsed is an end-to-end AI fairness workbench that turns raw datasets into explainable bias diagnostics, remediation ideas, and shareable audit reports.

### What It Solves

- Makes fairness analysis easier to run for non-experts.
- Reduces the time needed to inspect bias, proxy features, and subgroup risk.
- Gives both technical metrics and plain-English explanations.
- Helps users move from "I found a bias signal" to "here is what to do next."

### What Makes It Different

- It is not just a metric calculator. It is an interactive workflow.
- It combines deterministic fairness analysis with AI-assisted narrative reporting.
- It includes dataset profiling, proxy detection, simulation, and export tooling in one interface.
- It supports both simple group-rate audits and model-level fairness audits.

### Suggested Demo Flow

1. Open the workbench.
2. Load a demo dataset or upload your own CSV/XLSX.
3. Run the audit and point out DIR, SPD, bias score, hotspots, and proxy risks.
4. Show the simulator and explain how the result changes under a hypothetical fix.
5. Generate the AI report and show how it turns metrics into a readable review.
6. Export the result to Colab or What-If Tool for deeper follow-up.

---

## Overview

**bAIsed** helps teams evaluate, explain, and reduce bias in datasets and machine-learning decision workflows. It combines deterministic fairness metrics, dataset diagnostics, proxy detection, risk profiling, simulation, export tooling, and Gemini-assisted reporting in a browser-based workflow.

The project is designed for researchers, students, and builders who need a practical fairness audit surface without stitching together multiple notebooks, scripts, and reporting tools by hand.

---

## Core Capabilities

- Run quick fairness checks from simple group selection-rate inputs.
- Upload `.csv` or `.xlsx` datasets for structured fairness analysis.
- Upload trained `.pkl`, `.joblib`, or TensorFlow/Keras models with test data for direct prediction fairness analysis.
- Auto-detect likely protected attributes, outcome columns, and qualification signals.
- Compute fairness metrics including DIR, SPD, EOD, AOD, and an aggregate bias score.
- Identify bias hotspots, intersectional disparities, and high-impact feature patterns.
- Detect proxy features using association and correlation signals.
- Profile dataset reliability based on missingness, imbalance, subgroup size, and outcome quality.
- Classify likely bias patterns such as proxy bias, threshold-driven disparity, and underrepresentation.
- Simulate what-if remediation scenarios and estimate trade-offs.
- Generate Gemini-powered audit reports with findings and recommendations.
- Export analysis assets for Google Colab, TensorBoard What-If Tool, and advanced JSON workflows.

---

## How The System Works

The app has two layers:

### Frontend

The frontend is a browser workbench built with HTML, CSS, and JavaScript. It handles file upload, form interactions, result rendering, charting, AI report display, and export actions.

### Backend

The backend is a Flask application that exposes analysis endpoints. It reads datasets, computes fairness metrics, detects patterns, profiles risk, runs simulations, and formats results for the UI.

### End-to-End Flow

1. The user uploads a dataset or selects a demo.
2. The frontend sends the file or dataset ID to the Flask API.
3. The backend standardizes the data and identifies likely protected and outcome columns.
4. The analysis pipeline computes fairness metrics and risk signals.
5. The frontend renders the metrics, charts, and explanations.
6. If requested, Gemini turns the findings into a long-form narrative report.
7. The user can export the analysis for follow-up in external tools.

---

## Why bAIsed

bAIsed complements fairness libraries such as Fairlearn by focusing on an end-to-end audit experience:

- **Interactive workbench:** Upload data, inspect metrics, review hotspots, run simulations, and generate reports from one UI.
- **Dataset-first diagnostics:** Risk profiling, proxy detection, and column detection help users understand whether an audit result is reliable.
- **AI-assisted reporting:** Gemini integration translates metric outputs into readable audit findings and remediation guidance.
- **Exportable workflows:** Colab notebooks, What-If Tool bundles, and JSON exports make it easier to continue analysis outside the app.
- **Modular Flask backend:** Analysis, simulation, risk profiling, proxy detection, pattern classification, and export logic are separated for easier extension.

---

## Architecture

```mermaid
graph LR
    A["Frontend Workbench"] -->|HTTP| B["Flask API"]
    C["Demo Dataset Generator"] --> A
    B --> D["Analysis Pipeline"]
    D --> E["Fairness Metrics"]
    D --> F["Proxy Detector"]
    D --> G["Risk Profiler"]
    D --> H["Pattern Detector"]
    D --> I["Advanced Metrics"]
    D --> J["Simulator"]
    E --> K["Gemini AI Report"]
    F --> K
    G --> K
    H --> K
    I --> K
    J --> K
    K --> A
    A --> L["Colab Export"]
    A --> M["What-If Tool Export"]
    A --> N["Advanced JSON Export"]
```

---

## Feature Modules

### Fairness Analysis

The main analysis pipeline computes group-level outcomes, selection-rate disparities, warning signals, feature influence, repair suggestions, and structured metric explanations.

Implemented metrics include:

- **DIR - Disparate Impact Ratio:** lowest group selection rate divided by highest group selection rate.
- **SPD - Statistical Parity Difference:** difference between the highest and lowest group rates.
- **EOD - Equal Opportunity Difference:** disparity within a qualified subset when qualification data is available.
- **AOD - Average Odds Difference:** combined disparity signal.
- **Bias Score:** normalized 0-100 severity score derived from the metric set.

In practice, this is the core of the audit. The system compares outcomes across groups, identifies where selection rates diverge, and turns those differences into a severity signal plus a human-readable explanation.

### Model Fairness Analysis

The workbench also supports a trained-model audit path:

1. Upload a CSV/XLSX test dataset.
2. Choose a protected attribute and true label column.
3. Upload a `.pkl`, `.joblib`, `.keras`, `.h5`, or `.hdf5` model.
4. bAIsed runs model predictions, stores them in `model_prediction`, and audits those predictions across protected groups.

When true labels are available, the response includes group-level accuracy, error rate, true-positive-rate, false-positive-rate, and false-negative-rate gaps. Model upload support requires compatible server dependencies for the model artifact, such as scikit-learn/joblib or TensorFlow.

This is useful when a user wants to audit a deployed or near-deployed model instead of only a static dataset. The app checks whether the model itself is amplifying disparity through its predictions.

### Advanced Fairness Analysis

`backend/fairness_advanced.py` adds:

- Bootstrap confidence intervals.
- Mitigation suggestions.
- Intersectional analysis across multiple protected attributes.
- Additional advanced metric packaging for export.

This layer helps answer not only "is there bias?" but also "how stable is the signal?" and "does the disparity show up when groups overlap?"

### Proxy Bias Detection

`backend/proxy_detector.py` identifies features that may act as proxies for protected attributes:

- Cramer's V for categorical associations.
- Correlation for numeric relationships.
- Eta-squared for numeric-to-categorical association.
- Risk levels for high, medium, and low proxy signals.

This matters because fairness issues are often indirect. The protected attribute may not be used explicitly, but another feature can quietly encode the same signal.

### Dataset Risk Profiling

`backend/risk_profiler.py` scores audit reliability using:

- Missing value ratios.
- Small subgroup sizes.
- Group imbalance.
- Outcome imbalance.
- Proxy-risk indicators.

This helps prevent overconfidence. A fairness result from a tiny, imbalanced, or sparse dataset should be treated differently from one backed by stronger data.

### Bias Pattern Detection

`backend/pattern_detector.py` classifies common bias patterns:

- `PROXY_BIAS`
- `INTERSECTIONAL_HIDDEN_BIAS`
- `THRESHOLD_DRIVEN_DISPARITY`
- `SMALL_SAMPLE_UNRELIABLE`
- `GROUP_UNDERREPRESENTATION`
- `GLOBAL_SELECTION_DISPARITY`
- `NO_SIGNIFICANT_BIAS`

This gives the user a category-level interpretation. Instead of only showing numbers, the app suggests the kind of bias problem the data most resembles.

### Export Tools

`backend/exporters.py` supports:

- Google Colab notebook export.
- TensorBoard What-If Tool bundle export.
- Advanced JSON export for downstream analysis.

The export layer matters because it lets a mentor, teammate, or reviewer continue the analysis outside the app without starting from scratch.

---

## Tech Stack

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas" />
  <img src="https://img.shields.io/badge/OpenPyXL-107C10?style=for-the-badge&logo=microsoft-excel&logoColor=white" alt="OpenPyXL" />
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="JavaScript" />
  <img src="https://img.shields.io/badge/TailwindCSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind CSS" />
  <img src="https://img.shields.io/badge/Firebase-FFCA28?style=for-the-badge&logo=firebase&logoColor=black" alt="Firebase" />
  <img src="https://img.shields.io/badge/Google%20Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Gemini" />
</p>

---

## Project Structure

```text
bAIsed/
|-- backend/
|   |-- __init__.py
|   |-- app.py
|   |-- api.py
|   |-- analysis.py
|   |-- auth.py
|   |-- demo_datasets.py
|   |-- exporters.py
|   |-- fairness_advanced.py
|   |-- fb_admin.py
|   |-- pattern_detector.py
|   |-- preprocessor.py
|   |-- proxy_detector.py
|   |-- requirements.txt
|   |-- risk_profiler.py
|   |-- simulator.py
|   `-- temp_datasets/
|-- frontend/
|   |-- css/
|   |   `-- custom.css
|   |-- js/
|   |   |-- auth.js
|   |   |-- firebase-config.js
|   |   |-- site.js
|   |   `-- workbench.js
|   `-- pages/
|       |-- 404.html
|       |-- about.html
|       |-- case_study.html
|       |-- contact.html
|       |-- dashboard.html
|       |-- landing.html
|       |-- login.html
|       |-- methodology.html
|       |-- pricing.html
|       |-- privacy_policy.html
|       |-- signup.html
|       |-- solutions.html
|       |-- terms_of_service.html
|       `-- workbench.html
|-- run.py
|-- test_data.csv
`-- README.md
```

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

- `POST /analyze` - quick fairness check from group percentages.
- `POST /scan` - inspect uploaded data and detect likely columns.
- `POST /upload` - upload a dataset and run the full analysis pipeline.
- `POST /model-upload` - upload a trained model plus test data and run a direct prediction fairness audit.
- `POST /simulate` - run what-if fairness improvement scenarios.
- `POST /ai-analyze` - generate a Gemini-assisted audit report.
- `GET /api/demo-dataset/<type>` - download demo data for `credit`, `resume`, or `policing`.
- `GET /api/export/colab/<dataset_id>` - export a Google Colab notebook.
- `GET /api/export/what-if/<dataset_id>` - export a TensorBoard What-If Tool bundle.
- `GET /api/export/advanced-json/<dataset_id>` - export advanced analysis JSON.
- `POST /reset` - clear temporary uploaded datasets.

### Authentication Endpoints

- `POST /api/auth/verify`
- `GET /api/auth/profile`
- `POST /api/auth/profile`

> Firebase profile operations are scaffolded and should be completed before production enforcement.

---

## Local Setup

### Prerequisites

- Python 3.11 or newer
- `pip`

### Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### Configure Environment Variables

Create `backend/.env` or export the variables in your shell:

```env
GEMINI_API_KEY=your_google_ai_key
GEMINI_MODEL=gemini-2.5-flash

FLASK_ENV=development
FLASK_SECRET_KEY=change-me

GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
```

### Run the Application

```bash
python run.py
```

Open:

- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/workbench`

---

## Quick Start

### Try a Demo Dataset

1. Start the Flask app with `python run.py`.
2. Open `http://127.0.0.1:5000/workbench`.
3. Load a demo dataset for lending, hiring, or policing.
4. Review the metrics, proxy risks, reliability score, and recommended actions.
5. Export the result to Colab, What-If Tool, or JSON if needed.

### Audit Your Own Dataset

1. Open the Dataset Audit workflow in the workbench.
2. Upload a `.csv` or `.xlsx` file.
3. Select protected attribute and outcome columns, or use auto-detection.
4. Review fairness metrics, hotspots, feature impact, and risk profiling.
5. Run simulations to compare remediation options.
6. Generate an AI-assisted report and export the analysis.

### Audit A Trained Model

1. Open the Model Audit workflow in the workbench.
2. Upload test data with protected attributes, model features, and a true label.
3. Upload a `.pkl`, `.joblib`, `.keras`, `.h5`, or `.hdf5` model.
4. Select the protected attribute and true label columns.
5. Run the audit to evaluate the model's generated predictions and group-level error disparities.

### How To Explain It To A Mentor

If your mentor asks what the project actually does, explain it in this order:

1. It ingests data or a trained model and tests for fairness issues.
2. It computes selection-rate disparity metrics such as DIR and SPD.
3. It finds the likely protected groups, proxy features, and risky patterns.
4. It checks how trustworthy the result is by profiling the dataset itself.
5. It simulates what would happen if the decision rule changed.
6. It produces a human-readable report so the findings are easy to communicate.

If they ask why this is valuable, say that most fairness projects stop at raw metrics. bAIsed tries to bridge the gap between metric output and actual decision-making.

---

## Deployment

This project can run anywhere that supports a Python Flask application. A typical production start command is:

```bash
gunicorn backend.app:app
```

For Render, use:

```bash
pip install -r backend/requirements.txt
```

as the build command, and:

```bash
gunicorn backend.app:app
```

as the start command.

Before deploying, configure the required environment variables, keep credentials out of source control, and ensure Firebase and Gemini credentials are available only on the server.

---

## Important Notes

- Temporary uploaded datasets are stored in `backend/temp_datasets/`.
- The `/reset` endpoint clears temporary uploaded datasets.
- Column names are standardized during preprocessing.
- Gemini reporting requires `GEMINI_API_KEY`.
- Firebase admin credentials must remain server-side.
- Authentication is scaffolded and should be hardened before production use.
- Do not commit `.env`, service account files, or generated temporary datasets.

### Module Cheat Sheet

- `backend/app.py`: creates the Flask app and serves the frontend pages.
- `backend/api.py`: hosts the API routes, request handling, uploads, analysis orchestration, exports, and AI reporting.
- `backend/analysis.py`: computes the core fairness metrics and dataset analysis.
- `backend/proxy_detector.py`: looks for proxy variables that may encode protected attributes.
- `backend/risk_profiler.py`: judges how trustworthy the audit is based on dataset quality.
- `backend/pattern_detector.py`: labels the likely bias pattern.
- `backend/fairness_advanced.py`: adds advanced metrics and intersectional analysis.
- `backend/simulator.py`: runs what-if remediation scenarios.
- `backend/exporters.py`: builds notebook and tool exports.
- `frontend/js/workbench.js`: handles the interactive workbench, uploads, charts, AI report rendering, and exports.

### Short Pitch Script

You can say this almost verbatim:

> bAIsed is a fairness workbench that lets me upload a dataset or model, compute bias metrics, detect proxy features, evaluate dataset risk, simulate possible fixes, and generate a narrative AI report. The goal is to make fairness analysis easier to understand and easier to act on, not just to display raw numbers.

---

## Troubleshooting

- **Gemini report errors:** Confirm `GEMINI_API_KEY` is configured and the Generative Language API is enabled.
- **Upload parsing errors:** Validate that the file is a readable `.csv` or `.xlsx`.
- **Unexpected fairness output:** Check that the selected outcome is binary or can be converted into a binary decision signal.
- **Weak audit confidence:** Review subgroup size, missing data, and outcome imbalance warnings.
- **Render import errors:** Use `gunicorn backend.app:app` as the start command and confirm dependencies are installed.

---

## Roadmap

- Complete production-ready Firebase profile enforcement.
- Add formal automated tests for the full API and analysis pipeline.
- Expand mitigation recommendations with configurable policy constraints.
- Split long-form technical documentation into dedicated `docs/` files.

---
