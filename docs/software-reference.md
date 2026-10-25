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
- The graph window can be set to 10, 30, 60, 120, 300, or 600 seconds; the default is 60 seconds.
- The live panel displays MUX channels, ADS1115 voltage, battery voltage, sample counter, T2/T3 state, packet age, and the latest JSON payload.
- The live chart plots ADS1115 voltage against UTC capture time.
- The history section displays up to the latest 10,000 saved rows and provides a CSV download.
- MUX controls expose channels 0 through 7.
- **Clear saved history** truncates the local CSV and writes its header again.

The sidebar's telemetry URL customizes telemetry reads. MUX controls currently use the fixed FastAPI base URL `http://127.0.0.1:8000`.

## CSV history

The application creates `cerephyte_history.csv` beside `app.py` if it does not exist or is empty. Columns are:

`captured_at`, `sample`, `mux1_channel`, `mux2_channel`, `voltage`, `bat`, `curr`, `t2`, `t3`, `age_ms`

`captured_at` is recorded as a UTC ISO-8601 timestamp. The dashboard appends a row only when the sample number differs from the last row in the file. Since the API exposes only the newest snapshot and the dashboard polls periodically, intermediate samples may be missed. This CSV is therefore not guaranteed to be a lossless acquisition log.

The graph reads recent CSV rows and limits its working set to 3,000 rows. The history table and CSV download use at most the latest 10,000 rows.

## Dependencies

Dependencies and their minimum versions are listed in `CerePhyte_Dashboard/requirements.txt`: Streamlit, Plotly, pandas, requests, FastAPI, Uvicorn, and httpx.

