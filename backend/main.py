from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
import numpy as np
import io, uuid, json, re, unicodedata
from pathlib import Path

app = FastAPI(title="Data Analysis Studio API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
DATASETS = {}

class DatasetRequest(BaseModel):
    dataset_id: str

class CleanRequest(BaseModel):
    dataset_id: str
    actions: list[str] = []

def get_df(dataset_id):
    if dataset_id not in DATASETS:
        raise HTTPException(404, "Dataset not found. Please upload it again.")
    return DATASETS[dataset_id]

def json_safe(value):
    if pd.isna(value): return None
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)): return float(value)
    if isinstance(value, (np.bool_,)): return bool(value)
    return str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value

@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Data Analysis Studio API is running"}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = file.filename or "dataset"
    raw = await file.read()
    try:
        if name.lower().endswith(".csv"):
            try: df = pd.read_csv(io.BytesIO(raw))
            except UnicodeDecodeError: df = pd.read_csv(io.BytesIO(raw), encoding="latin-1")
        elif name.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw))
        elif name.lower().endswith(".json"):
            df = pd.read_json(io.BytesIO(raw))
        else:
            raise HTTPException(400, "Supported formats: CSV, XLSX, XLS, JSON")
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")
    if df.empty and len(df.columns) == 0: raise HTTPException(400, "The uploaded file is empty.")
    df.columns = [str(c) for c in df.columns]
    dataset_id = str(uuid.uuid4())
    DATASETS[dataset_id] = df.copy()
    return {"dataset_id": dataset_id, "filename": name, "profile": make_profile(df), "preview": df.head(20).replace({np.nan: None}).to_dict(orient="records")}

def make_profile(df):
    missing = df.isna().sum()
    columns = []
    for c in df.columns:
        s = df[c]
        sample = [json_safe(x) for x in s.dropna().head(4).tolist()]
        columns.append({"name": c, "dtype": str(s.dtype), "missing": int(s.isna().sum()),
                        "missing_pct": round(float(s.isna().mean()*100), 2),
                        "unique": int(s.nunique(dropna=True)), "sample": sample})
    numeric = df.select_dtypes(include=np.number)
    stats = {}
    if not numeric.empty:
        stats = numeric.describe().replace({np.nan: None}).to_dict()
    return {"rows": int(len(df)), "columns_count": int(len(df.columns)),
            "duplicate_rows": int(df.duplicated().sum()), "missing_cells": int(missing.sum()),
            "memory_kb": round(float(df.memory_usage(deep=True).sum()/1024), 2),
            "columns": columns, "numeric_summary": stats}

@app.post("/api/profile")
def profile(req: DatasetRequest):
    return make_profile(get_df(req.dataset_id))


def column_kind(column_name, series):
    name = str(column_name).lower()
    if any(k in name for k in ["email", "e-mail", "mail"]): return "email"
    if any(k in name for k in ["date", "dob", "time"]): return "date"
    if any(k in name for k in ["phone", "mobile", "contact", "tel"]): return "phone"
    if any(k in name for k in ["amount", "price", "salary", "sales", "revenue", "cost", "total", "balance", "fee"]): return "numeric"
    if pd.api.types.is_numeric_dtype(series): return "numeric"
    return "text"

def parse_numeric_text(value):
    if value is None or pd.isna(value): return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)): return float(value)
    cleaned = re.sub(r"[^0-9.+-]", "", str(value).strip().replace(",", ""))
    if cleaned in ("", "-", "+", ".", "-.", "+."): return np.nan
    try: return float(cleaned)
    except ValueError: return np.nan

def clean_special_value(value, kind):
    if not isinstance(value, str): return value
    value = value.strip()
    if kind == "email":
        return re.sub(r"[^\w@.+-]", "", value, flags=re.UNICODE)
    if kind == "date":
        return re.sub(r"[^\w\s./:-]", "", value, flags=re.UNICODE)
    if kind == "phone": return re.sub(r"[^0-9+]", "", value)
    if kind == "numeric":
        n = parse_numeric_text(value)
        return n if not np.isnan(n) else value
    return "".join(ch for ch in value if ch.isspace() or unicodedata.category(ch)[0] not in ("P", "S"))

@app.post("/api/clean/preview")
def clean_preview(req: DatasetRequest):
    df = get_df(req.dataset_id)
    suggestions = []
    for c in df.columns:
        col = df[c]
        if col.isna().any():
            suggestions.append({"id":f"missing:{c}","column":c,"issue":"Missing values","count":int(col.isna().sum()),"recommendation":"Numeric: median; categorical: mode. Review before applying."})
        if col.dtype == "object" or pd.api.types.is_string_dtype(col):
            vals = col.dropna().astype(str)
            trims = int((vals.str.strip() != vals).sum())
            if trims:
                suggestions.append({"id":f"trim:{c}","column":c,"issue":"Extra spaces","count":trims,"recommendation":"Remove leading/trailing spaces."})
            kind = column_kind(c, col)
            cleaned = col.map(lambda x: clean_special_value(x, kind))
            special = int((col.astype(str) != cleaned.astype(str)).sum())
            if special:
                suggestions.append({"id":f"special:{c}","column":c,"issue":"Special characters / symbols","count":special,"recommendation":"Remove unwanted symbols while preserving useful email, date and phone characters."})
            if kind == "numeric":
                parsed = col.map(parse_numeric_text)
                ratio = parsed.notna().sum()/max(1, col.notna().sum())
                if col.notna().sum() and ratio >= .7:
                    suggestions.append({"id":f"numeric:{c}","column":c,"issue":"Numbers stored as text","count":int(parsed.notna().sum()),"recommendation":"Convert currency/number text to numeric values."})
                neg = int((parsed.dropna() < 0).sum())
                if neg:
                    suggestions.append({"id":f"absolute:{c}","column":c,"issue":"Negative values","count":neg,"recommendation":"Convert negative values to positive using absolute value."})
        elif pd.api.types.is_numeric_dtype(col):
            neg = int((col.dropna() < 0).sum())
            if neg:
                suggestions.append({"id":f"absolute:{c}","column":c,"issue":"Negative values","count":neg,"recommendation":"Convert negative values to positive using absolute value."})
    dup = int(df.duplicated().sum())
    if dup:
        suggestions.append({"id":"duplicates","column":"All columns","issue":"Duplicate rows","count":dup,"recommendation":"Remove exact duplicate rows."})
    return {"suggestions":suggestions,"note":"Review and select operations before applying. Original columns are retained."}

@app.post("/api/clean/apply")
def clean_apply(req: CleanRequest):
    df = get_df(req.dataset_id).copy()
    applied = []
    for action in req.actions:
        if action == "duplicates":
            before=len(df); df=df.drop_duplicates(); applied.append({"action":action,"changed":before-len(df)}); continue
        if ":" not in action: continue
        kind, col = action.split(":",1)
        if col not in df.columns: continue
        series=df[col]
        if kind == "trim":
            before=series.astype(str); df[col]=series.map(lambda x:x.strip() if isinstance(x,str) else x)
            applied.append({"action":action,"changed":int((before!=df[col].astype(str)).sum())})
        elif kind == "missing":
            if pd.api.types.is_numeric_dtype(series): fill=series.median()
            else:
                modes=series.mode(dropna=True); fill=modes.iloc[0] if len(modes) else None
            if fill is not None and not pd.isna(fill):
                n=int(series.isna().sum()); df[col]=series.fillna(fill); applied.append({"action":action,"changed":n,"fill_value":json_safe(fill)})
        elif kind == "numeric":
            parsed=series.map(parse_numeric_text); ratio=parsed.notna().sum()/max(1,series.notna().sum())
            if ratio>=.7: df[col]=parsed; applied.append({"action":action,"changed":int(parsed.notna().sum())})
        elif kind == "special":
            typ=column_kind(col,series); before=series.astype(str)
            df[col]=series.map(lambda x:clean_special_value(x,typ))
            applied.append({"action":action,"changed":int((before!=df[col].astype(str)).sum())})
        elif kind == "absolute":
            if pd.api.types.is_numeric_dtype(series):
                n=int((series.dropna()<0).sum()); df[col]=series.abs()
            else:
                parsed=series.map(parse_numeric_text); ratio=parsed.notna().sum()/max(1,series.notna().sum())
                n=int((parsed.dropna()<0).sum())
                if ratio>=.7: df[col]=parsed.abs()
                else: n=0
            applied.append({"action":action,"changed":n})
    DATASETS[req.dataset_id]=df
    return {"profile":make_profile(df),"applied":applied,"preview":df.head(20).replace({np.nan:None}).to_dict(orient="records")}

@app.post("/api/analyze")
def analyze(req: DatasetRequest):
    df = get_df(req.dataset_id)
    numeric = df.select_dtypes(include=np.number)
    categorical = df.select_dtypes(exclude=np.number)
    correlations = {}
    if numeric.shape[1] >= 2:
        corr = numeric.corr(numeric_only=True).round(3).replace({np.nan: None})
        correlations = {"labels": list(corr.columns), "matrix": corr.values.tolist()}
    distributions = []
    for c in numeric.columns[:8]:
        vals = numeric[c].dropna()
        if len(vals):
            counts, edges = np.histogram(vals, bins=min(12, max(4, int(np.sqrt(len(vals))))))
            distributions.append({"column":c,"labels":[round(float((edges[i]+edges[i+1])/2),2) for i in range(len(counts))],"values":counts.tolist()})
    category_counts = []
    for c in categorical.columns[:5]:
        vc = df[c].fillna("(Missing)").astype(str).value_counts().head(8)
        category_counts.append({"column":c,"labels":vc.index.tolist(),"values":vc.values.tolist()})
    return {"correlations":correlations,"distributions":distributions,"categories":category_counts}

@app.post("/api/insights")
def insights(req: DatasetRequest):
    df = get_df(req.dataset_id)
    p = make_profile(df)
    lines = [f"Your dataset contains {p['rows']:,} rows and {p['columns_count']} columns."]
    if p["missing_cells"]: lines.append(f"There are {p['missing_cells']:,} missing cells. Review the cleaning suggestions before filling them.")
    else: lines.append("No missing cells were detected.")
    if p["duplicate_rows"]: lines.append(f"{p['duplicate_rows']:,} exact duplicate rows were found.")
    else: lines.append("No exact duplicate rows were found.")
    nums = df.select_dtypes(include=np.number)
    if not nums.empty:
        for c in nums.columns[:5]:
            s=nums[c].dropna()
            if len(s): lines.append(f"{c}: average {s.mean():,.2f}, median {s.median():,.2f}, range {s.min():,.2f} to {s.max():,.2f}.")
    if len(df.columns): lines.append("Next step: investigate unusual values and relationships between columns before making business decisions.")
    return {"insights":lines,"type":"rule-based"}

@app.post("/api/export")
def export(req: DatasetRequest):
    df = get_df(req.dataset_id)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=analysis_dataset.csv"})

app.mount("/", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "frontend"), html=True), name="frontend")
