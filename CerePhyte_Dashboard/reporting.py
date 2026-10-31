import io
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

NAVY = "#0F2B5C"
SIGNAL_BLUE = "#2563EB"
SUCCESS_GREEN = "#059669"
WARNING_AMBER = "#D97706"
CARD_BORDER = "#E2E8F0"
ISLERI_GRADIENT = ("#784BFF", "#6C74FA", "#6296FA", "#55D4E6")


def _draw_gradient_rule(figure, y, plt, x=0.075, width=0.85, height=0.004):
    from matplotlib.colors import LinearSegmentedColormap

    gradient_axis = figure.add_axes([x, y, width, height])
    gradient = np.linspace(0, 1, 512).reshape(1, -1)
    gradient_axis.imshow(
        gradient,
        extent=(0, 1, 0, 1),
        aspect="auto",
        cmap=LinearSegmentedColormap.from_list("isleri_report", ISLERI_GRADIENT),
    )
    gradient_axis.axis("off")


def _draw_brand_header(
    figure,
    title,
    subtitle,
    logo_path,
    plt,
    source_name,
    start_time,
    end_time,
    generated_at,
):
    figure.text(
        0.17, 0.964, subtitle.upper(), color=NAVY, fontsize=6.4,
        fontweight="bold", family="DejaVu Sans Mono", va="top",
    )
    figure.text(
        0.17, 0.939, title.upper(), color=NAVY, fontsize=10.4,
        fontweight="bold", family="DejaVu Sans Mono", va="top",
    )
    figure.text(
        0.17, 0.911,
        f"SRC {Path(source_name).name}  |  UTC {start_time:%Y-%m-%d %H:%M:%S}–{end_time:%H:%M:%S}",
        color="#475569", fontsize=5.8, family="DejaVu Sans Mono", va="top",
    )
    figure.text(
        0.92, 0.964, f"GEN {generated_at:%Y-%m-%d %H:%M:%S} UTC",
        color="#475569", fontsize=5.5, family="DejaVu Sans Mono",
        ha="right", va="top",
    )
    figure.text(
        0.92, 0.939, "SIGNAL ANALYSIS REPORT",
        color=SIGNAL_BLUE, fontsize=5.8, family="DejaVu Sans Mono",
        ha="right", va="top",
    )

    logo = Path(logo_path)
    if logo.is_file():
        logo_axis = figure.add_axes([0.075, 0.91, 0.065, 0.065])
        logo_axis.imshow(plt.imread(logo), aspect="equal")
        logo_axis.set_xticks([])
        logo_axis.set_yticks([])
        logo_axis.set_frame_on(False)
        for spine in logo_axis.spines.values():
            spine.set_visible(False)
    _draw_gradient_rule(figure, 0.884, plt)


def _draw_report_footer(figure, page_number, page_count, plt):
    figure.add_artist(plt.Line2D([0.075, 0.925], [0.062, 0.062], color=CARD_BORDER, linewidth=0.7))
    figure.text(
        0.075, 0.043, "ISLERI  /  CEREPHYTE  /  BIOSIGNAL INSTRUMENTATION",
        color="#64748B", fontsize=5.6, family="DejaVu Sans Mono",
    )
    figure.text(
        0.925, 0.043, f"{page_number:02d} / {page_count:02d}",
        color=NAVY, fontsize=6, family="DejaVu Sans Mono", ha="right",
    )


def _filter_description(config):
    filter_name = config["filter"]
    if filter_name == "Wavelet denoising":
        filter_name = "Wavelet Denoising"
    if "band-pass" in config["filter"]:
        return f"{filter_name} ({config['low']}–{config['high']} Hz)"
    if "low-pass" in config["filter"] or "high-pass" in config["filter"]:
        return f"{filter_name} ({config['cutoff']} Hz)"
    return filter_name


def build_report_pdf(
    df,
    chart_configs,
    source_name,
    logo_path,
    chart_series,
    chart_modes,
    apply_filter,
    resample_uniform,
):
    import matplotlib
    from matplotlib.dates import DateFormatter

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.colors import LinearSegmentedColormap

    if df.empty:
        raise ValueError("The selected CSV contains no valid timestamped samples.")
    if not chart_configs:
        raise ValueError("Add at least one chart configuration before generating the report.")

    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans Mono",
        "font.size": 7.5,
        "axes.labelsize": 7.5,
        "axes.titlesize": 8.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.edgecolor": "#CBD5E1",
        "axes.linewidth": 0.65,
        "xtick.color": "#475569",
        "ytick.color": "#475569",
        "text.color": NAVY,
    })

    signal_columns = {item["column"] for item in chart_series.values()}
    if "signal_strength" in signal_columns:
        voltage = pd.to_numeric(df["voltage"], errors="coerce")
        baseline = voltage.rolling(window=10, min_periods=2).mean()
        df = df.copy()
        df["signal_strength"] = (
            (voltage - baseline).pow(2).rolling(window=10, min_periods=2).mean().pow(0.5)
        )

    plot_data = df.tail(3000).copy()
    pdf_buffer = io.BytesIO()
    start_time = df["captured_at"].min()
    end_time = df["captured_at"].max()
    generated_at = datetime.now(timezone.utc)
    duration_seconds = (end_time - start_time).total_seconds()
    page_count = len(chart_configs) + 2
    voltage = pd.to_numeric(df["voltage"], errors="coerce").dropna()
    if voltage.empty:
        raise ValueError("The selected CSV does not contain any valid voltage measurements.")

    with PdfPages(pdf_buffer) as pdf:
        metadata = pdf.infodict()
        metadata["Title"] = "CerePhyte Signal Analysis Report"
        metadata["Author"] = "ISLERI"
        metadata["Subject"] = f"Signal analysis of {Path(source_name).name}"
        metadata["CreationDate"] = generated_at
        metadata["Keywords"] = "CerePhyte, ISLERI, biosignal, UTC, scientific report"

        cover = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        cover_ax = cover.add_axes([0.08, 0.06, 0.84, 0.88])
        cover_ax.axis("off")
        _draw_brand_header(
            cover,
            "SIGNAL ANALYSIS REPORT",
            "CEREPHYTE / BIOSIGNAL INSTRUMENTATION",
            logo_path,
            plt,
            source_name,
            start_time,
            end_time,
            generated_at,
        )

        cover_ax.text(
            0.03, 0.89, "MEASUREMENT SUMMARY", transform=cover_ax.transAxes,
            color=NAVY, fontsize=9, fontweight="bold", family="DejaVu Sans Mono", va="top",
        )

        metadata_rows = [
            ("RECORDED SAMPLES", f"{len(df):,}"),
            ("PLOTTED SAMPLES", f"{len(plot_data):,}"),
            ("VOLTAGE MINIMUM", f"{voltage.min():.6f} V"),
            ("VOLTAGE MAXIMUM", f"{voltage.max():.6f} V"),
            ("VOLTAGE MEAN", f"{voltage.mean():.6f} V"),
            ("VOLTAGE STD DEV", f"{voltage.std():.6f} V" if len(voltage) > 1 else "N/A"),
            ("DURATION", f"{duration_seconds:.3f} s"),
            ("SOURCE FILE", Path(source_name).name),
        ]
        for card_index, (label, value) in enumerate(metadata_rows):
            column = card_index % 2
            row = card_index // 2
            card_x = 0.03 + column * 0.48
            card_y = 0.46 + (3 - row) * 0.075
            cover_ax.add_patch(
                plt.Rectangle(
                    (card_x, card_y), 0.455, 0.064,
                    facecolor="white", edgecolor=CARD_BORDER,
                    linewidth=0.8, transform=cover_ax.transAxes,
                )
            )
            cover_ax.text(
                card_x + 0.012, card_y + 0.047, label,
                transform=cover_ax.transAxes, color="#64748B",
                fontsize=6.0, fontweight="bold", family="DejaVu Sans Mono", va="center",
            )
            cover_ax.text(
                card_x + 0.012, card_y + 0.019, value,
                transform=cover_ax.transAxes, color=NAVY,
                fontsize=7.3, family="DejaVu Sans Mono", va="center",
            )
        cover_ax.text(
            0.03, 0.415, "ANALYSIS CONFIGURATION", transform=cover_ax.transAxes,
            color=NAVY, fontsize=8.2, fontweight="bold", family="DejaVu Sans Mono", va="top",
        )
        cover_ax.text(
            0.03, 0.38,
            "\n".join(
                f"{index}. {config['series']} — {config['mode']} | {_filter_description(config)}"
                for index, config in enumerate(chart_configs, start=1)
            ),
            transform=cover_ax.transAxes, color="#475569", fontsize=6.8,
            family="DejaVu Sans Mono", va="top",
            linespacing=1.35,
        )
        _draw_gradient_rule(cover, 0.11, plt, x=0.105, width=0.79, height=0.003)
        _draw_report_footer(cover, 1, page_count, plt)
        pdf.savefig(cover, facecolor=cover.get_facecolor())
        plt.close(cover)

        for index, config in enumerate(chart_configs, start=1):
            if config["mode"] not in chart_modes:
                raise ValueError(f"Chart {index} has an unsupported scientific view.")
            series_config = chart_series[config["series"]]
            values = pd.to_numeric(plot_data[series_config["column"]], errors="coerce")
            clean = pd.DataFrame({
                "captured_at": plot_data["captured_at"],
                "value": values,
            }).dropna().sort_values("captured_at")
            if clean.empty:
                raise ValueError(f"Chart {index} has no valid values for {config['series']}.")

            times, filtered_values, filter_note, filter_error = apply_filter(
                clean["captured_at"],
                clean["value"],
                config["filter"],
                config["cutoff"],
                config["low"],
                config["high"],
            )
            if filter_error or times is None or filtered_values is None or len(filtered_values) == 0:
                raise ValueError(f"Chart {index}: {filter_error or 'No valid filtered samples.'}")

            figure = plt.figure(figsize=(11.69, 8.27), facecolor="white")
            axis = figure.add_axes([0.105, 0.17, 0.79, 0.66])
            axis.set_facecolor("white")
            axis.grid(True, color=CARD_BORDER, linewidth=0.7)
            axis.set_axisbelow(True)
            color = series_config["color"]
            mode = config["mode"]
            unit = series_config["unit"]
            title = f"{config['series']} · {mode}"
            _draw_brand_header(
                figure,
                f"FIGURE {index:02d}  /  {mode.upper()}",
                "CEREPHYTE / BIOSIGNAL INSTRUMENTATION",
                logo_path,
                plt,
                source_name,
                start_time,
                end_time,
                generated_at,
            )

            if mode == "Line":
                axis.plot(times, filtered_values, color=SIGNAL_BLUE, linewidth=1.25, label="Raw signal")
                axis.set_xlabel("TIME / UTC")
                axis.set_ylabel(f"Signal ({unit})")
                axis.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d\n%H:%M:%S", tz=timezone.utc))
            elif mode == "Smoothed Trend":
                smoothed = pd.Series(filtered_values).rolling(
                    window=9, min_periods=1, center=True,
                ).mean()
                axis.plot(times, filtered_values, color=SIGNAL_BLUE, linewidth=0.85, alpha=0.42, label="Raw samples")
                axis.plot(times, smoothed, color=SUCCESS_GREEN, linewidth=1.7, label="9-sample moving average")
                axis.set_xlabel("TIME / UTC")
                axis.set_ylabel(f"Signal ({unit})")
                axis.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d\n%H:%M:%S", tz=timezone.utc))
                axis.legend(
                    frameon=False, loc="upper right", ncol=2,
                    prop={"family": "DejaVu Sans Mono", "size": 6},
                )
            elif mode == "Time-Amplitude Heatmap":
                timestamps = pd.to_datetime(times, utc=True)
                timestamps_ns = timestamps.array.as_unit("ns").asi8
                relative_seconds = (timestamps_ns - timestamps_ns[0]).astype(np.float64) / 1_000_000_000
                time_bins = min(48, max(1, len(filtered_values) // 3))
                value_bins = min(32, max(4, int(np.sqrt(len(filtered_values)))))
                density, time_edges, value_edges = np.histogram2d(
                    relative_seconds, filtered_values, bins=(time_bins, value_bins),
                )
                mesh = axis.pcolormesh(
                    time_edges, value_edges, density.T, shading="auto", cmap="viridis",
                )
                colorbar = figure.colorbar(mesh, ax=axis, fraction=0.035, pad=0.025)
                colorbar.set_label("SAMPLE DENSITY", fontsize=6.5, family="DejaVu Sans Mono")
                axis.set_xlabel("ELAPSED TIME / s")
                axis.set_ylabel(f"Signal ({unit})")
            elif mode == "Distribution":
                axis.hist(
                    filtered_values,
                    bins=min(50, max(10, int(np.sqrt(len(filtered_values)) * 2))),
                    color=color,
                    edgecolor="white",
                )
                axis.set_xlabel(f"SIGNAL / {unit}")
                axis.set_ylabel("SAMPLE COUNT")
            elif mode == "Frequency Spectrum (FFT)":
                _, spectrum_values, sample_interval, spectrum_error = resample_uniform(
                    times, filtered_values,
                )
                if spectrum_error or spectrum_values is None or sample_interval is None:
                    plt.close(figure)
                    raise ValueError(
                        f"Chart {index}: {spectrum_error or 'Could not calculate the frequency spectrum.'}"
                    )
                centered_values = spectrum_values - np.mean(spectrum_values)
                window = np.hanning(len(centered_values))
                amplitudes = np.abs(np.fft.rfft(centered_values * window)) * 2 / np.sum(window)
                frequencies = np.fft.rfftfreq(len(centered_values), d=sample_interval)
                if len(amplitudes) > 1 and len(centered_values) % 2 == 0:
                    amplitudes[-1] *= 0.5
                axis.plot(frequencies[1:], amplitudes[1:], color=SIGNAL_BLUE, linewidth=1.25)
                axis.set_xlabel("FREQUENCY / Hz")
                axis.set_ylabel(f"AMPLITUDE / {unit}")
            else:
                plt.close(figure)
                raise ValueError(f"Chart {index} has an unsupported scientific view: {mode}.")

            figure.text(
                0.105, 0.105,
                f"PROCESSING  {_filter_description(config).upper()}  |  {filter_note or ''}",
                fontsize=5.7, color="#475569", family="DejaVu Sans Mono", wrap=True,
            )
            _draw_gradient_rule(figure, 0.083, plt, x=0.105, width=0.79, height=0.003)
            _draw_report_footer(figure, index + 1, page_count, plt)
            pdf.savefig(figure, facecolor=figure.get_facecolor())
            plt.close(figure)

        closing = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        closing_ax = closing.add_axes([0.09, 0.08, 0.82, 0.77])
        closing_ax.axis("off")
        _draw_brand_header(
            closing,
            "TECHNICAL NOTES  /  SIGN-OFF",
            "CEREPHYTE / BIOSIGNAL INSTRUMENTATION",
            logo_path,
            plt,
            source_name,
            start_time,
            end_time,
            generated_at,
        )
        disclaimer_sections = (
            (
                "Calibration and measurement",
                "Confirm instrument calibration, sensor configuration, and measurement units before "
                "comparing values or drawing conclusions. Calibration records are not included in "
                "the supplied CSV.",
            ),
            (
                "Plant/electrode contact",
                "Electrode placement, contact quality, and contact impedance can affect biosignal "
                "measurements. These conditions are not recorded in the supplied CSV; document "
                "them separately for the experiment.",
            ),
            (
                "Environment and shielding",
                "Ambient electrical interference, Faraday shielding, temperature, and humidity may "
                "influence measurements. Their values or presence cannot be determined from the "
                "supplied CSV and should be recorded in the lab notes.",
            ),
            (
                "Sampling and signal processing",
                "The dashboard records changed telemetry snapshots and may miss intermediate device "
                "samples. Filtered results depend on the selected method and cutoff values; frequency "
                "analysis uses median-interval resampling.",
            ),
            (
                "Interpretation",
                "This report is an exploratory instrument output, not a calibration certificate or "
                "a diagnostic conclusion. Interpret results alongside experimental records and "
                "independent validation.",
            ),
        )
        y_position = 0.91
        for heading, body in disclaimer_sections:
            heading_color = (
                WARNING_AMBER
                if heading in {"Environment and shielding", "Interpretation"}
                else NAVY
            )
            closing_ax.text(
                0.02, y_position, heading, transform=closing_ax.transAxes,
                fontsize=8.3, color=heading_color, fontweight="bold",
                family="DejaVu Sans Mono", va="top",
            )
            closing_ax.text(
                0.02, y_position - 0.045, body, transform=closing_ax.transAxes,
                fontsize=7.4, color="#475569", family="DejaVu Sans",
                va="top", wrap=True,
                linespacing=1.5,
            )
            y_position -= 0.145
        closing_ax.text(
            0.02, 0.19, "OPERATOR SIGN-OFF",
            transform=closing_ax.transAxes, color=NAVY,
            fontsize=8.3, fontweight="bold", family="DejaVu Sans Mono", va="top",
        )
        closing_ax.text(
            0.02, 0.145, "Name / ID: __________________________",
            transform=closing_ax.transAxes, color="#334155", fontsize=7.3,
            family="DejaVu Sans Mono", va="top",
        )
        closing_ax.text(
            0.52, 0.145, "Date (UTC): __________________",
            transform=closing_ax.transAxes, color="#334155", fontsize=7.3,
            family="DejaVu Sans Mono", va="top",
        )
        closing_ax.text(
            0.02, 0.10, "Signature: ______________________________________________",
            transform=closing_ax.transAxes, color="#334155", fontsize=7.3,
            family="DejaVu Sans Mono", va="top",
        )
        _draw_gradient_rule(closing, 0.11, plt, x=0.105, width=0.79, height=0.003)
        _draw_report_footer(closing, page_count, page_count, plt)
        pdf.savefig(closing, facecolor=closing.get_facecolor())
        plt.close(closing)

    return pdf_buffer.getvalue()
