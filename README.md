# CEREPHYTE Dashboard

A Streamlit dashboard scaffold for CEREPHYTE plant bioelectric data acquisition
and analysis. The current implementation provides a simulation workflow,
session recording and CSV export, and validated CSV import. It is intended for
research and learning and is not a medically validated diagnostic instrument.

## Run locally

Use Python 3.10 or newer:

```text
python -m venv .venv
```

Activate the virtual environment, then install the core dependencies and launch:

```text
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Modes and current limitations

- **SIMULATION** generates clearly labeled, unitless example values for eight
  channels. These are not plant measurements and do not validate hardware.
- **DEVICE** is an explicit placeholder. The authoritative firmware protocol,
  endpoint, and payload schema are not present in this repository. The app
  makes no device requests and never substitutes simulated data in this mode.
- **IMPORTED DATA** accepts CSV files with `timestamp_utc` and numeric `CH1`
  through `CH8` columns. `source_mode` is optional; absent provenance is labeled
  `IMPORTED DATA`.

Simulation monitoring refreshes on a software timer for demonstration purposes.
This refresh cadence is not the instrument's sampling rate. Timestamps are
stored in UTC; signal units are not defined. Recordings remain in the current
Streamlit session until it is reset or closed. Download recordings to retain
them outside the session.

AI assistance is not included or required. No data is sent to an external
service.

## CSV schema

CSV columns are ordered as `timestamp_utc`, `source_mode`, then `CH1` through
`CH8`. Timestamps are ISO 8601 UTC values. Each row's source is `SIMULATION`,
`DEVICE`, or `IMPORTED DATA`. Channel values have no specified units.

## Tests

Run the standard-library test suite from the repository root:

```text
python -m unittest discover -s tests
```
