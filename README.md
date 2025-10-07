# Personal Finance Trend Analyzer

A practical, resume-ready data science project: ingest bank/UPI exports, auto-categorize transactions with **rules + NLP**, visualize trends, and **forecast** future spend. Built with **Pandas**, **Plotly**, **Streamlit**, and classic time-series models.

> Works on Windows with VSCode. ARIMA/ETS by default; Prophet optional.

---

## 🚀 Features

- **Flexible ingestion**: CSV/Excel from banks/wallets (PhonePe, ICICI, etc.) → standardized schema  
- **Cleaning**: robust parsing of dates/amounts; signed spending  
- **Categorization**: keyword rules + optional TF-IDF Logistic Regression model you can train  
- **Visualizations**: interactive Plotly charts (category bars, monthly trend)  
- **Forecasting**: auto-ARIMA (if available) or Exponential Smoothing fallback  
- **Deliverables**: batch pipeline outputs (CSV + HTML charts) and a Streamlit dashboard

---

### Budgets & Alerts
- Configure caps in `config/budgets.yml`:
  - `monthly_total_cap` for overall budget
  - `categories:` for per-category caps
  - `warn_threshold` (e.g., 0.9 = alert at 90% used)
- Dashboard shows **TOTAL** + per-category status (OK / NEAR / OVER) and a
  **“this month vs 3-month average”** variance card.
- Batch pipeline writes `outputs/alerts.csv` for automation/reporting.

---

## 📦 Project Structure

personal-finance-trend-analyzer/
├─ app.py
├─ requirements.txt
├─ README.md
├─ config/
│ ├─ category_rules.yml
│ └─ schema.json
├─ data/
│ └─ sample_transactions.csv
├─ pipeline/
│ ├─ init.py
│ ├─ utils.py
│ ├─ ingestion.py
│ ├─ cleaning.py
│ ├─ categorize.py
│ ├─ forecasting.py
│ └─ visualize.py
├─ scripts/
│ ├─ run_pipeline.py
│ └─ train_classifier.py
├─ outputs/ # generated artifacts (gitignored is recommended)
├─ models/ # saved classifier (gitignored is recommended)
├─ tests/
│ └─ test_ingestion.py
└─ .vscode/
├─ launch.json
└─ settings.json