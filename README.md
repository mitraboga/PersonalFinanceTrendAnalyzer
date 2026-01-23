# 🧠 End-to-End NLP Project (Streamlit + Training + Evaluation + Deployment)

A production-style NLP system that takes raw text → cleans/structures it → trains & evaluates models → serves predictions through a Streamlit UI (+ optional API/CLI). Built to be reproducible, testable, and deployment-ready.

---

## Demo

**Main App (Streamlit):**
- Paste text or upload a file
- Run predictions (sentiment/topic/intent/etc.)
- View confidence + insights
- Export results

**Add your screenshots here (these will render on GitHub):**
- `assets/ui/01-home.png`
- `assets/ui/02-input.png`
- `assets/ui/03-results.png`
- `assets/ui/04-insights.png`
- `assets/ui/05-batch.png`
- `assets/ui/06-model.png`

---

## What This Project Does

This project builds an end-to-end NLP pipeline that:

1) **Ingests** raw text (CSV/JSON/text box)  
2) **Preprocesses** (cleaning, normalization, tokenization/encoding)  
3) **Trains** models (transformer + classical baselines)  
4) **Evaluates** with meaningful metrics + error analysis  
5) **Serves** predictions via:
   - ✅ **Streamlit web app** for interactive use
   - ✅ Optional **API** for programmatic use
   - ✅ Optional **CLI** for local/batch runs  
6) **Operationalizes**: reproducible runs, saved artifacts, tests, and a deploy-friendly workflow

---

## Key Features

### ✅ Modeling
- Transformer pipeline (fine-tuning) + classical baselines (e.g., Logistic Regression / SVM)
- Config-driven training (swap models without rewriting logic)
- Model artifacts + metadata saved per run (run-id/versioned folders)

### ✅ Evaluation
- Metrics: Accuracy / Precision / Recall / F1 (macro + weighted)
- Confusion matrix + class-wise report
- Error analysis: hardest samples, frequent confusion pairs

### ✅ Inference
- Single text inference (Streamlit + CLI)
- Batch inference (CSV in → CSV out)
- Confidence scores + probabilities (when available)

### ✅ Production-Ready Engineering
- Modular pipeline: ingestion → preprocessing → training → evaluation → serving
- `.env` support for environment configuration
- Docker-friendly layout
- Tests + CI-ready structure

---

## System Overview

High-level flow:

```text
Raw Data/Text
   │
   ▼
Ingestion (load + validate)
   │
   ▼
Preprocessing (clean/tokenize/encode)
   │
   ▼
Training (fit model + save artifacts)
   │
   ▼
Evaluation (metrics + reports)
   │
   ▼
Serving
 ├─ Streamlit UI (interactive)
 └─ API/CLI (optional)
```

---

## Tech Stack

- Python
- Streamlit
- Pandas / NumPy
- scikit-learn
- Transformers + PyTorch (if transformer fine-tuning is used)
- Matplotlib (optional visuals)
- pytest (tests)
- Docker (optional deployment)

---

## Repository Structure

If your repo already has different names, keep your actual names—this structure shows the intended separation of concerns.

```text
.
├── app.py                      # Streamlit entry point
├── src/
│   ├── pipeline/
│   │   ├── ingestion.py         # load/validate datasets
│   │   ├── preprocessing.py     # cleaning + tokenization/encoding
│   │   ├── features.py          # vectorizers/encoders
│   │   ├── train.py             # training loop
│   │   ├── evaluate.py          # metrics + reports
│   │   └── infer.py             # inference utilities
│   ├── models/
│   │   ├── registry.py          # load/save model artifacts
│   │   └── baselines.py         # classical baseline models
│   ├── utils/
│   │   ├── config.py            # config parsing
│   │   ├── io.py                # file helpers
│   │   └── logging.py           # consistent logging
│   └── api/                     # optional FastAPI service
│       ├── main.py
│       └── schemas.py
├── configs/
│   ├── train.yaml               # training configuration
│   └── infer.yaml               # inference configuration
├── data/
│   ├── raw/                     # original data
│   ├── processed/               # cleaned/encoded data
│   └── sample/                  # tiny sample for quick testing
├── artifacts/
│   ├── models/                  # saved models
│   ├── reports/                 # metrics, confusion matrix, etc.
│   └── logs/
├── tests/
│   ├── test_preprocessing.py
│   ├── test_infer.py
│   └── test_training_smoke.py
├── assets/
│   └── ui/                      # Streamlit screenshots live here
├── requirements.txt
├── .env.example
├── README.md
└── LICENSE
```

---

## Getting Started

### 1) Clone & Create a Virtual Environment


git clone <YOUR_REPO_URL>
cd <YOUR_REPO_NAME>

python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS/Linux:
source .venv/bin/activate

### 2) Install Dependencies

```bash
pip install -r requirements.txt
```

### 3) Environment Variables

Copy the template and edit as needed:


cp .env.example .env
```

Example `.env.example`:

```env
APP_ENV=dev
SEED=42

ARTIFACTS_DIR=artifacts
MODEL_DIR=artifacts/models

# Optional API
API_HOST=0.0.0.0
API_PORT=8000
```

### 4) Run the Streamlit App

```bash
streamlit run app.py
```

---

## Data Format

### Common Classification Dataset Format (CSV)

A typical dataset for sentiment/intent/topic classification:

```csv
text,label
"Delivery was fast and smooth",positive
"Support was unhelpful",negative
```

Recommended sample locations:

```text
data/sample/train.csv
data/sample/valid.csv
```

If your app supports batch inference, a minimal unlabeled file often looks like:

```csv
text
"My order arrived early"
"The UI keeps crashing"
```

---

## Training

Update these commands if your repo uses different entry points.

### Train (Config-Driven)

```bash
python -m src.pipeline.train --config configs/train.yaml
```

### Expected Outputs

After training, you should see something like:

```text
artifacts/models/<run_id>/model.pkl   (or model.pt)
artifacts/models/<run_id>/metadata.json
artifacts/reports/<run_id>/metrics.json
artifacts/reports/<run_id>/confusion_matrix.png
```

---

## Evaluation

```bash
python -m src.pipeline.evaluate --model_dir artifacts/models/<run_id> --data data/sample/valid.csv
```

Recommended evaluation outputs:

- Accuracy / Macro-F1 / Weighted-F1
- Confusion matrix
- Class-wise precision/recall
- “Top failure cases” table (text + predicted + actual)

---

## Inference

### Single Text (CLI)

```bash
python -m src.pipeline.infer --model_dir artifacts/models/<run_id> --text "Your text here"
```

### Batch Inference (CSV)

```bash
python -m src.pipeline.infer --model_dir artifacts/models/<run_id> --input data/sample/unlabeled.csv --output artifacts/predictions.csv
```

---

## Streamlit UI Walkthrough (Screenshots + Explanations)

Create the folder:

```bash
mkdir -p assets/ui
```

Save screenshots inside it using these exact names:

```text
01-home.png
02-input.png
03-results.png
04-insights.png
05-batch.png
06-model.png
```

Then add them to GitHub, and they will render automatically below.

---

### 1) Home / Overview

![Home Screen](assets/ui/01-home.png)

What this section shows:

```text
- What the project does (the NLP task(s) supported)
- How to use the app in ~10 seconds
- Current model version / run ID (recommended)
```

What to mention in your explanation:

```text
- The supported tasks (e.g., sentiment, intent, topic)
- Any constraints (max text length, supported file types)
- The “happy path” flow: paste → predict → inspect → export
```

---

### 2) Input Panel (Paste Text / Upload File)

![Input Panel](assets/ui/02-input.png)

What this section does:

```text
- Accepts raw input text for instant prediction
- Supports file upload for batch predictions
- Validates input and shows helpful error messages
```

Document these details:

```text
- Supported upload types (.csv, .txt, .json)
- Required columns (typically: text)
- Example text users can copy/paste
```

---

### 3) Prediction Results (Main Output)

![Results Panel](assets/ui/03-results.png)

What this section explains:

```text
- Predicted label (sentiment/topic/intent/etc.)
- Confidence score (and what it means)
- Extra metadata (probabilities, top keywords, etc.)
```

Recommended to include:

```text
- How confidence is computed (softmax probability, calibrated score, etc.)
- What users should do if confidence is low
```

---

### 4) Insights / Explainability (If Included)

![Insights](assets/ui/04-insights.png)

What this section explains:

```text
- Why the model predicted what it predicted
- Highlighted tokens/keywords (if available)
- Common failure cases + limitations
```

Recommended additions:

```text
- “Known limitations” list (sarcasm, domain shift, slang, etc.)
- Small guidance note for best input quality
```

---

### 5) Batch Predictions (Table + Export)

![Batch Predictions](assets/ui/05-batch.png)

What this section explains:

```text
- Preview of uploaded rows
- How predictions are appended
- Export/download results file
```

Typical output columns:

```text
- prediction
- confidence
- optional: per-class probabilities
```

---

### 6) Model & Experiment Info (Reproducibility)

![Model Details](assets/ui/06-model.png)

What this section explains:

```text
- Model type/name (baseline vs transformer)
- Training data version + preprocessing version
- Metrics snapshot
- Run ID and artifact path
```

---

## Docker (Optional)

### Build

```bash
docker build -t nlp-streamlit .
```

### Run

```bash
docker run -p 8501:8501 nlp-streamlit
```

---

## Testing

```bash
pytest -q
```

Recommended tests:

```text
- Preprocessing correctness
- Inference returns expected schema
- Training “smoke test” on sample data
```

---

## CI/CD (Recommended)

Suggested GitHub Actions checks:

```text
- Lint (ruff/flake8)
- Tests (pytest)
- Docker build (if used)
- Optional: training smoke test on tiny sample data
```

---

## Roadmap

```text
- Add model monitoring + drift detection
- Add active learning loop (collect hard examples)
- Add caching for faster inference
- Add experiment tracking (MLflow/W&B)
- Add API auth + rate limiting
```

---

## License

Choose one:

```text
- MIT
- Apache-2.0
- GPL-3.0
```
