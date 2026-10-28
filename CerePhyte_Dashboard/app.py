import base64
import csv
import json
import os
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "isleri_logo.jpg"
LOGO_DATA_URI = "data:image/jpeg;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")

# Store writable user data outside the installation directory.
APP_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "CerePhyte"
    / "state"
)
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

CSV_PATH = APP_DATA_DIR / "cerephyte_history.csv"
CONFIG_PATH = APP_DATA_DIR / "dashboard_config.json"
CSV_COLUMNS = ["captured_at", "sample", "mux1_channel", "mux2_channel", "voltage", "bat", "curr", "t2", "t3", "age_ms"]
DEFAULT_API = "http://127.0.0.1:8000/telemetry"
FASTAPI_BASE = "http://127.0.0.1:8000"
REFRESH_OPTIONS = [250, 350, 500, 750, 1000, 10000, 600000]
HISTORY_OPTIONS = [10, 30, 60, 120, 300, 600, 3600]
THEME_OPTIONS = ("CerePhyte Blue", "ISLERI Gradient")
DEFAULT_SETTINGS = {
    "background_theme": "CerePhyte Blue",
    "refresh_ms": 350,
    "history_seconds": 60,
    "sidebar_mux1": 0,
    "sidebar_mux2": 0,
}

st.set_page_config(
    page_title="CerePhyte | Live Instrumentation",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
  display: inline-flex; align-items: center; justify-content: center;
  width: 2rem; height: 2rem; flex: none;
  filter: drop-shadow(0 0 10px rgba(98, 150, 250, .4));
}
.brand-logo {
  display: block; width: 100%; height: 100%; object-fit: contain;
  padding: .12rem; border-radius: .45rem; background: #fff;
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
.loading-splash {
  position: fixed; inset: 0; z-index: 999999; display: grid; place-items: center;
  overflow: hidden; background: rgba(5, 10, 24, .96); backdrop-filter: blur(18px);
}
.loading-splash::before {
  content: ""; position: absolute; inset: -60%;
  background: linear-gradient(110deg, transparent 35%, rgba(120, 75, 255, .36) 48%,
    rgba(98, 150, 250, .42) 57%, rgba(85, 212, 230, .32) 66%, transparent 78%);
  background-size: 220% 100%; animation: brand-gradient-flow 3.4s ease-in-out infinite alternate;
}
.loading-content { position: relative; display: flex; flex-direction: column; align-items: center; gap: 1rem; }
.loading-logo { display: flex; align-items: center; gap: .75rem; color: #fff; }
.loading-logo .brand-mark { width: 3rem; height: 3rem; }
.loading-logo .brand-name { font-size: 1.25rem; letter-spacing: .28em; }
.loading-ring {
  width: 2rem; height: 2rem; border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, .18); border-top-color: #55d4e6;
  border-right-color: #784bff; animation: loader-spin .9s linear infinite;
}
.loading-caption { color: #c2cee2; font-size: .9rem; letter-spacing: .04em; }
@keyframes brand-gradient-flow {
  from { transform: translateX(-8%) rotate(-7deg); background-position: 0% 50%; }
  to { transform: translateX(8%) rotate(7deg); background-position: 100% 50%; }
}
@keyframes loader-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) {
  .loading-splash::before, .loading-ring { animation-duration: 8s; }
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
    try:
        with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
            rows = csv.DictReader(f)
            last_sample = None
            for row in rows:
                last_sample = row.get("sample")
        if last_sample is not None and last_sample != "" and int(last_sample) == sample:
            return False
    except (OSError, ValueError, csv.Error):
        pass

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
    return True


def load_history(seconds=60, limit=3000):
    init_csv()
    try:
        df = pd.read_csv(CSV_PATH)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
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


def load_all_history(limit=10000):
    init_csv()
    try:
        df = pd.read_csv(CSV_PATH)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=CSV_COLUMNS)
    if df.empty:
        return df
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    for col in ("sample", "mux1_channel", "mux2_channel", "voltage", "bat", "curr", "t2", "t3", "age_ms"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["captured_at"]).sort_values("captured_at").tail(int(limit))


def make_voltage_chart(df):
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(go.Scattergl(
            x=df["captured_at"], y=df["voltage"], name="ADS1115 A0 Voltage",
            mode="lines", line=dict(width=2, color="#55e6bd"),
            hovertemplate="%{x|%H:%M:%S.%L}<br>Voltage: %{y:.3f} V<extra></extra>",
        ))
    fig.update_layout(
        height=390, margin=dict(l=12, r=18, t=20, b=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0c141e",
        font=dict(color="#b7c7d9", size=12),
        xaxis=dict(title=None, showgrid=True, gridcolor="#1c2a3a", zeroline=False),
        yaxis=dict(title="Voltage (V)", showgrid=True, gridcolor="#1c2a3a", zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        hovermode="x unified",
    )
    return fig


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

st.session_state.setdefault("initial_loading", True)


@st.fragment(run_every=f"{refresh_ms}ms")
def live_panel():
    loading_screen = None
    if st.session_state["initial_loading"]:
        loading_screen = st.empty()
        loading_screen.markdown(f"""
        <div class="loading-splash">
          <div class="loading-content">
            <div class="loading-logo"><span class="brand-mark"><img class="brand-logo" src="{LOGO_DATA_URI}" alt="ISLERI logo"></span><span class="brand-name">ISLERI</span></div>
            <div class="loading-ring"></div>
            <div class="loading-caption">Connecting to your CerePhyte instrument</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    data, good, error = get_latest_sample()
    if loading_screen is not None:
        st.session_state["initial_loading"] = False
        loading_screen.empty()

    if good:
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

        df = load_history(history_seconds)
        st.markdown("### Live signal · ADS1115 A0 Voltage")
        st.caption(f"Showing the last {history_seconds} seconds · {len(df):,} saved points · timestamps normalized to UTC")
        st.plotly_chart(make_voltage_chart(df), use_container_width=True, config={
            "displaylogo": False,
            "scrollZoom": True,
            "responsive": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        }, key="voltage_live_chart")
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