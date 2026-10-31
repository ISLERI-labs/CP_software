"""Generate a complete CEREPHYTE signal-analysis PDF from a recording CSV.

Usage:
    python generate_scientific_report.py recording.csv
    python generate_scientific_report.py recording.csv --output report.pdf
    python generate_scientific_report.py recording.csv --logo path\\to\\logo.jpg
"""

import argparse
import io
import sys
from datetime import timezone
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd

CSV_COLUMNS = (
    "captured_at",
    "sample",
    "mux1_channel",
    "mux2_channel",
    "voltage",
    "bat",
    "curr",
    "t2",
    "t3",
    "age_ms",
)
CHART_SERIES = {
    "ADS1115 Voltage": {"column": "voltage", "unit": "V", "color": "#2563EB"},
}
CHART_MODES = (
    "Line",
    "Smoothed Trend",
    "Time-Amplitude Heatmap",
    "Distribution",
    "Frequency Spectrum (FFT)",
)
MAX_ANALYSIS_SAMPLES = 3000
NAVY = "#0F2B5C"
SIGNAL_BLUE = "#2563EB"
SUCCESS_GREEN = "#059669"
WARNING_AMBER = "#D97706"
CARD_BORDER = "#E2E8F0"
LOGO_PATH = Path(__file__).resolve().with_name("isleri_logo.jpg")


def load_recording(csv_path):
    """Load a CerePhyte-format CSV and normalize timestamp and signal columns."""
    try:
        dataframe = pd.read_csv(csv_path)
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read recording CSV {csv_path}: {exc}") from exc

    missing_columns = [column for column in CSV_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(
            "The input is not a CerePhyte recording CSV; missing columns: "
            + ", ".join(missing_columns)
        )
    if dataframe.empty:
        raise ValueError("The recording CSV has no samples.")

    dataframe = dataframe.copy()
    dataframe["captured_at"] = pd.to_datetime(
        dataframe["captured_at"], utc=True, errors="coerce",
    )
    for column in CSV_COLUMNS[1:]:
        dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
    dataframe = dataframe.dropna(subset=["captured_at", "voltage"])
    dataframe = dataframe.sort_values("captured_at").reset_index(drop=True)
    if dataframe.empty:
        raise ValueError("The CSV has no rows with both valid UTC timestamps and voltage values.")
    return dataframe


def resample_uniform(times, values):
    """Linearly resample a signal while preserving its original UTC time origin."""
    timestamps = pd.to_datetime(times, utc=True, errors="coerce")
    timestamps_ns = timestamps.array.as_unit("ns").asi8
    signal_values = np.asarray(values, dtype=np.float64)
    if len(timestamps_ns) != len(signal_values):
        return None, None, None, "Timestamp and signal sample counts do not match."

    valid = (~np.asarray(timestamps.isna(), dtype=bool)) & np.isfinite(signal_values)
    timestamps_ns = timestamps_ns[valid]
    signal_values = signal_values[valid]
    if len(timestamps_ns) < 8:
        return None, None, None, "Filtering and FFT need at least 8 valid samples."

    order = np.argsort(timestamps_ns)
    timestamps_ns = timestamps_ns[order]
    signal_values = signal_values[order]
    timestamps_ns, unique_indices = np.unique(timestamps_ns, return_index=True)
    signal_values = signal_values[unique_indices]
    if len(timestamps_ns) < 8:
        return None, None, None, "Filtering and FFT need at least 8 unique timestamps."

    origin_ns = timestamps_ns[0]
    relative_seconds = (timestamps_ns - origin_ns).astype(np.float64) / 1_000_000_000
    sample_interval = float(np.median(np.diff(relative_seconds)))
    if not np.isfinite(sample_interval) or sample_interval <= 0:
        return None, None, None, "Could not determine a valid sample interval."

    sample_count = int(np.floor(relative_seconds[-1] / sample_interval)) + 1
    if sample_count < 8:
        return None, None, None, "The selected time window is too short for filtering or FFT."
    if sample_count > MAX_ANALYSIS_SAMPLES:
        return None, None, None, (
            f"Resampling would exceed the {MAX_ANALYSIS_SAMPLES:,}-sample safety limit."
        )

    regular_seconds = np.arange(sample_count) * sample_interval
    regular_values = np.interp(regular_seconds, relative_seconds, signal_values)
    regular_times = pd.Timestamp(origin_ns, tz="UTC") + pd.to_timedelta(
        regular_seconds, unit="s",
    )
    return regular_times, regular_values, sample_interval, None


def apply_report_filter(times, values, filter_name, cutoff_text, low_text, high_text):
    """Apply the raw or Daubechies-4 denoising used in the default report suite."""
    signal_values = np.asarray(values, dtype=np.float64)
    if filter_name == "Raw (unfiltered)":
        return times, signal_values, "Raw telemetry; no filter applied.", None
    if filter_name != "Wavelet denoising":
        return None, None, None, f"Unsupported report filter: {filter_name}."

    uniform_times, uniform_values, _, error = resample_uniform(times, signal_values)
    if error or uniform_times is None or uniform_values is None:
        return None, None, None, error or "Could not resample the signal."

    try:
        import pywt
    except ImportError:
        return None, None, None, "Wavelet denoising requires PyWavelets; install project requirements."

    wavelet = pywt.Wavelet("db4")
    level = 4
    maximum_level = pywt.dwt_max_level(len(uniform_values), wavelet.dec_len)
    if maximum_level < level:
        return None, None, None, (
            "Level-4 Daubechies-4 denoising requires at least "
            f"{2 ** level * (wavelet.dec_len - 1)} uniformly resampled points; "
            f"this recording supports level {maximum_level}."
        )
    try:
        coefficients = pywt.wavedec(uniform_values, wavelet, mode="symmetric", level=level)
        finest_detail = coefficients[-1]
        noise_sigma = np.median(np.abs(finest_detail - np.median(finest_detail))) / 0.6745
        threshold = noise_sigma * np.sqrt(2 * np.log(len(uniform_values)))
        denoised = [coefficients[0]] + [
            pywt.threshold(detail, threshold, mode="soft")
            for detail in coefficients[1:]
        ]
        filtered_values = pywt.waverec(denoised, wavelet, mode="symmetric")
    except (ValueError, FloatingPointError) as exc:
        return None, None, None, f"Wavelet denoising failed: {exc}"

    note = f"Daubechies-4 wavelet denoising applied at level {level}."
    return uniform_times, filtered_values[:len(uniform_values)], note, None


def full_report_configs():
    """Return the standard publication report suite in display order."""
    defaults = {"series": "ADS1115 Voltage", "cutoff": "", "low": "", "high": ""}
    selections = (
        ("Line", "Raw (unfiltered)"),
        ("Smoothed Trend", "Raw (unfiltered)"),
        ("Time-Amplitude Heatmap", "Raw (unfiltered)"),
        ("Time-Amplitude Heatmap", "Wavelet denoising"),
        ("Frequency Spectrum (FFT)", "Raw (unfiltered)"),
        ("Distribution", "Raw (unfiltered)"),
        ("Line", "Wavelet denoising"),
    )
    return [
        {**defaults, "mode": mode, "filter": filter_name}
        for mode, filter_name in selections
    ]


def _render_chart_image(dataframe, config):
    """Render one bounded scientific chart to an in-memory PNG image."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.dates import DateFormatter

    series_config = CHART_SERIES[config["series"]]
    signal = pd.to_numeric(dataframe[series_config["column"]], errors="coerce")
    valid = pd.DataFrame({
        "captured_at": dataframe["captured_at"],
        "value": signal,
    }).dropna().sort_values("captured_at").tail(MAX_ANALYSIS_SAMPLES)
    if valid.empty:
        raise ValueError(f"No valid samples are available for {config['series']}.")

    times, values, filter_note, error = apply_report_filter(
        valid["captured_at"],
        valid["value"],
        config["filter"],
        config["cutoff"],
        config["low"],
        config["high"],
    )
    if error or times is None or values is None or not len(values):
        raise ValueError(error or "The selected chart has no filtered samples.")

    figure, axis = plt.subplots(figsize=(10.5, 5.2), facecolor="white")
    axis.set_facecolor("white")
    axis.grid(True, color=CARD_BORDER, linewidth=0.7)
    axis.set_axisbelow(True)
    mode = config["mode"]
    unit = series_config["unit"]
    color = SIGNAL_BLUE

    if mode == "Line":
        axis.plot(times, values, color=color, linewidth=1.6)
        axis.set_xlabel("Time (UTC)")
        axis.set_ylabel(f"Voltage ({unit})")
        axis.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d\n%H:%M:%S", tz=timezone.utc))
    elif mode == "Smoothed Trend":
        smoothed = pd.Series(values).rolling(window=9, min_periods=1, center=True).mean()
        axis.plot(times, values, color=color, linewidth=0.9, alpha=0.35, label="Raw samples")
        axis.plot(times, smoothed, color=SUCCESS_GREEN, linewidth=2.1, label="9-sample moving average")
        axis.set_xlabel("Time (UTC)")
        axis.set_ylabel(f"Voltage ({unit})")
        axis.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d\n%H:%M:%S", tz=timezone.utc))
        axis.legend(frameon=False)
    elif mode == "Time-Amplitude Heatmap":
        timestamp_values = pd.to_datetime(times, utc=True)
        timestamps_ns = timestamp_values.array.as_unit("ns").asi8
        relative_seconds = (timestamps_ns - timestamps_ns[0]).astype(np.float64) / 1_000_000_000
        time_bins = min(48, max(1, len(values) // 3))
        value_bins = min(32, max(4, int(np.sqrt(len(values)))))
        density, time_edges, value_edges = np.histogram2d(
            relative_seconds, values, bins=(time_bins, value_bins),
        )
        mesh = axis.pcolormesh(
            time_edges, value_edges, density.T, shading="auto", cmap="viridis",
        )
        figure.colorbar(mesh, ax=axis, label="Sample density")
        axis.set_xlabel("Time since recording start (seconds)")
        axis.set_ylabel(f"Voltage ({unit})")
    elif mode == "Distribution":
        axis.hist(
            values,
            bins=min(50, max(10, int(np.sqrt(len(values)) * 2))),
            color=color,
            edgecolor="white",
        )
        axis.set_xlabel(f"Voltage ({unit})")
        axis.set_ylabel("Sample count")
    elif mode == "Frequency Spectrum (FFT)":
        _, uniform_values, sample_interval, error = resample_uniform(times, values)
        if error or uniform_values is None or sample_interval is None:
            plt.close(figure)
            raise ValueError(error or "Could not compute the frequency spectrum.")
        centered = uniform_values - np.mean(uniform_values)
        window = np.hanning(len(centered))
        amplitudes = np.abs(np.fft.rfft(centered * window)) * 2 / np.sum(window)
        frequencies = np.fft.rfftfreq(len(centered), d=sample_interval)
        if len(amplitudes) > 1 and len(centered) % 2 == 0:
            amplitudes[-1] *= 0.5
        axis.plot(frequencies[1:], amplitudes[1:], color=color, linewidth=1.6)
        axis.set_xlabel("Frequency (Hz)")
        axis.set_ylabel(f"Amplitude ({unit})")
    else:
        plt.close(figure)
        raise ValueError(f"Unsupported scientific view: {mode}.")

    figure.tight_layout()
    image = io.BytesIO()
    figure.savefig(image, format="png", dpi=170, facecolor="white")
    plt.close(figure)
    image.seek(0)
    return image, filter_note


def build_report_pdf(dataframe, chart_configs, source_name, source_size, logo_path):
    """Compose the executive summary, chart suite, disclaimers, and sign-off."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from report_fonts import register_report_fonts

    if not chart_configs:
        raise ValueError("The report must include at least one scientific chart.")
    if dataframe.empty:
        raise ValueError("The recording CSV contains no valid samples.")

    navy = colors.HexColor(NAVY)
    blue = colors.HexColor(SIGNAL_BLUE)
    green = colors.HexColor(SUCCESS_GREEN)
    border = colors.HexColor(CARD_BORDER)
    text_color = colors.HexColor("#334155")
    muted = colors.HexColor("#64748B")
    page_width, page_height = A4
    margin = 0.62 * inch
    output = io.BytesIO()
    font_names = register_report_fonts()
    generated_at = pd.Timestamp.now(tz="UTC")
    start_time = dataframe["captured_at"].min()
    end_time = dataframe["captured_at"].max()
    duration_seconds = (end_time - start_time).total_seconds()
    page_count = len(chart_configs) + 2

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName=font_names["mono_bold"],
        fontSize=15, leading=19, textColor=navy, alignment=TA_LEFT,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle", parent=styles["Normal"], fontName=font_names["sans"],
        fontSize=9, leading=12, textColor=blue, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", parent=styles["Heading2"], fontName=font_names["mono_bold"],
        fontSize=9, leading=12, textColor=navy, spaceBefore=4, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="CardLabel", parent=styles["Normal"], fontName=font_names["mono_bold"],
        fontSize=6, leading=7, textColor=muted,
    ))
    styles.add(ParagraphStyle(
        name="CardValue", parent=styles["Normal"], fontName=font_names["mono"],
        fontSize=8, leading=10,
        textColor=navy, wordWrap="CJK",
    ))
    styles.add(ParagraphStyle(
        name="BodyCopy", parent=styles["BodyText"], fontName=font_names["sans"],
        fontSize=8, leading=11, textColor=text_color, spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="SmallNote", parent=styles["Normal"], fontName=font_names["sans"],
        fontSize=7, leading=9,
        textColor=muted,
    ))
    styles.add(ParagraphStyle(
        name="ChartTitle", parent=styles["Heading1"], fontName=font_names["mono_bold"],
        fontSize=11, leading=14, textColor=navy, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="ViewEntry", parent=styles["Normal"], fontName=font_names["mono"],
        fontSize=7, leading=9, textColor=text_color,
    ))
    styles.add(ParagraphStyle(
        name="Signature", parent=styles["Normal"], fontName=font_names["mono"],
        fontSize=7.5, leading=10, textColor=text_color,
    ))
    styles.add(ParagraphStyle(
        name="Identifier", parent=styles["Normal"], fontName=font_names["mono_bold"],
        fontSize=6.2, leading=8, textColor=navy,
    ))
    styles.add(ParagraphStyle(
        name="TitleSmall", parent=styles["Normal"], fontName=font_names["mono_bold"],
        fontSize=8.5, leading=11, textColor=navy,
    ))

    def draw_page(canvas, document):
        canvas.saveState()
        logo_width = 40
        logo_x = margin
        logo_y = page_height - 55
        if Path(logo_path).is_file():
            canvas.setStrokeColor(border)
            canvas.setLineWidth(0.55)
            canvas.rect(logo_x - 2, logo_y - 2, logo_width + 4, 36, stroke=1, fill=0)
            canvas.drawImage(
                str(logo_path),
                logo_x,
                logo_y,
                width=logo_width,
                height=32,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        text_x = margin + 52
        canvas.setFillColor(navy)
        canvas.setFont(font_names["mono_bold"], 7)
        canvas.drawString(text_x, page_height - 31, "CEREPHYTE / BIOSIGNAL INSTRUMENTATION")
        canvas.setFont(font_names["mono_bold"], 10)
        canvas.drawString(text_x, page_height - 45, "SIGNAL ANALYSIS REPORT")
        canvas.setFillColor(muted)
        canvas.setFont(font_names["mono"], 5.3)
        canvas.drawString(
            text_x,
            page_height - 58,
            f"SRC {Path(source_name).name[:38]}  |  UTC {start_time:%Y-%m-%d %H:%M:%S} — {end_time:%H:%M:%S}",
        )
        canvas.drawRightString(
            page_width - margin,
            page_height - 31,
            f"GEN {generated_at:%Y-%m-%d %H:%M:%S} UTC",
        )
        canvas.setFillColor(green)
        canvas.setFont(font_names["mono_bold"], 5.5)
        canvas.drawRightString(page_width - margin, page_height - 45, "SOURCE TIMEZONE: UTC")
        gradient_stops = ("#784BFF", "#6C74FA", "#6296FA", "#55D4E6")
        segment_count = 64
        gradient_width = page_width - 2 * margin
        for segment in range(segment_count):
            position = segment / (segment_count - 1)
            color_index = min(int(position * (len(gradient_stops) - 1)), len(gradient_stops) - 2)
            fraction = position * (len(gradient_stops) - 1) - color_index
            start_color = colors.HexColor(gradient_stops[color_index])
            end_color = colors.HexColor(gradient_stops[color_index + 1])
            color = colors.Color(
                start_color.red + (end_color.red - start_color.red) * fraction,
                start_color.green + (end_color.green - start_color.green) * fraction,
                start_color.blue + (end_color.blue - start_color.blue) * fraction,
            )
            canvas.setFillColor(color)
            canvas.rect(
                margin + segment * gradient_width / segment_count,
                page_height - 70,
                gradient_width / segment_count + 0.2,
                1.8,
                stroke=0,
                fill=1,
            )
        canvas.setStrokeColor(border)
        canvas.setLineWidth(0.5)
        canvas.line(margin, 34, page_width - margin, 34)
        canvas.setFillColor(muted)
        canvas.setFont(font_names["mono"], 5.8)
        canvas.drawString(margin, 21, "ISLERI  /  CEREPHYTE  /  BIOSIGNAL INSTRUMENTATION")
        canvas.drawRightString(page_width - margin, 21, f"{document.page:02d} / {page_count:02d}")
        canvas.restoreState()

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=88,
        bottomMargin=48,
        title="CEREPHYTE Plant Electrophysiology Signal Analysis",
        author="ISLERI",
        subject=f"Scientific analysis of {Path(source_name).name}",
    )

    story = []
    story.append(Paragraph("SIGNAL ANALYSIS REPORT", styles["ReportTitle"]))
    story.append(Paragraph(
        "CEREPHYTE / PLANT BIOSIGNAL INSTRUMENTATION",
        styles["ReportSubtitle"],
    ))
    story.append(Paragraph("01  /  MEASUREMENT SUMMARY", styles["SectionTitle"]))

    voltage = pd.to_numeric(dataframe["voltage"], errors="coerce").dropna()
    if voltage.empty:
        raise ValueError("The recording CSV contains no valid voltage values.")
    metrics = (
        ("SOURCE FILE", Path(source_name).name),
        ("FILE SIZE", f"{source_size:,} bytes"),
        ("RECORDED SAMPLES", f"{len(dataframe):,}"),
        ("PLOTTED SAMPLES", f"{min(len(dataframe), MAX_ANALYSIS_SAMPLES):,} / chart"),
        ("UTC START", dataframe["captured_at"].min().strftime("%Y-%m-%d %H:%M:%S.%f UTC")),
        ("UTC END", dataframe["captured_at"].max().strftime("%Y-%m-%d %H:%M:%S.%f UTC")),
        ("RECORDING DURATION", f"{duration_seconds:.3f} s"),
        ("VOLTAGE MINIMUM", f"{voltage.min():.6f} V"),
        ("VOLTAGE MAXIMUM", f"{voltage.max():.6f} V"),
        ("VOLTAGE MEAN", f"{voltage.mean():.6f} V"),
        ("VOLTAGE STD DEV", f"{voltage.std():.6f} V" if len(voltage) > 1 else "N/A"),
    )
    cards = []
    for label, value in metrics:
        card = Table(
            [[Paragraph(escape(label), styles["CardLabel"])],
             [Paragraph(escape(value), styles["CardValue"])]],
            colWidths=[(page_width - 2 * margin - 14) / 2],
        )
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.7, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        cards.append(card)
    card_rows = [[cards[index], cards[index + 1]] for index in range(0, len(cards), 2)]
    summary_grid = Table(
        card_rows,
        colWidths=[(page_width - 2 * margin - 14) / 2] * 2,
        hAlign="LEFT",
    )
    summary_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(summary_grid)
    story.append(Spacer(1, 10))
    story.append(Paragraph("02  /  ANALYSIS CONFIGURATION", styles["SectionTitle"]))
    views = []
    for index, config in enumerate(chart_configs, start=1):
        views.append([Paragraph(
            f"{index:02d}  {escape(config['series'])}  /  "
            f"{escape(config['mode'])} — {escape(config['filter'])}",
            styles["ViewEntry"],
        )])
    view_table = Table(views, colWidths=[page_width - 2 * margin])
    view_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, border),
        ("LINEBEFORE", (0, 0), (0, -1), 2, blue),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(view_table)

    plot_data = dataframe.tail(MAX_ANALYSIS_SAMPLES).copy()
    for index, config in enumerate(chart_configs, start=1):
        story.append(PageBreak())
        story.append(Paragraph(
            f"FIGURE {index:02d}  /  {escape(config['mode']).upper()}",
            styles["ChartTitle"],
        ))
        story.append(Paragraph(
            f"SERIES  {escape(config['series'])}    /    PROCESSING  {escape(config['filter']).upper()}",
            styles["SmallNote"],
        ))
        story.append(Spacer(1, 8))
        chart_image, filter_note = _render_chart_image(plot_data, config)
        chart_width = page_width - 2 * margin
        chart_height = 4.35 * inch
        chart = Image(chart_image, width=chart_width, height=chart_height, kind="proportional")
        story.append(chart)
        story.append(Spacer(1, 8))
        story.append(Paragraph(escape(filter_note), styles["SmallNote"]))
        story.append(Paragraph(
            "RAW MEASUREMENTS ARE PRESERVED. Processed traces are separately labeled; chart timestamps "
            "are UTC. Frequency analysis uses median-interval linear resampling, and wavelet plots "
            "retain the source recording's UTC time origin.",
            styles["SmallNote"],
        ))

    story.append(PageBreak())
    story.append(Paragraph("03  /  TECHNICAL NOTES & OPERATOR SIGN-OFF", styles["ChartTitle"]))
    story.append(Paragraph(
        "ISLERI laboratory documentation notes",
        styles["ReportSubtitle"],
    ))
    disclaimer_rows = (
        (
            "Calibration and measurement",
            "Verify instrument calibration, sensor configuration, and measurement units before "
            "comparing values or drawing conclusions. Calibration records are not included in the CSV.",
        ),
        (
            "Electrode contact and impedance",
            "Plant electrode placement, contact quality, and contact impedance may affect measured "
            "signals. These conditions are not encoded in the recording; document electrode type, "
            "placement, and impedance checks in the experiment record.",
        ),
        (
            "Ambient interference and shielding",
            "Electrical interference, Faraday shielding, temperature, and humidity may influence "
            "measurements. The CSV does not establish whether shielding was used or record ambient "
            "conditions; enter those observations in the operator notes.",
        ),
        (
            "Sampling and processing limitations",
            "The dashboard records changed telemetry snapshots and may miss intermediate device "
            "samples. Wavelet and frequency-domain results depend on the sampling interval and "
            "processing choices stated with each chart.",
        ),
        (
            "Interpretation",
            "This report is an exploratory instrument output, not a calibration certificate or "
            "diagnostic conclusion. Confirm signal integrity and experimental context before "
            "scientific interpretation.",
        ),
    )
    for index, (heading, body) in enumerate(disclaimer_rows):
        heading_color = amber if index in (2, 4) else navy
        block = Table(
            [[Paragraph(escape(heading), ParagraphStyle(
                f"DisclaimerHeading{index}",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=9.5,
                leading=12,
                textColor=heading_color,
            ))],
             [Paragraph(escape(body), styles["BodyCopy"])]],
            colWidths=[page_width - 2 * margin],
        )
        block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, border),
            ("LINEBEFORE", (0, 0), (0, -1), 2, heading_color),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.extend((block, Spacer(1, 6)))

    signoff = Table(
        [
            [Paragraph("<b>Operator name / ID</b>", styles["Signature"]), "",
             Paragraph("<b>Date (UTC)</b>", styles["Signature"]), ""],
            ["", "", "", ""],
            [Paragraph("<b>Signature</b>", styles["Signature"]), "", "", ""],
            ["", "", "", ""],
        ],
        colWidths=[1.35 * inch, 2.0 * inch, 0.85 * inch, 2.1 * inch],
        rowHeights=[20, 20, 20, 20],
    )
    signoff.setStyle(TableStyle([
        ("SPAN", (1, 2), (3, 2)),
        ("LINEBELOW", (1, 1), (1, 1), 0.8, muted),
        ("LINEBELOW", (3, 1), (3, 1), 0.8, muted),
        ("LINEBELOW", (1, 3), (3, 3), 0.8, muted),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.extend((Spacer(1, 8), signoff))

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return output.getvalue()


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Create an ISLERI-branded, full-suite CEREPHYTE scientific analysis PDF "
            "from a CerePhyte recording CSV."
        ),
    )
    parser.add_argument("csv", type=Path, help="Input CerePhyte recording CSV")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="PDF output path (default: <CSV name>_scientific_report.pdf)",
    )
    parser.add_argument(
        "--logo",
        type=Path,
        default=LOGO_PATH,
        help=f"ISLERI logo image (default: {LOGO_PATH})",
    )
    return parser


def main(argv=None):
    arguments = build_argument_parser().parse_args(argv)
    csv_path = arguments.csv.expanduser().resolve()
    output_path = arguments.output or csv_path.with_name(
        f"{csv_path.stem}_scientific_report.pdf",
    )
    output_path = output_path.expanduser().resolve()
    logo_path = arguments.logo.expanduser().resolve()

    if not csv_path.is_file():
        print(f"Input CSV does not exist: {csv_path}", file=sys.stderr)
        return 2
    if not logo_path.is_file():
        print(f"ISLERI logo does not exist: {logo_path}", file=sys.stderr)
        return 2
    if csv_path == output_path:
        print("The PDF output path must not overwrite the source CSV.", file=sys.stderr)
        return 2

    try:
        dataframe = load_recording(csv_path)
        pdf_bytes = build_report_pdf(
            dataframe,
            full_report_configs(),
            str(csv_path),
            csv_path.stat().st_size,
            logo_path,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_name(output_path.name + ".tmp")
        try:
            temporary_path.write_bytes(pdf_bytes)
            temporary_path.replace(output_path)
        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise
    except (ImportError, MemoryError, OSError, RuntimeError, ValueError, FloatingPointError) as exc:
        print(f"Could not generate the scientific report: {exc}", file=sys.stderr)
        return 1

    print(f"Generated report: {output_path}")
    print(f"Samples included: {len(dataframe):,}")
    print(
        "UTC range: "
        f"{dataframe['captured_at'].min().strftime('%Y-%m-%d %H:%M:%S.%f UTC')} to "
        f"{dataframe['captured_at'].max().strftime('%Y-%m-%d %H:%M:%S.%f UTC')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
