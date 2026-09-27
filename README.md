# Predictive Decision Support System (PDSS)

PDSS is a full-stack vendor-risk and supply-chain continuity application. The backend exposes FastAPI endpoints for vendor data, delay/risk prediction, forecasting, and vendor recommendations. The frontend is a React + Vite dashboard.

## Project structure

```text
PDSS/
├── backend/
│   ├── app/
│   ├── data/raw/
│   ├── models/
│   ├── supply_chain.db
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- npm

The repository already contains trained model artifacts and a populated SQLite database, so **normal startup does not require Kaggle credentials or retraining**.

## 1. Start the backend

Open a terminal in the `PDSS` folder.

### Windows PowerShell

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
python backend/app/main.py
```

If PowerShell blocks activation, use:

```powershell
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
..\.venv\Scripts\python.exe backend/app/main.py
```

The API runs at:

- http://localhost:8000
- Swagger UI: http://localhost:8000/docs

### macOS/Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
python backend/app/main.py
```

## 2. Start the frontend

Open a second terminal in the `PDSS` folder:

```bash
cd frontend
npm install
npm run dev
```

Vite normally starts at:

- http://localhost:5173

The frontend reads the backend URL from `VITE_API_BASE_URL`. If it is not set, it defaults to `http://localhost:8000`.

For a different backend URL, create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 3. Verify the application

1. Start the backend and open `/docs`.
2. Start the frontend and open the Vite URL.
3. Confirm the dashboard loads vendors and model metrics.
4. Test Vendor Comparison, Risk Heatmap, Forecast, and Scenario Simulator.

## Model retraining

Retraining is intentionally **not performed automatically** during API startup. This prevents every restart from downloading datasets and retraining models.

If you explicitly want to retrain, configure your Kaggle credentials outside Git and run:

### Windows PowerShell

```powershell
$env:PDSS_RUN_PIPELINE="1"
python backend/app/main.py
```

### macOS/Linux

```bash
PDSS_RUN_PIPELINE=1 python backend/app/main.py
```

Kaggle credentials should be stored in the normal user location (`~/.kaggle/kaggle.json`) and **must not be committed to Git**. If a credential has previously been committed or shared, revoke/rotate it in Kaggle before using the repository again.

## Common problems

### `ModuleNotFoundError`

Activate the backend virtual environment and run:

```bash
pip install -r backend/requirements.txt
```

### `vite is not recognized` / `vite: not found`

From `frontend` run:

```bash
npm install
npm run dev
```

### Backend says model artifacts are missing

The normal repository should contain the files under `backend/models/`. If they are missing, configure Kaggle credentials and explicitly run the training pipeline with `PDSS_RUN_PIPELINE=1`.

### Frontend cannot reach the API

Confirm the backend is running on port 8000 and check `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Git safety

Do not commit:

- `kaggle.json`
- `.env` files containing secrets
- Python virtual environments
- `node_modules`
- build output

Before pushing:

```bash
git status
git add .
git commit -m "Fix PDSS setup and startup"
git push
```
