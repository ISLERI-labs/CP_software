# Software reference

## Components and data flow

The application consists of two Python processes:

1. **FastAPI backend (`CerePhyte_Dashboard/main.py`)** polls the NodeMCU at `http://192.168.4.1/api/data` every 200 ms and keeps the newest response in memory.
2. **Streamlit dashboard (`CerePhyte_Dashboard/app.py`)** polls the backend's `/telemetry` endpoint, renders the current snapshot, and records changed sample counters to a local CSV file.

The backend does not persist samples. The dashboard's local CSV is the only history store in this implementation.

## API reference

The API listens on port 8000 when started using the included launcher.

### `GET /telemetry`

Returns the latest JSON payload received from the NodeMCU. While waiting for a device response or when the NodeMCU is unavailable, it returns a status object such as:

```json
{"ok": false, "error": "NodeMCU unavailable"}
```

For live dashboard display, a successful payload must contain:

| Field | Use in dashboard |
| --- | --- |
| `ok` | Indicates the snapshot is valid. |
| `sample` | Sample counter and CSV de-duplication key. |
| `mux1_channel`, `mux2_channel` | Current MUX channel indicators. |
| `voltage` | ADS1115 A0 voltage, plotted in volts. |
| `bat`, `curr` | Battery and current readings. |
| `t2`, `t3` | Touch/LED state indicators. |
| `age_ms` | Optional packet age indicator; saved as zero if absent. |

The backend passes through the NodeMCU response without transforming its fields.

### `GET /api/mux1?channel={channel}` and `GET /api/mux2?channel={channel}`

Set the requested MUX channel by forwarding the request to the corresponding NodeMCU endpoint. `channel` is required and must be an integer from 0 through 7. A failed backend-to-device request returns HTTP 503.

## Dashboard behavior

- The sidebar refresh selector supports 250, 350, 500, 750, and 1000 ms; the default is 350 ms.
- The graph window can be set to 10, 30, 60, 120, 300, 600, or 3,600 seconds; the default is 60 seconds.
- The live panel displays MUX channels, ADS1115 voltage, battery voltage, sample counter, T2/T3 state, packet age, and the latest JSON payload.
- The chart independently refreshes every two seconds, separate from the live telemetry panel.
- Available series are ADS1115 voltage, battery voltage, current consumption, and signal strength derived as a rolling 10-sample RMS deviation of ADS1115 voltage.
- Available chart modes are line, smoothed trend, time-amplitude heatmap, value distribution, and frequency spectrum (FFT).
- Filters include raw (unfiltered), FFT low/high/band-pass, fourth-order Butterworth low/high/band-pass, and Daubechies-4 wavelet denoising. Filter cutoffs are entered in Hz and must be below the estimated Nyquist frequency; band-pass requires the low cutoff to be less than the high cutoff.
- The chart area shows an animated ISLERI-branded loading panel with status text describing the current calculation. It clears when rendering finishes and chart errors are reported in the panel.
- Recent chart history and analysis are bounded to 3,000 points. Resampling requests that would exceed the point limit are rejected rather than allocating an unbounded array.
- The history section displays up to the latest 10,000 saved rows and provides a CSV download. Reports accept CSV files with the complete CerePhyte column set. Chart calculations use at most the latest 3,000 rows. The PDFs use a technical, monospace-first layout; an aligned ISLERI logo; a restrained violet-to-cyan accent rule; report/source/UTC metadata; explicit filter names; and a closing calibration, experimental-conditions, and operator sign-off page.
- `CerePhyte_Dashboard/generate_scientific_report.py` uses ReportLab for paginated PDF layout and Matplotlib for charts to generate the standard full report suite from a CerePhyte CSV without running Streamlit. The existing suite retains one summary page, seven scientific chart pages (raw line, smoothed trend, raw and wavelet-denoised heatmaps, FFT, distribution, and wavelet-denoised line), and one notes/sign-off page. Daubechies-4 denoising uses level 4 and preserves the CSV's UTC time origin; recordings too short for level 4 are rejected with an explicit error. Run `python generate_scientific_report.py path/to/recording.csv`; `--output` and `--logo` customize the destination and logo file.
- Both PDF workflows use DejaVu Sans Mono for numerical and technical information and DejaVu Sans for explanatory copy. Fonts are sourced from the locally installed Matplotlib package and embedded into generated PDFs, so report creation does not require network font downloads.
- MUX controls expose channels 0 through 7.
- **Clear saved history** truncates the local CSV and writes its header again.
- The sidebar can start and stop a named recording CSV. New recordings use the same columns as the history archive and default to `%LOCALAPPDATA%\CerePhyte\state\recordings`; a custom folder path can be entered.
- **Generate report from a recording CSV** accepts file selection or drag-and-drop. Multiple chart configurations can repeat scientific views with different signals, filters, and cutoff values. The downloadable ISLERI-branded PDF includes recording timestamps, voltage summary statistics, and one page per chart.

The sidebar's telemetry URL customizes telemetry reads. MUX controls currently use the fixed FastAPI base URL `http://127.0.0.1:8000`.

The dashboard displays an ISLERI-branded startup screen on the first app load. Dashboard preferences are stored separately from measurement history in `%LOCALAPPDATA%\CerePhyte\state\dashboard_config.json` on Windows. Preferences include theme, refresh interval, graph window, MUX selections, chart series/mode/filter, and filter cutoffs.

## CSV history

On Windows, the application stores `cerephyte_history.csv` under `%LOCALAPPDATA%\CerePhyte\state\`. Columns are:

`captured_at`, `sample`, `mux1_channel`, `mux2_channel`, `voltage`, `bat`, `curr`, `t2`, `t3`, `age_ms`

`captured_at` is recorded as a UTC ISO-8601 timestamp. The dashboard appends a row only when the sample number differs from the last row in the file. Since the API exposes only the newest snapshot and the dashboard polls periodically, intermediate samples may be missed. This CSV is therefore not guaranteed to be a lossless acquisition log.

Named recordings use the same header and are created in `%LOCALAPPDATA%\CerePhyte\state\recordings` unless a different output folder is entered. Only the currently active recording receives new rows; stopping it leaves the CSV available for report generation.

The graph reads recent CSV rows and limits its working set to 3,000 rows. The history table and CSV download use at most the latest 10,000 rows.

## Dependencies

Dependencies and their minimum versions are listed in `CerePhyte_Dashboard/requirements.txt`: Streamlit, Plotly, pandas, NumPy, SciPy, PyWavelets, Matplotlib, ReportLab, requests, FastAPI, Uvicorn, and httpx. SciPy enables Butterworth filtering, PyWavelets enables wavelet denoising, Matplotlib renders charts and provides locally bundled embeddable DejaVu fonts, and ReportLab provides standalone report layout and PDF generation.
