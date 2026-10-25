# CerePhyte Rev. 4.5 Dashboard

## Included
- Live telemetry cards for sample, A0, battery, current, T2, T3/LED and packet age.
- A0-only live graph.
- Local CSV recording in `cerephyte_history.csv` (no SQLite database).
- Adjustable refresh interval and graph window; CSV export.
- `run.bat` launches FastAPI and Streamlit together on Windows.
- `run.sh` is included for Bash / Git Bash / WSL users.

## Windows setup

1. Open this folder in Command Prompt or PowerShell.
2. Create a virtual environment (recommended):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Double-click `run.bat` (or run `run.bat` from the terminal).
4. Open the dashboard at `http://localhost:8501`.

The batch file automatically uses `.venv\Scripts\python.exe` if that environment exists; otherwise it uses `python` from PATH. It opens FastAPI and Streamlit in separate command windows. Close those windows to stop the services.

## FastAPI module name

By default, `run.bat` expects `main.py` in this folder to contain `app = FastAPI(...)`. If your API file is named `api.py`, open Command Prompt in this folder and run:

```bat
set FASTAPI_APP=api:app
run.bat
```

Replace `api:app` with `your_filename:app` if the file has a different name. The `app.py` file in this package is the Streamlit dashboard, so do not use `app:app` for FastAPI unless your API object is actually defined there.

## Data endpoint

The dashboard defaults to `http://127.0.0.1:8000/telemetry`. Change it in the sidebar if needed.

## CSV recording caveat

The dashboard writes a row when the Arduino sample counter changes. Because FastAPI currently exposes only its latest snapshot, dashboard polling may skip intermediate Arduino samples. For lossless scientific recording, log every serial sample in the FastAPI collector itself, then have the dashboard read that CSV.
