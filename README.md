# Data Analysis Studio

A beginner-friendly, extensible data analysis web application with a Python FastAPI backend and HTML/CSS/JavaScript frontend.

## Features
- Upload CSV, Excel (`.xlsx`, `.xls`) and JSON datasets
- Dataset profiling: rows, columns, missing cells, duplicates, data types, unique counts and sample values
- Preview the first 20 records
- Cleaning suggestions with user approval before applying
- Detect and remove unwanted special symbols while preserving common email/date punctuation
- Detect negative numeric values and convert them to positive values when approved
- Upload/replace a dataset from the dashboard without refreshing the browser
- Conservative cleaning: trim whitespace, fill missing numeric values with median and categorical values with mode, remove exact duplicate rows, convert likely numeric text columns
- Exploratory analysis: numeric distributions, category frequency charts and correlation matrix
- Rule-based insights
- Export processed data as CSV

## Requirements
- Windows 10/11, macOS or Linux
- Python 3.10+

## Run on Windows (PowerShell)
1. Extract the ZIP.
2. Open PowerShell in the extracted `DataAnalysisStudio` folder.
3. Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
pip install -r backend\requirements.txt
```

5. Start the app:

```powershell
uvicorn backend.main:app --reload
```

6. Open http://127.0.0.1:8000

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again.

## Run on macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000

## Important notes
- This is a working starter application, not a claim that every possible analyst workflow is automated.
- Uploaded datasets are held in server memory and disappear when the server restarts. This is suitable for local testing, not production or multi-user deployment.
- The frontend loads Chart.js from a CDN, so charts need an internet connection. Upload, profiling, cleaning and CSV export are handled by the local Python backend.
- Cleaning suggestions are intentionally conservative. Always inspect the data and approve selected operations. The app does not automatically delete columns.
- The current insights engine is rule-based, not connected to a generative AI model.
- For production use, add authentication, persistent storage, upload-size limits, background jobs, audit logs, role permissions and stronger validation.


## Latest fixes
- **Upload / Change dataset** remains available in the header after a dataset is loaded. Select another file without refreshing the browser.
- Special-character cleaning is column-aware: general text removes punctuation/symbols; email, date and phone columns preserve useful characters; numeric/currency columns can be parsed.
- Negative numeric values and parseable negative currency strings can be converted to positive values.
- These cleaning actions appear in the review list and are applied only after approval. Original columns are retained.
