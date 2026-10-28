import base64
import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import numpy as np
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "isleri_logo.jpg"

# Store writable user data outside the installation directory.
APP_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "CerePhyte"
    / "state"
)
CSV_PATH = APP_DATA_DIR / "cerephyte_history.csv"
CONFIG_PATH = APP_DATA_DIR / "dashboard_config.json"
CSV_COLUMNS = ["captured_at", "sample", "mux1_channel", "mux2_channel", "voltage", "bat", "curr", "t2", "t3", "age_ms"]
DEFAULT_API = "http://127.0.0.1:8000/telemetry"
FASTAPI_BASE = "http://127.0.0.1:8000"
REFRESH_OPTIONS = [250, 350, 500, 750, 1000, 10000, 600000]
HISTORY_OPTIONS = [10, 30, 60, 120, 300, 600, 3600]
MAX_HISTORY_ROWS = 10000
MAX_ANALYSIS_SAMPLES = 3000
CHART_REFRESH_SECONDS = 2
THEME_OPTIONS = ("CerePhyte Blue", "ISLERI Gradient")
CHART_SERIES = {
    "ADS1115 Voltage": {"column": "voltage", "unit": "V", "color": "#55d4e6"},
    "Battery Voltage": {"column": "bat", "unit": "V", "color": "#6296fa"},
    "Current Consumption": {"column": "curr", "unit": "mA", "color": "#9b84ff"},
    "Signal Strength (10-sample RMS)": {
        "column": "signal_strength",
        "unit": "V RMS",
        "color": "#45d6bd",
    },
}
CHART_MODES = (
    "Line",
    "Smoothed Trend",
    "Time-Amplitude Heatmap",
    "Distribution",
    "Frequency Spectrum (FFT)",
)
FILTER_OPTIONS = (
    "Raw (unfiltered)",
    "FFT low-pass",
    "FFT high-pass",
    "FFT band-pass",
    "Butterworth low-pass",
    "Butterworth high-pass",
    "Butterworth band-pass",
    "Wavelet denoising",
)
DEFAULT_SETTINGS = {
    "background_theme": "CerePhyte Blue",
    "refresh_ms": 350,
    "history_seconds": 60,
    "sidebar_mux1": 0,
    "sidebar_mux2": 0,
    "chart_series": "ADS1115 Voltage",
    "chart_mode": "Line",
    "chart_filter": "Raw (unfiltered)",
    "filter_cutoff_hz": "0.5",
    "filter_low_hz": "0.2",
    "filter_high_hz": "1.0",
}

st.set_page_config(
    page_title="CerePhyte | Live Instrumentation",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_DATA_URI = "data:image/jpeg;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
show_startup_splash = not st.session_state.get("startup_intro_shown", False)
startup_splash = st.empty() if show_startup_splash else None
if startup_splash is not None:
    startup_splash.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{ background: #07101f; }}
[data-testid="stHeader"] {{ background: transparent; }}
.startup-splash {{
  position: fixed; inset: 0; z-index: 999999; display: grid; place-items: center;
  overflow: hidden; isolation: isolate; background: #07101f;
}}
.startup-splash::before, .startup-splash::after {{
  content: ""; position: absolute; inset: -35%; z-index: 0; pointer-events: none;
}}
.startup-splash::before {{
  background:
    radial-gradient(ellipse at 18% 44%, rgba(72, 81, 212, .24), transparent 38%),
    radial-gradient(ellipse at 74% 35%, rgba(37, 112, 190, .28), transparent 40%),
    radial-gradient(ellipse at 68% 80%, rgba(28, 155, 175, .22), transparent 42%),
    radial-gradient(ellipse at 42% 60%, rgba(34, 81, 155, .25), transparent 46%);
  background-size: 145% 145%; filter: blur(28px);
  animation: isleri-aurora-drift 16s ease-in-out infinite alternate;
}}
.startup-splash::after {{
  background: linear-gradient(112deg, transparent 30%, rgba(80, 148, 220, .10) 48%,
    rgba(72, 190, 207, .12) 54%, transparent 72%);
  transform: translateX(-45%) rotate(-8deg);
  animation: isleri-light-flow 9s ease-in-out infinite alternate;
}}
.startup-stars {{
  position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background-image:
    radial-gradient(1.5px 1.5px at 12% 22%, rgba(188, 219, 255, .75) 50%, transparent 100%),
    radial-gradient(1px 1px at 27% 76%, rgba(85, 212, 230, .7) 50%, transparent 100%),
    radial-gradient(2px 2px at 42% 18%, rgba(205, 221, 255, .6) 50%, transparent 100%),
    radial-gradient(1px 1px at 63% 31%, rgba(98, 150, 250, .75) 50%, transparent 100%),
    radial-gradient(1.5px 1.5px at 78% 72%, rgba(85, 212, 230, .65) 50%, transparent 100%),
    radial-gradient(1px 1px at 91% 43%, rgba(197, 221, 255, .7) 50%, transparent 100%),
    radial-gradient(1px 1px at 55% 88%, rgba(120, 151, 255, .7) 50%, transparent 100%);
  animation: isleri-star-twinkle 5.5s ease-in-out infinite alternate;
}}
.startup-content {{
  position: relative; z-index: 2;
  display: flex; flex-direction: column; align-items: center; gap: 1.35rem;
  padding: 2rem; text-align: center;
}}
.startup-logo {{ display: flex; align-items: center; gap: 1rem; color: #fff; }}
.startup-logo-frame {{
  position: relative; display: grid; place-items: center; isolation: isolate;
  width: 4.9rem; height: 4.9rem; overflow: hidden; border-radius: 1rem;
  background: #101c33; box-shadow: 0 0 25px rgba(55, 142, 194, .18);
}}
.startup-logo-frame::before {{
  content: ""; position: absolute; inset: -70%; z-index: -1;
  background: conic-gradient(from 0deg, transparent 0 68%, #55d4e6 76%,
    #6296fa 82%, #784bff 88%, transparent 96%);
  animation: isleri-logo-light-orbit 4.5s linear infinite;
}}
.startup-logo-frame img {{
  display: block; width: 4.35rem; height: 4.35rem; object-fit: contain;
  padding: .16rem; border-radius: .78rem; background: #fff;
}}
.startup-name {{ font-size: 1.6rem; font-weight: 800; letter-spacing: .3em; }}
.startup-caption {{ color: #d3e2f1; font-size: 1.05rem; letter-spacing: .035em; }}
@keyframes isleri-aurora-drift {{
  0% {{ transform: translate(-4%, 2%) scale(.96); background-position: 0% 40%; }}
  50% {{ transform: translate(2%, -3%) scale(1.02); background-position: 60% 100%; }}
  100% {{ transform: translate(4%, 1%) scale(1.05); background-position: 100% 20%; }}
}}
@keyframes isleri-light-flow {{
  from {{ transform: translateX(-48%) rotate(-8deg); opacity: .45; }}
  to {{ transform: translateX(48%) rotate(-8deg); opacity: .9; }}
}}
@keyframes isleri-logo-light-orbit {{
  to {{ transform: rotate(360deg); }}
}}
@keyframes isleri-star-twinkle {{
  from {{ opacity: .42; }}
  to {{ opacity: .95; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .startup-splash::before, .startup-splash::after, .startup-stars,
  .startup-logo-frame::before {{ animation: none; }}
}}
</style>
<div class="startup-splash">
  <div class="startup-stars" aria-hidden="true"></div>
  <div class="startup-content">
    <div class="startup-logo"><span class="startup-logo-frame"><img src="{LOGO_DATA_URI}" alt="ISLERI logo"></span><span class="startup-name">ISLERI</span></div>
    <div class="startup-caption">Initialising...</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Keep the first paint visible long enough to register before loading dashboard dependencies.
    time.sleep(3)
    st.session_state["startup_intro_shown"] = True

import pandas as pd
import plotly.graph_objects as go
import requests

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

st.markdown("""
<style>
:root { color-scheme: dark; }
.block-container { padding-top: 3.75rem; padding-bottom: 2rem; max-width: 1600px; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppViewContainer"] { background: var(--app-background); }
[data-testid="stSidebar"] {
  background: var(--sidebar-background);
  border-right: 1px solid var(--theme-border);
}
.hero {
  padding: 1.15rem 1.4rem; border: 1px solid var(--theme-border); border-radius: 18px;
  background: var(--hero-background); margin-bottom: 1rem;
  box-shadow: 0 12px 40px rgba(0, 0, 0, .14);
}
.brand-lockup { display: flex; align-items: center; gap: .55rem; margin-bottom: .45rem; }
.brand-mark {
  position: relative; isolation: isolate; overflow: hidden;
  display: inline-flex; align-items: center; justify-content: center;
  width: 2rem; height: 2rem; flex: none; padding: 2px;
  border-radius: .58rem; background: #101c33;
  filter: drop-shadow(0 0 10px rgba(98, 150, 250, .4));
}
.brand-mark::before {
  content: ""; position: absolute; inset: -75%; z-index: -1;
  background: conic-gradient(from 0deg, transparent 0 68%, #55d4e6 76%,
    #6296fa 82%, #784bff 88%, transparent 96%);
  animation: isleri-logo-light-orbit 4.5s linear infinite;
}
.brand-logo {
  position: relative; z-index: 1;
  display: block; width: 100%; height: 100%; object-fit: contain;
  border-radius: .4rem; background: #fff;
}
@keyframes isleri-logo-light-orbit { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .brand-mark::before { animation: none; }
}
.brand-name { color: #f2f7fc; font-size: .82rem; font-weight: 800; letter-spacing: .2em; }
.eyebrow { color: var(--theme-accent); font-size: .76rem; font-weight: 700; letter-spacing: .16em; }
.hero h1 { margin: .25rem 0 .15rem 0; font-size: 2rem; color: #f2f7fc; }
.hero p { margin: 0; color: #b6c8df; }
div[data-testid="stMetric"] {
  background: var(--panel-background); border: 1px solid var(--theme-border);
  border-radius: 14px; padding: .8rem 1rem;
}
div[data-testid="stMetricLabel"] { color: #b6c8df; }
div[data-testid="stMetricValue"] { color: #edf5ff; }
.panel {
  border: 1px solid var(--theme-border); border-radius: 15px; padding: 1rem 1.1rem;
  background: var(--panel-background); margin-bottom: .7rem;
}
.small-muted { color: #b6c8df; font-size: .86rem; }
.status-card {
  display: flex; flex-direction: column; gap: .2rem;
  border: 1px solid var(--theme-border); border-radius: 14px;
  padding: .8rem 1rem; margin: .75rem 0 1rem 0;
  background: var(--panel-background);
}
.status-kicker { color: var(--theme-accent); font-size: .7rem; text-transform: uppercase; letter-spacing: .16em; font-weight: 700; }
.status-value { font-size: 1.25rem; font-weight: 700; }
.status-good { border-color: rgba(87, 214, 170, 0.7); box-shadow: inset 0 0 0 1px rgba(87, 214, 170, 0.2); }
.status-bad { border-color: rgba(255, 153, 102, 0.7); box-shadow: inset 0 0 0 1px rgba(255, 153, 102, 0.2); }
.status-detail { color: #b6c8df; font-size: .9rem; }
.chart-loading {
  position: relative; display: grid; place-items: center; min-height: 420px;
  overflow: hidden; isolation: isolate; border: 1px solid rgba(98, 150, 250, .24);
  border-radius: 14px; background: linear-gradient(130deg, #08152a, #102744, #0b2637, #08152a);
  background-size: 250% 250%; animation: chart-gradient-drift 8s ease-in-out infinite alternate;
}
.chart-loading::before {
  content: ""; position: absolute; inset: -20%; z-index: -1;
  background:
    radial-gradient(ellipse at 22% 30%, rgba(98, 150, 250, .19), transparent 42%),
    radial-gradient(ellipse at 75% 68%, rgba(85, 212, 230, .17), transparent 44%);
  filter: blur(20px); animation: chart-glow-drift 6s ease-in-out infinite alternate;
}
.chart-loading-stars {
  position: absolute; inset: 0; pointer-events: none; opacity: .58;
  background-image:
    radial-gradient(1px 1px at 14% 25%, rgba(195, 220, 255, .8) 50%, transparent 100%),
    radial-gradient(1.5px 1.5px at 36% 72%, rgba(85, 212, 230, .7) 50%, transparent 100%),
    radial-gradient(1px 1px at 66% 28%, rgba(98, 150, 250, .8) 50%, transparent 100%),
    radial-gradient(1px 1px at 87% 68%, rgba(195, 220, 255, .7) 50%, transparent 100%);
  animation: chart-stars-twinkle 4s ease-in-out infinite alternate;
}
.chart-loading-content {
  display: flex; flex-direction: column; align-items: center; gap: .8rem;
  max-width: min(90%, 620px); padding: 1.5rem; text-align: center;
}
.chart-loading-brand { display: flex; align-items: center; gap: .55rem; }
.chart-loading-brand img {
  width: 2rem; height: 2rem; padding: 2px; border-radius: .55rem;
  background: #fff; box-shadow: 0 0 16px rgba(85, 212, 230, .22);
}
.chart-loading-brand strong { color: #f2f7fc; font-size: .85rem; letter-spacing: .2em; }
.chart-loading-title { color: #f2f7fc; font-size: 1.02rem; font-weight: 650; }
.chart-loading-detail { color: #b9c9de; font-size: .82rem; }
.chart-loading-track {
  width: min(250px, 70vw); height: 3px; margin-top: .3rem; overflow: hidden;
  border-radius: 99px; background: rgba(204, 222, 245, .12);
}
.chart-loading-track::after {
  content: ""; display: block; width: 42%; height: 100%; border-radius: inherit;
  background: linear-gradient(90deg, #784bff, #6296fa, #55d4e6);
  animation: chart-progress-flow 1.6s ease-in-out infinite;
}
@keyframes chart-gradient-drift {
  from { background-position: 0% 40%; }
  to { background-position: 100% 60%; }
}
@keyframes chart-glow-drift {
  from { transform: translate(-2%, 1%) scale(.96); }
  to { transform: translate(2%, -1%) scale(1.04); }
}
@keyframes chart-stars-twinkle { from { opacity: .32; } to { opacity: .76; } }
@keyframes chart-progress-flow {
  from { transform: translateX(-115%); }
  to { transform: translateX(250%); }
}
@media (prefers-reduced-motion: reduce) {
  .chart-loading, .chart-loading::before, .chart-loading-stars,
  .chart-loading-track::after { animation: none; }
}
</style>
""", unsafe_allow_html=True)


def load_dashboard_settings():
    settings = DEFAULT_SETTINGS.copy()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            stored_settings = json.load(config_file)
    except FileNotFoundError:
        return settings, None
    except (OSError, ValueError) as exc:
        return settings, f"Could not read dashboard settings; using defaults: {exc}"

    if not isinstance(stored_settings, dict):
        return settings, "Dashboard settings must contain a JSON object; using defaults."

    if stored_settings.get("background_theme") in THEME_OPTIONS:
        settings["background_theme"] = stored_settings["background_theme"]
    if stored_settings.get("refresh_ms") in REFRESH_OPTIONS:
        settings["refresh_ms"] = stored_settings["refresh_ms"]
    if stored_settings.get("history_seconds") in HISTORY_OPTIONS:
        settings["history_seconds"] = stored_settings["history_seconds"]
    if stored_settings.get("chart_series") in CHART_SERIES:
        settings["chart_series"] = stored_settings["chart_series"]
    if stored_settings.get("chart_mode") in CHART_MODES:
        settings["chart_mode"] = stored_settings["chart_mode"]
    if stored_settings.get("chart_filter") in FILTER_OPTIONS:
        settings["chart_filter"] = stored_settings["chart_filter"]
    for key in ("filter_cutoff_hz", "filter_low_hz", "filter_high_hz"):
        value = stored_settings.get(key)
        if isinstance(value, str):
            settings[key] = value
    for key in ("sidebar_mux1", "sidebar_mux2"):
        value = stored_settings.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 7:
            settings[key] = value
    return settings, None


def save_dashboard_settings(settings):
    temporary_path = CONFIG_PATH.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as config_file:
        json.dump(settings, config_file, indent=2)
        config_file.write("\n")
    temporary_path.replace(CONFIG_PATH)


def init_csv():
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def history_count():
    try:
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)
    except OSError:
        return 0


def get_latest_sample():
    api_url = st.session_state.get("api_url", DEFAULT_API).strip().rstrip("/")
    try:
        response = requests.get(api_url, timeout=1.2, headers={"Cache-Control": "no-cache"})
        response.raise_for_status()
        data = response.json()
        if not data.get("ok", False):
            return data, False, f"NodeMCU/API reports: {data.get('error', 'no valid data')}"
        required = ("sample", "mux1_channel", "mux2_channel", "voltage", "bat", "curr", "t2", "t3")
        missing = [key for key in required if key not in data]
        if missing:
            return data, False, "Missing fields: " + ", ".join(missing)
        return data, True, ""
    except requests.RequestException as exc:
        return None, False, f"Cannot reach FastAPI at {api_url}: {exc}"
    except (ValueError, TypeError) as exc:
        return None, False, f"Invalid JSON response: {exc}"


def save_if_new(data):
    """Append one row per changed Arduino sample number to the CSV archive."""
    init_csv()
    sample = int(data["sample"])
    last_sample = st.session_state.get("last_saved_sample")
    if last_sample is None:
        recent_row = read_recent_history(1)
        if not recent_row.empty:
            last_sample = int(recent_row["sample"].iloc[-1])
        st.session_state["last_saved_sample"] = last_sample
    if last_sample == sample:
        return False

    row = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "sample": sample,
        "mux1_channel": int(data["mux1_channel"]),
        "mux2_channel": int(data["mux2_channel"]),
        "voltage": float(data["voltage"]),
        "bat": float(data["bat"]),
        "curr": float(data["curr"]),
        "t2": int(data["t2"]),
        "t3": int(data["t3"]),
        "age_ms": int(data.get("age_ms") or 0),
    }
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writerow(row)
    st.session_state["last_saved_sample"] = sample
    return True


def read_recent_history(limit):
    """Read only the newest CSV rows so chart refresh cost stays bounded."""
    init_csv()
    if limit <= 0:
        return pd.DataFrame(columns=CSV_COLUMNS)
    header = ",".join(CSV_COLUMNS)
    chunk_size = 64 * 1024
    with CSV_PATH.open("rb") as history_file:
        history_file.seek(0, os.SEEK_END)
        position = history_file.tell()
        chunks = []
        newline_count = 0
        while position > 0 and newline_count <= limit + 1:
            read_size = min(chunk_size, position)
            position -= read_size
            history_file.seek(position)
            chunk = history_file.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")

    lines = b"".join(reversed(chunks)).splitlines()
    if position > 0 and lines:
        lines = lines[1:]
    try:
        if position == 0:
            csv_text = b"\n".join(lines).decode("utf-8-sig")
        else:
            data_lines = lines[-limit:]
            csv_text = header + "\n" + b"\n".join(data_lines).decode("utf-8")
        return pd.read_csv(io.StringIO(csv_text))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame(columns=CSV_COLUMNS)


@st.cache_data(ttl=1, max_entries=16, show_spinner=False)
def load_history(seconds=60, limit=MAX_ANALYSIS_SAMPLES):
    try:
        df = read_recent_history(limit)
    except OSError:
        return pd.DataFrame(columns=CSV_COLUMNS)
    if df.empty:
        return df

    for col in ("sample", "mux1_channel", "mux2_channel", "voltage", "bat", "curr", "t2", "t3", "age_ms"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["captured_at", "voltage"]).sort_values("captured_at").tail(int(limit))
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=int(seconds))
    return df[df["captured_at"] >= cutoff].copy()


def load_all_history(limit=MAX_HISTORY_ROWS):
    try:
        df = read_recent_history(limit)
    except OSError:
        return pd.DataFrame(columns=CSV_COLUMNS)
    if df.empty:
        return df
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    for col in ("sample", "mux1_channel", "mux2_channel", "voltage", "bat", "curr", "t2", "t3", "age_ms"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["captured_at"]).sort_values("captured_at").tail(int(limit))


def resample_uniform(times, values):
    time_values = pd.to_datetime(times, utc=True, errors="coerce")
    epoch_seconds = time_values.astype("int64").to_numpy(dtype=np.float64) / 1_000_000_000
    signal_values = np.asarray(values, dtype=np.float64)
    if len(epoch_seconds) != len(signal_values):
        return None, None, None, "Timestamp and signal sample counts do not match."
    valid = (~np.asarray(time_values.isna(), dtype=bool)) & np.isfinite(epoch_seconds) & np.isfinite(signal_values)
    epoch_seconds = epoch_seconds[valid]
    signal_values = signal_values[valid]
    if len(epoch_seconds) < 8:
        return None, None, None, "Filtering and FFT need at least 8 valid samples."

    order = np.argsort(epoch_seconds)
    epoch_seconds = epoch_seconds[order]
    signal_values = signal_values[order]
    epoch_seconds, unique_indices = np.unique(epoch_seconds, return_index=True)
    signal_values = signal_values[unique_indices]
    if len(epoch_seconds) < 8:
        return None, None, None, "Filtering and FFT need at least 8 unique timestamps."

    sample_interval = float(np.median(np.diff(epoch_seconds)))
    if not np.isfinite(sample_interval) or sample_interval <= 0:
        return None, None, None, "Could not determine a valid sample interval."

    sample_count = int(np.floor((epoch_seconds[-1] - epoch_seconds[0]) / sample_interval)) + 1
    if sample_count < 8:
        return None, None, None, "The selected time window is too short for filtering or FFT."
    if sample_count > MAX_ANALYSIS_SAMPLES:
        return None, None, None, (
            f"Resampling would exceed the {MAX_ANALYSIS_SAMPLES:,}-sample safety limit. "
            "Choose a shorter graph window or collect data at a steadier rate."
        )
    regular_seconds = epoch_seconds[0] + np.arange(sample_count) * sample_interval
    regular_values = np.interp(regular_seconds, epoch_seconds, signal_values)
    regular_times = pd.to_datetime(regular_seconds, unit="s", utc=True)
    return regular_times, regular_values, sample_interval, None


def apply_signal_filter(times, values, filter_name, cutoff_text, low_text, high_text):
    if filter_name == "Raw (unfiltered)":
        return times, np.asarray(values, dtype=np.float64), "Raw telemetry; no filter applied.", None

    uniform_times, uniform_values, sample_interval, error = resample_uniform(times, values)
    if error or uniform_times is None or uniform_values is None or sample_interval is None:
        return None, None, None, error or "Could not resample the selected signal."

    nyquist_hz = 0.5 / sample_interval
    is_bandpass = "band-pass" in filter_name
    is_lowpass = "low-pass" in filter_name
    is_highpass = "high-pass" in filter_name
    low_hz = None
    high_hz = None
    cutoff_hz = None

    if is_bandpass or is_lowpass or is_highpass:
        try:
            low_hz = float(low_text) if is_bandpass else None
            high_hz = float(high_text) if is_bandpass else None
            cutoff_hz = float(cutoff_text) if not is_bandpass else None
        except ValueError:
            return None, None, None, "Cutoff frequencies must be valid numbers in Hz."

        if is_bandpass:
            if low_hz is None or high_hz is None or not np.isfinite(low_hz) or not np.isfinite(high_hz):
                return None, None, None, "Cutoff frequencies must be finite numbers."
        elif cutoff_hz is None or not np.isfinite(cutoff_hz):
            return None, None, None, "Cutoff frequencies must be finite numbers."

        if is_bandpass and low_hz is not None and high_hz is not None and not (
            0 < low_hz < high_hz < nyquist_hz
        ):
            return None, None, None, (
                f"Band-pass requires 0 < low cutoff < high cutoff < Nyquist "
                f"({nyquist_hz:.4g} Hz for the current sample rate)."
            )
        if not is_bandpass and cutoff_hz is not None and not (0 < cutoff_hz < nyquist_hz):
            return None, None, None, (
                f"Cutoff must be greater than 0 and below Nyquist ({nyquist_hz:.4g} Hz)."
            )

    if filter_name.startswith("FFT "):
        frequencies = np.fft.rfftfreq(len(uniform_values), d=sample_interval)
        spectrum = np.fft.rfft(uniform_values)
        if is_bandpass:
            if low_hz is None or high_hz is None:
                return None, None, None, "Band-pass cutoff frequencies are required."
            keep = (frequencies >= low_hz) & (frequencies <= high_hz)
        elif is_lowpass or is_highpass:
            if cutoff_hz is None:
                return None, None, None, "A cutoff frequency is required."
            if is_lowpass:
                keep = frequencies <= cutoff_hz
            else:
                keep = frequencies >= cutoff_hz
        else:
            return None, None, None, f"Unsupported filter option: {filter_name}"
        filtered_values = np.fft.irfft(spectrum * keep, n=len(uniform_values))
        note = f"{filter_name} applied; Nyquist frequency is {nyquist_hz:.4g} Hz."
        return uniform_times, filtered_values, note, None

    if filter_name.startswith("Butterworth "):
        try:
            from scipy.signal import butter, sosfiltfilt
        except ImportError:
            return None, None, None, "Butterworth filtering requires SciPy. Install the updated requirements."

        if is_bandpass:
            critical_frequency = (low_hz, high_hz)
            filter_type = "bandpass"
        elif is_lowpass:
            critical_frequency = cutoff_hz
            filter_type = "lowpass"
        else:
            critical_frequency = cutoff_hz
            filter_type = "highpass"
        try:
            sections = butter(
                4,
                critical_frequency,
                btype=filter_type,
                fs=1 / sample_interval,
                output="sos",
            )
            filtered_values = sosfiltfilt(sections, uniform_values)
        except (ValueError, FloatingPointError) as exc:
            return None, None, None, f"Butterworth filter could not be applied: {exc}"
        note = f"Fourth-order Butterworth {filter_type} applied; Nyquist is {nyquist_hz:.4g} Hz."
        return uniform_times, filtered_values, note, None

    if filter_name == "Wavelet denoising":
        try:
            import pywt
        except ImportError:
            return None, None, None, "Wavelet denoising requires PyWavelets. Install the updated requirements."

        wavelet = pywt.Wavelet("db4")
        level = min(4, pywt.dwt_max_level(len(uniform_values), wavelet.dec_len))
        if level < 1:
            return None, None, None, "The selected time window is too short for wavelet denoising."
        try:
            coefficients = pywt.wavedec(uniform_values, wavelet, mode="symmetric", level=level)
            finest_detail = coefficients[-1]
            noise_sigma = np.median(np.abs(finest_detail - np.median(finest_detail))) / 0.6745
            threshold = noise_sigma * np.sqrt(2 * np.log(len(uniform_values)))
            denoised_coefficients = [coefficients[0]] + [
                pywt.threshold(detail, threshold, mode="soft") for detail in coefficients[1:]
            ]
            filtered_values = pywt.waverec(denoised_coefficients, wavelet, mode="symmetric")
        except (ValueError, FloatingPointError) as exc:
            return None, None, None, f"Wavelet denoising could not be applied: {exc}"
        note = f"Daubechies-4 wavelet denoising applied at level {level}."
        return uniform_times, filtered_values[:len(uniform_values)], note, None

    return None, None, None, f"Unsupported filter option: {filter_name}"


@st.cache_data(ttl=3, max_entries=16, show_spinner=False)
def make_telemetry_chart(
    df,
    series_name,
    chart_mode,
    filter_name,
    cutoff_text,
    low_text,
    high_text,
):
    series_config = CHART_SERIES[series_name]
    signal = pd.to_numeric(df.get(series_config["column"]), errors="coerce")
    signal_note = None
    if series_config["column"] == "signal_strength":
        voltage = pd.to_numeric(df.get("voltage"), errors="coerce")
        baseline = voltage.rolling(window=10, min_periods=2).mean()
        signal = (voltage - baseline).pow(2).rolling(window=10, min_periods=2).mean().pow(0.5)
        signal_note = "Derived as rolling 10-sample RMS deviation from ADS1115 voltage; not a separate sensor field."

    plot_data = pd.DataFrame({
        "captured_at": df.get("captured_at"),
        "value": signal,
    }).dropna().sort_values("captured_at").tail(MAX_ANALYSIS_SAMPLES)
    times, values, filter_note, filter_error = apply_signal_filter(
        plot_data["captured_at"],
        plot_data["value"],
        filter_name,
        cutoff_text,
        low_text,
        high_text,
    )
    fig = go.Figure()
    value_label = series_config["unit"]
    title = series_name

    if filter_error:
        fig.add_annotation(
            text=filter_error,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(color="#ffb38a", size=13),
        )
    elif times is None or values is None or len(values) == 0:
        fig.add_annotation(
            text="No valid samples in the selected time window.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(color="#b7c7d9", size=13),
        )
    elif chart_mode == "Line":
        fig.add_trace(go.Scattergl(
            x=times,
            y=values,
            name=title,
            mode="lines",
            line=dict(width=2, color=series_config["color"]),
            hovertemplate="%{x|%H:%M:%S.%L}<br>%{y:.5g} " + value_label + "<extra></extra>",
        ))
    elif chart_mode == "Smoothed Trend":
        smoothed = pd.Series(values).rolling(window=9, min_periods=1, center=True).mean()
        fig.add_trace(go.Scattergl(
            x=times,
            y=values,
            name="Filtered samples",
            mode="lines",
            line=dict(width=1, color=series_config["color"]),
            opacity=0.35,
        ))
        fig.add_trace(go.Scattergl(
            x=times,
            y=smoothed,
            name="9-sample moving average",
            mode="lines",
            line=dict(width=3, color="#55d4e6"),
        ))
    elif chart_mode == "Time-Amplitude Heatmap":
        epoch_seconds = pd.to_datetime(times, utc=True).astype("int64").to_numpy(dtype=np.float64) / 1_000_000_000
        relative_seconds = epoch_seconds - epoch_seconds[0]
        time_bins = min(48, max(1, len(values) // 3))
        value_bins = min(32, max(4, int(np.sqrt(len(values)))))
        density, time_edges, value_edges = np.histogram2d(
            relative_seconds,
            values,
            bins=(time_bins, value_bins),
        )
        time_centers = (time_edges[:-1] + time_edges[1:]) / 2
        time_origin = pd.to_datetime(epoch_seconds[0], unit="s", utc=True)
        heatmap_times = time_origin + pd.to_timedelta(time_centers, unit="s")
        value_centers = (value_edges[:-1] + value_edges[1:]) / 2
        fig.add_trace(go.Heatmap(
            x=heatmap_times,
            y=value_centers,
            z=density.T,
            colorscale="Viridis",
            colorbar=dict(title="Sample<br>density"),
            hovertemplate="%{x|%H:%M:%S}<br>%{y:.5g} " + value_label + "<br>Count: %{z}<extra></extra>",
        ))
    elif chart_mode == "Distribution":
        fig.add_trace(go.Histogram(
            x=values,
            nbinsx=min(50, max(10, int(np.sqrt(len(values)) * 2))),
            name=title,
            marker_color=series_config["color"],
            opacity=0.85,
            hovertemplate="%{x:.5g} " + value_label + "<br>Count: %{y}<extra></extra>",
        ))
    elif chart_mode == "Frequency Spectrum (FFT)":
        _, spectrum_values, sample_interval, spectrum_error = resample_uniform(times, values)
        if spectrum_error:
            fig.add_annotation(
                text=spectrum_error,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color="#ffb38a", size=13),
            )
        elif spectrum_values is None or sample_interval is None:
            fig.add_annotation(
                text="Could not calculate the frequency spectrum from the selected samples.",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color="#ffb38a", size=13),
            )
        else:
            centered_values = spectrum_values - np.mean(spectrum_values)
            window = np.hanning(len(centered_values))
            amplitudes = np.abs(np.fft.rfft(centered_values * window)) * 2 / np.sum(window)
            frequencies = np.fft.rfftfreq(len(centered_values), d=sample_interval)
            if len(amplitudes) > 1 and len(centered_values) % 2 == 0:
                amplitudes[-1] *= 0.5
            fig.add_trace(go.Scattergl(
                x=frequencies[1:],
                y=amplitudes[1:],
                name="Single-sided amplitude spectrum",
                mode="lines",
                line=dict(width=2, color=series_config["color"]),
                hovertemplate="%{x:.4g} Hz<br>%{y:.5g} " + value_label + "<extra></extra>",
            ))
            title = "Frequency Spectrum · " + series_name
    else:
        raise ValueError(f"Unsupported chart mode: {chart_mode}")

    if signal_note:
        title += " · Derived"
    fig.update_layout(
        title=dict(text=title, x=0.02, font=dict(size=15)),
        height=420,
        margin=dict(l=12, r=18, t=48, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0c141e",
        font=dict(color="#b7c7d9", size=12),
        xaxis=dict(
            title="Frequency (Hz)" if chart_mode == "Frequency Spectrum (FFT)" else (
                f"Signal value ({value_label})" if chart_mode == "Distribution" else "Time"
            ),
            showgrid=True,
            gridcolor="#1c2a3a",
            zeroline=False,
        ),
        yaxis=dict(
            title="Amplitude (" + value_label + ")" if chart_mode == "Frequency Spectrum (FFT)" else (
                "Sample count" if chart_mode == "Distribution" else f"Signal value ({value_label})"
            ),
            showgrid=True,
            gridcolor="#1c2a3a",
            zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        hovermode="x unified" if chart_mode in ("Line", "Smoothed Trend") else "closest",
    )
    notes = [note for note in (signal_note, filter_note) if note]
    if chart_mode == "Frequency Spectrum (FFT)" and not filter_error:
        notes.append("FFT uses median-interval linear resampling; frequency resolution is limited by the dashboard's telemetry sampling rate.")
    return fig, " ".join(notes), filter_error


init_csv()
saved_settings, settings_warning = load_dashboard_settings()
for setting_name, setting_value in saved_settings.items():
    st.session_state.setdefault(setting_name, setting_value)

with st.sidebar:
    st.markdown("## ⚙️ Acquisition")
    background_theme = st.radio(
        "Dashboard background",
        THEME_OPTIONS,
        key="background_theme",
    )
    api_url = st.text_input("FastAPI telemetry URL", value=st.session_state.get("api_url", DEFAULT_API))
    st.session_state["api_url"] = api_url
    
    refresh_ms = st.select_slider(
        "Dashboard refresh",
        options=REFRESH_OPTIONS,
        format_func=lambda x: f"{x} ms",
        key="refresh_ms",
    )
    
    history_seconds = st.select_slider(
        "Graph time window",
        options=HISTORY_OPTIONS,
        format_func=lambda x: f"{x} seconds" if x < 60 else f"{x // 60} min" if x % 60 == 0 else f"{x} seconds",
        key="history_seconds",
    )

    st.divider()
    st.markdown("### 📈 Signal Analysis")
    chart_series = st.selectbox(
        "Signal to display",
        tuple(CHART_SERIES),
        key="chart_series",
    )
    chart_mode = st.selectbox(
        "Scientific view",
        CHART_MODES,
        key="chart_mode",
    )
    chart_filter = st.selectbox(
        "Signal filter",
        FILTER_OPTIONS,
        key="chart_filter",
    )
    if "band-pass" in chart_filter:
        filter_low_hz = st.text_input("Lower cutoff (Hz)", key="filter_low_hz")
        filter_high_hz = st.text_input("Upper cutoff (Hz)", key="filter_high_hz")
        filter_cutoff_hz = st.session_state["filter_cutoff_hz"]
    elif "low-pass" in chart_filter or "high-pass" in chart_filter:
        filter_cutoff_hz = st.text_input("Cutoff frequency (Hz)", key="filter_cutoff_hz")
        filter_low_hz = st.session_state["filter_low_hz"]
        filter_high_hz = st.session_state["filter_high_hz"]
    else:
        filter_cutoff_hz = st.session_state["filter_cutoff_hz"]
        filter_low_hz = st.session_state["filter_low_hz"]
        filter_high_hz = st.session_state["filter_high_hz"]
    if chart_series == "Signal Strength (10-sample RMS)":
        st.caption("Derived from ADS1115 voltage variation; not a separate sensor measurement.")

    st.divider()
    st.markdown("### 🎛️ Dual-MUX Control")
    
    m1_ch = st.selectbox("MUX 1 Channel", list(range(8)), key="sidebar_mux1")
    if st.button("Set MUX 1 Channel", use_container_width=True):
        try:
            res = requests.get(f"{FASTAPI_BASE}/api/mux1", params={"channel": m1_ch}, timeout=1.5)
            if res.status_code == 200:
                st.success(f"MUX 1 set to Channel {m1_ch}")
            else:
                st.error("Failed to set MUX 1")
        except Exception as e:
            st.error(f"Connection error: {e}")

    m2_ch = st.selectbox("MUX 2 Channel", list(range(8)), key="sidebar_mux2")
    if st.button("Set MUX 2 Channel", use_container_width=True):
        try:
            res = requests.get(f"{FASTAPI_BASE}/api/mux2", params={"channel": m2_ch}, timeout=1.5)
            if res.status_code == 200:
                st.success(f"MUX 2 set to Channel {m2_ch}")
            else:
                st.error("Failed to set MUX 2")
        except Exception as e:
            st.error(f"Connection error: {e}")

    st.divider()
    st.markdown("### 💾 History")
    count = history_count()
    st.caption(f"{count:,} saved samples in local CSV history.")
    if st.button("Clear saved history", type="secondary", use_container_width=True):
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_COLUMNS).writeheader()
        st.session_state.pop("last_saved_sample", None)
        st.rerun()
    st.caption("History is stored on this computer in `cerephyte_history.csv`.")

try:
    save_dashboard_settings({name: st.session_state[name] for name in DEFAULT_SETTINGS})
except OSError as exc:
    st.error(f"Could not save dashboard settings: {exc}")
if settings_warning:
    st.warning(settings_warning)

theme_styles = {
    "CerePhyte Blue": """
      :root {
        --app-background: radial-gradient(ellipse at 82% 12%, rgba(0, 153, 255, .25), transparent 38%),
          linear-gradient(135deg, #061735 0%, #074b91 52%, #071d4b 100%);
        --sidebar-background: linear-gradient(180deg, #07376e, #082755 72%, #071d43);
        --hero-background: linear-gradient(120deg, rgba(7, 45, 93, .92), rgba(6, 25, 60, .92));
        --panel-background: rgba(6, 24, 57, .78);
        --theme-border: rgba(100, 175, 255, .25);
        --theme-accent: #45dbea;
      }
    """,
    "ISLERI Gradient": """
      :root {
        --app-background: radial-gradient(ellipse at 12% 10%, rgba(120, 75, 255, .32), transparent 36%),
          radial-gradient(ellipse at 88% 82%, rgba(85, 212, 230, .25), transparent 38%),
          linear-gradient(115deg, #171333 0%, #20234c 48%, #102e43 100%);
        --sidebar-background: linear-gradient(180deg, rgba(22, 21, 53, .98), rgba(11, 33, 54, .98));
        --hero-background: linear-gradient(110deg, rgba(120, 75, 255, .20), rgba(98, 150, 250, .16), rgba(85, 212, 230, .16));
        --panel-background: rgba(13, 19, 42, .78);
        --theme-border: rgba(148, 166, 255, .28);
        --theme-accent: #79d8ec;
      }
    """,
}
st.markdown(f"<style>{theme_styles[background_theme]}</style>", unsafe_allow_html=True)

st.markdown(f"""
<div class="hero">
  <div class="brand-lockup"><span class="brand-mark"><img class="brand-logo" src="{LOGO_DATA_URI}" alt="ISLERI logo"></span><span class="brand-name">ISLERI</span></div>
  <div class="eyebrow">ISLERI · BIOSIGNAL INSTRUMENTATION</div>
  <h1>CerePhyte <span style="color:#71dfbd">/</span> Live Console</h1>
  <p>Rev:5 · Local telemetry · Independent Dual-MUX monitoring with persistent history</p>
</div>
""", unsafe_allow_html=True)

def chart_calculation_status(mode, signal_filter):
    operations = []
    if "Wavelet" in signal_filter:
        title = "Denoising signal"
        operations.append("Applying Daubechies-4 wavelet thresholding.")
    elif "FFT" in signal_filter:
        title = "Filtering in frequency domain"
        operations.append(f"Applying the selected {signal_filter} filter.")
    elif "Butterworth" in signal_filter:
        title = "Applying Butterworth filter"
        operations.append(f"Filtering with the selected {signal_filter} cutoff.")
    else:
        title = "Preparing raw signal chart"

    mode_operations = {
        "Frequency Spectrum (FFT)": "Uniformly resampling, windowing, and transforming the signal with an FFT.",
        "Time-Amplitude Heatmap": "Calculating time-amplitude density bins.",
        "Smoothed Trend": "Calculating a rolling trend across the selected samples.",
        "Distribution": "Building the selected signal's value distribution.",
        "Line": "Loading and plotting the selected telemetry samples.",
    }
    if signal_filter == "Raw (unfiltered)":
        title = {
            "Frequency Spectrum (FFT)": "Calculating FFT spectrum",
            "Time-Amplitude Heatmap": "Building signal heatmap",
            "Smoothed Trend": "Smoothing signal trend",
            "Distribution": "Calculating value distribution",
            "Line": "Preparing raw signal chart",
        }.get(mode, "Preparing signal chart")
    operations.append(mode_operations.get(mode, "Loading and plotting the selected telemetry samples."))
    return title, " ".join(operations)


@st.fragment(run_every=f"{CHART_REFRESH_SECONDS}s")
def chart_panel():
    st.markdown(f"### {chart_series} · {chart_mode}")
    loader = st.empty()
    loading_title, loading_detail = chart_calculation_status(chart_mode, chart_filter)
    loader.markdown(
        f'<div class="chart-loading" role="status" aria-live="polite">'
        f'<div class="chart-loading-stars" aria-hidden="true"></div>'
        f'<div class="chart-loading-content">'
        f'<div class="chart-loading-brand"><img src="{LOGO_DATA_URI}" alt="">'
        f'<strong>ISLERI</strong></div>'
        f'<div class="chart-loading-title">{escape(loading_title)}</div>'
        f'<div class="chart-loading-detail">{escape(loading_detail)}</div>'
        f'<div class="chart-loading-track" aria-hidden="true"></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    try:
        df = load_history(history_seconds)
        chart, chart_note, chart_error = make_telemetry_chart(
            df,
            chart_series,
            chart_mode,
            chart_filter,
            filter_cutoff_hz,
            filter_low_hz,
            filter_high_hz,
        )
        st.caption(
            f"Showing the last {history_seconds} seconds · {len(df):,} saved points · "
            "timestamps normalized to UTC"
        )
        if chart_note:
            st.caption(chart_note)
        if chart_error:
            st.warning(chart_error)
        st.plotly_chart(chart, use_container_width=True, config={
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        }, key=f"telemetry_chart_{chart_series}_{chart_mode}_{chart_filter}")
    except (ValueError, FloatingPointError, RuntimeError, MemoryError) as exc:
        st.error(f"Chart calculation stopped safely: {exc}")
    finally:
        loader.empty()


@st.fragment(run_every=f"{refresh_ms}ms")
def live_panel():
    data, good, error = get_latest_sample()
    if startup_splash is not None:
        startup_splash.empty()

    if good and data is not None:
        current_draw = float(data.get("curr", 0.0))
        status_text = "System online"
        status_detail = (
            f"Live telemetry · Sample #{int(data['sample']):,} · "
            f"Battery draw {current_draw:.3f} ma · Packet age {int(data.get('age_ms') or 0):,} ms"
        )
        status_class = "status-good"
        try:
            save_if_new(data)
        except OSError as exc:
            st.error(f"Could not save history: {exc}")

        st.markdown(
            f'<div class="status-card {status_class}"><div class="status-kicker">Current status</div>'
            f'<div class="status-value">{escape(status_text)}</div>'
            f'<div class="status-detail">{escape(status_detail)}</div></div>',
            unsafe_allow_html=True,
        )
        st.success("LIVE · FastAPI connected · Newest complete telemetry snapshot")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("MUX 1 Ch", int(data["mux1_channel"]))
        c2.metric("MUX 2 Ch", int(data["mux2_channel"]))
        c3.metric("ADS1115 Voltage", f"{float(data['voltage']):.3f} V")
        c4.metric("Battery", f"{float(data['bat']):.2f} V")
        c5.metric("Sample counter", f"{int(data['sample']):,}")

        c6, c7, c8, c9 = st.columns(4)
        c6.metric("Battery current", f"{current_draw:.3f} ma")
        c7.metric("Touch T2", "HIGH" if int(data["t2"]) else "LOW")
        c8.metric("Touch T3 / LED", "HIGH · LED ON" if int(data["t3"]) else "LOW · LED OFF")
        age = data.get("age_ms")
        c9.metric("Packet age", f"{int(age)} ms" if age is not None else "—")

        with st.expander("Latest JSON payload"):
            st.json(data)
    else:
        status_text = "System offline"
        status_detail = error or "No live telemetry available"
        status_class = "status-bad"
        st.markdown(
            f'<div class="status-card {status_class}"><div class="status-kicker">Current status</div>'
            f'<div class="status-value">{escape(status_text)}</div>'
            f'<div class="status-detail">{escape(status_detail)}</div></div>',
            unsafe_allow_html=True,
        )
        st.error("NO LIVE DATA")
        st.warning(error)
        st.info("Check that FastAPI is running, that its telemetry endpoint returns `ok: true`, and that the laptop can reach the NodeMCU.")
        st.code(f"FastAPI URL: {api_url}")

live_panel()
chart_panel()

st.divider()
st.markdown("### Recorded history")
all_df = load_all_history(10000)

if all_df.empty:
    st.caption("No samples saved yet. Keep the dashboard open while CerePhyte is running.")
else:
    all_df = all_df.sort_values("captured_at")
    st.caption(f"Local CSV archive contains {len(all_df):,} most recent samples.")
    csv_export = all_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export history as CSV",
        data=csv_export,
        file_name=f"cerephyte_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
    display_df = all_df.tail(20).iloc[::-1].copy()
    display_df["captured_at"] = display_df["captured_at"].dt.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

st.caption("CerePhyte is a prototype instrument. Verify calibration and signal integrity before interpreting measurements.")