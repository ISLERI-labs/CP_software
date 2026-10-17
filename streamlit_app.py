"""Streamlit entry point for the CEREPHYTE data dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd
import streamlit as st

from cerephyte.data import (
    CHANNEL_COLUMNS,
    EXPORT_COLUMNS,
    SOURCE_COLUMN,
    TIMESTAMP_COLUMN,
    samples_to_csv,
    summarize_samples,
    validate_samples,
)
from cerephyte.simulation import generate_simulated_sample

MAX_LIVE_SAMPLES = 600


def initialize_session_state() -> None:
    defaults = {
        "monitoring_active": False,
        "live_samples": [],
        "sample_index": 0,
        "recordings": [],
        "active_recording_id": None,
        "last_source_mode": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def find_recording(recording_id: str) -> dict[str, object] | None:
    for recording in st.session_state.recordings:
        if recording["id"] == recording_id:
            return recording
    return None


def start_recording() -> None:
    recording_id = uuid4().hex
    st.session_state.recordings.append(
        {
            "id": recording_id,
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "samples": [],
        }
    )
    st.session_state.active_recording_id = recording_id


def stop_recording() -> None:
    recording = find_recording(st.session_state.active_recording_id)
    if recording is not None:
        recording["completed_at"] = datetime.now(timezone.utc)
    st.session_state.active_recording_id = None


def recording_frame(recording: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(recording["samples"], columns=EXPORT_COLUMNS)


def render_live_panel(source_mode: str, update_simulation: bool = False) -> None:
    st.subheader("Live monitor")

    if source_mode == "DEVICE":
        st.warning(
            "Device acquisition is not configured. The firmware protocol and endpoint "
            "are not available in this repository, so no device requests are made."
        )
        return

    if source_mode != "SIMULATION":
        st.info("Choose Simulation or Device to view the live monitor.")
        return

    if update_simulation and st.session_state.monitoring_active:
        sample = generate_simulated_sample(st.session_state.sample_index)
        st.session_state.sample_index += 1
        st.session_state.live_samples.append(sample)
        if len(st.session_state.live_samples) > MAX_LIVE_SAMPLES:
            del st.session_state.live_samples[:-MAX_LIVE_SAMPLES]

        active_recording_id = st.session_state.active_recording_id
        if active_recording_id is not None:
            recording = find_recording(active_recording_id)
            if recording is not None:
                recording["samples"].append(sample)

    samples = st.session_state.live_samples
    active_recording_id = st.session_state.active_recording_id
    active_recording = (
        find_recording(active_recording_id)
        if active_recording_id is not None
        else None
    )
    recording_count = len(active_recording["samples"]) if active_recording else 0

    status = "Monitoring" if st.session_state.monitoring_active else "Stopped"
    status_column, latest_column, recording_column = st.columns(3)
    status_column.metric("Simulation status", status)
    latest_value = samples[-1]["CH1"] if samples else None
    latest_column.metric(
        "Latest CH1 example value",
        f"{latest_value:.3f}" if latest_value is not None else "-",
    )
    recording_column.metric("Active recording samples", recording_count)

    st.caption(
        "Generated, unitless example values only, not plant measurements. "
        "The display refresh is a software-demo cadence, not the device sample rate. "
        "Timestamps use UTC."
    )

    if not samples:
        st.info("Start monitoring to generate example data.")
        return

    chart_data = pd.DataFrame(samples).set_index(TIMESTAMP_COLUMN)
    st.line_chart(chart_data.loc[:, CHANNEL_COLUMNS], height=320)


@st.fragment(run_every="1s")
def render_simulation_monitor() -> None:
    render_live_panel("SIMULATION", update_simulation=True)


def render_recordings() -> None:
    st.subheader("Simulation recordings")
    recordings = st.session_state.recordings
    if not recordings:
        st.info("No recording sessions yet. Start monitoring, then start a recording.")
        return

    labels = {
        recording["id"]: (
            f"{recording['started_at'].strftime('%Y-%m-%d %H:%M:%S UTC')} "
            f"({len(recording['samples'])} samples)"
        )
        for recording in recordings
    }
    recording_ids = list(labels)
    selected_id = st.selectbox(
        "Select a recording session",
        recording_ids,
        format_func=lambda recording_id: labels[recording_id],
    )
    selected = find_recording(selected_id)
    if selected is None:
        st.error("The selected recording session could not be found.")
        return

    samples = recording_frame(selected)
    if samples.empty:
        st.info("This session has no samples yet. Keep monitoring while it is recording.")
        return

    stats_column, export_column = st.columns([2, 1])
    with stats_column:
        st.dataframe(summarize_samples(samples), use_container_width=True)
    with export_column:
        st.download_button(
            "Download CSV",
            data=samples_to_csv(samples),
            file_name=f"cerephyte_recording_{selected_id[:8]}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    st.caption(
        "CSV columns: timestamp_utc (ISO 8601 UTC), source_mode, and CH1 through CH8. "
        "Channel units are unspecified."
    )


def render_imported_data() -> None:
    st.subheader("Import a recording")
    st.caption(
        "CSV files must include timestamp_utc and numeric CH1 through CH8 columns. "
        "An optional source_mode column is preserved; timestamps are normalized to UTC."
    )
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded_file is None:
        return

    try:
        imported = pd.read_csv(uploaded_file)
        samples = validate_samples(imported)
    except (pd.errors.ParserError, UnicodeDecodeError, OSError, ValueError) as error:
        st.error(f"Could not import this CSV: {error}")
        return

    sources = ", ".join(sorted(set(samples[SOURCE_COLUMN])))
    st.success(f"Loaded {len(samples)} rows. Original source label(s): {sources}.")
    st.line_chart(
        samples.set_index(TIMESTAMP_COLUMN).loc[:, CHANNEL_COLUMNS],
        height=320,
    )
    st.dataframe(summarize_samples(samples), use_container_width=True)
    st.download_button(
        "Download normalized CSV",
        data=samples_to_csv(samples),
        file_name="cerephyte_imported_data.csv",
        mime="text/csv",
    )


def main() -> None:
    st.set_page_config(
        page_title="CEREPHYTE Dashboard",
        layout="wide",
    )
    initialize_session_state()
    st.markdown(
        """
        <style>
        .stApp { background: #10151d; color: #e7edf5; }
        [data-testid="stSidebar"] { background: #151c26; }
        [data-testid="stMetric"] {
            background: #1a2430;
            border: 1px solid #293848;
            padding: 0.8rem;
            border-radius: 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    active_recording_id = st.session_state.active_recording_id
    st.title("CEREPHYTE")
    st.caption("Plant bioelectric signal acquisition and analysis dashboard")

    with st.sidebar:
        st.header("Data source")
        source_mode = st.radio(
            "Choose a mode",
            ("SIMULATION", "DEVICE", "IMPORTED DATA"),
            disabled=active_recording_id is not None,
        )
        if st.session_state.last_source_mode != source_mode:
            st.session_state.monitoring_active = False
            st.session_state.last_source_mode = source_mode
        if active_recording_id is not None:
            st.caption("Stop the active recording before changing data source.")

        st.divider()
        if source_mode == "SIMULATION":
            if st.session_state.monitoring_active:
                if st.button(
                    "Stop monitoring",
                    disabled=active_recording_id is not None,
                    use_container_width=True,
                ):
                    st.session_state.monitoring_active = False
            elif st.button("Start monitoring", use_container_width=True):
                st.session_state.monitoring_active = True

            if active_recording_id is None:
                if st.button(
                    "Start recording",
                    disabled=not st.session_state.monitoring_active,
                    use_container_width=True,
                ):
                    start_recording()
            elif st.button("Stop recording", use_container_width=True):
                stop_recording()

            if not st.session_state.monitoring_active:
                st.caption("Monitoring must be active before a recording can start.")
        elif source_mode == "DEVICE":
            st.caption("Device mode will not fall back to simulated values.")
        else:
            st.caption("Imported files remain separate from live acquisition.")

    if source_mode == "SIMULATION":
        st.info("SIMULATION: Generated example values; hardware acquisition is not used.")
    elif source_mode == "DEVICE":
        st.warning("DEVICE: Acquisition unavailable; protocol details are not configured.")
    else:
        st.info("IMPORTED DATA: Viewing a user-provided CSV file.")

    if source_mode == "SIMULATION":
        if st.session_state.monitoring_active:
            render_simulation_monitor()
        else:
            render_live_panel(source_mode)
        render_recordings()
    elif source_mode == "DEVICE":
        render_live_panel(source_mode)
    else:
        render_imported_data()


if __name__ == "__main__":
    main()
