# CerePhyte Dashboard

## Included
- Live telemetry cards for sample, A0, battery, current, T2, T3/LED and packet age.
- Local CSV recording (no SQLite database).
- Start/stop named CSV recordings using the CerePhyte history column format; recordings default to `%LOCALAPPDATA%\CerePhyte\state\recordings` and can be saved to a custom folder.
- Generate a publication-style PDF from an uploaded or drag-and-dropped recording CSV. The report uses ISLERI's restrained violet-to-cyan accent, the supplied logo, embedded local monospaced/sans-serif fonts, technical metadata, and a closing calibration/experimental-conditions disclaimer. Configure multiple charts, including repeated scientific views with different filters and cutoff values.
- Adjustable refresh interval and graph window; CSV export.
- Selectable ADS1115 voltage, battery voltage, current consumption, and derived signal-strength series.
- Scientific graph views: line, smoothed trend, time/amplitude-density heatmap, value distribution, and FFT spectrum.
- Raw, FFT, and fourth-order Butterworth low/high/band-pass filters, plus Daubechies-4 wavelet denoising. Filter cutoffs are entered in Hz; frequency-domain modes resample recorded telemetry to its median interval.
- Chart calculation runs separately from fast live telemetry polling, refreshes every two seconds, and displays an ISLERI-branded animated loading panel with operation-specific status text while preparing a chart.
- Chart analysis uses at most 3,000 points; resampling that would exceed this limit is rejected with a clear message. Work is bounded rather than spawning extra processes for small signals.
- Selectable CerePhyte blue and ISLERI violet-to-cyan dashboard backgrounds.
- Animated ISLERI-branded loading screen while the dashboard connects on first load.
- ISLERI logo image is loaded from `isleri_logo.jpg` in this folder.
- Dashboard preferences (background, refresh interval, graph window, selected MUX channels, chart series/mode/filter, and filter cutoffs) are stored separately from history in `%LOCALAPPDATA%\CerePhyte\state\dashboard_config.json` on Windows.
- On Windows, CSV history is stored at `%LOCALAPPDATA%\CerePhyte\state\cerephyte_history.csv`.
- Named recordings are stored in `%LOCALAPPDATA%\CerePhyte\state\recordings` by default; the recording panel accepts a custom folder path.
- PDF reports include ISLERI branding, recording timestamps, voltage summary statistics, UTC chart axes, and one page per configured scientific chart.
- `run.bat` launches FastAPI and Streamlit together on Windows.
- `run.sh` is included for Bash / Git Bash / WSL users.

## ISLERI development update

**CerePhyte Dashboard — Scientific Charting & Performance Improvements**

- 📊 Choose among ADS1115 voltage, battery voltage, current consumption, and derived signal strength.
- 🔬 Use line, smoothed trend, time-amplitude heatmap, distribution, or FFT spectrum views.
- 🎛️ Apply raw, FFT, Butterworth, or Daubechies-4 wavelet processing.
- 🌌 View an animated ISLERI-branded chart loading panel with status text matched to the selected calculation.
- ⚡ Keep chart refreshes independent of live telemetry polling, with bounded data processing to help avoid long or excessive calculations.

Signal strength is derived from ADS1115 voltage variation and is not an independent sensor reading. NumPy, SciPy, PyWavelets, Matplotlib, and ReportLab are listed in `requirements.txt`; install the updated requirements to enable all filter options and PDF report generation.

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

The dashboard writes a row when the Arduino sample counter changes. The active named recording and local history archive receive the same rows and CSV columns. Because FastAPI currently exposes only its latest snapshot, dashboard polling may skip intermediate Arduino samples. For lossless scientific recording, log every serial sample in the FastAPI collector itself, then have the dashboard read that CSV.

## PDF reports

Open **Generate report from a recording CSV**, then choose a CerePhyte-format CSV in the file picker or drag it into the upload area. Add or remove chart configurations independently; repeated views are supported with different signals, filters, and cutoff values. The exported PDF contains a technical metadata page, one chart page per configuration, and a final notes/sign-off page. Charts use up to the latest 3,000 rows, consistent with the dashboard analysis limit. Both dashboard and command-line reports embed locally bundled DejaVu Sans Mono and DejaVu Sans fonts; no internet access is required at report time.

### Generate a complete report from the command line

The standalone ReportLab script creates the standard report suite without launching Streamlit:

```powershell
cd CerePhyte_Dashboard
python -m pip install -r requirements.txt
python generate_scientific_report.py ..\cerephyte_history.csv
```

By default, the PDF is written beside the CSV as `cerephyte_history_scientific_report.pdf`. Choose a different destination or logo with:

```powershell
python generate_scientific_report.py ..\cerephyte_history.csv --output C:\Reports\plant-study.pdf --logo .\isleri_logo.jpg
```

The script uses ReportLab for paginated PDF layout and Matplotlib for chart images. It includes raw line and moving-average views, raw and wavelet-denoised time-amplitude heatmaps, FFT and distribution charts, and a Daubechies-4 denoised line view. The report uses a monospace-first technical hierarchy, embedded local fonts, restrained ISLERI gradient rules, source/generation/UTC metadata, an instrument summary, and the disclaimer/operator sign-off page. It rejects CSV files that do not contain the complete CerePhyte column set. Plotting is bounded to 3,000 samples per chart. The standard suite has nine pages: one summary, seven charts, and one notes/sign-off page.

The branded PDF's supporting stylesheet and typography use DejaVu Sans Mono for identifiers, measurements, timestamps, statistics, and chart labels, with DejaVu Sans for explanatory paragraphs. These fonts ship with the local Matplotlib installation and are embedded by the PDF exporters; report generation does not fetch fonts from the network.
