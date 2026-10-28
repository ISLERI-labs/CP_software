# Getting started

This guide runs the CerePhyte dashboard and API on a computer that can reach the NodeMCU access point at `192.168.4.1`.

## Requirements

- Python 3.10 or later.
- Network connectivity to the NodeMCU at `192.168.4.1`.
- Windows for the bundled `run.bat` launcher. On other platforms, start the two services with the commands below.

Install dependencies from the dashboard directory:

```powershell
cd CerePhyte_Dashboard
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the `py` launcher is unavailable, use `python` to create the environment. Activate or explicitly use the environment's Python executable for subsequent commands.

## Start the application

On Windows, run `run.bat` from `CerePhyte_Dashboard`. It opens separate command windows for Streamlit and Uvicorn. Close both windows to stop the services.

Alternatively, open two terminals in `CerePhyte_Dashboard` and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS or Linux, substitute `.venv\Scripts\python.exe` with `.venv/bin/python`.

Open the dashboard at <http://localhost:8501>. The API's interactive OpenAPI documentation is available at <http://localhost:8000/docs>.

## Configuration

- The API polls `http://192.168.4.1/api/data` every 200 ms. The NodeMCU address is currently configured in `main.py`.
- The dashboard's telemetry URL defaults to `http://127.0.0.1:8000/telemetry`; it can be changed in the dashboard sidebar.
- MUX control requests use `http://127.0.0.1:8000` as the FastAPI base URL.
- On Windows, dashboard history and preferences are stored separately under `%LOCALAPPDATA%\CerePhyte\state\` as `cerephyte_history.csv` and `dashboard_config.json`. On other platforms, the same files are stored under `~/CerePhyte/state/`.
- The dashboard remembers theme, refresh interval, graph window, MUX selections, chart series/mode/filter, and filter cutoffs.
- Install dependencies from the updated `requirements.txt` to enable SciPy Butterworth filters and PyWavelets denoising.

## Troubleshooting

- **No live data:** Check that both services are running, the computer can reach the NodeMCU, and `http://127.0.0.1:8000/telemetry` returns a payload with `"ok": true`.
- **FastAPI reports NodeMCU unavailable:** Verify the device address and network connection. The API currently uses a fixed NodeMCU address and a one-second HTTP timeout.
- **Dashboard cannot reach the API:** Check the telemetry URL in the sidebar and verify that the API is listening on port 8000.
- **MUX control fails:** Check that the API is running at `127.0.0.1:8000` and that the requested channel is between 0 and 7 inclusive.

The launcher binds the API to `0.0.0.0`, making it reachable on network interfaces. Use it only on a trusted network; the API does not implement authentication.
