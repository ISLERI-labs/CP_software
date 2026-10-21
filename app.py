"""CEREPHYTE Rev. 4.5 — functional desktop UI prototype (SIMULATION ONLY)."""
import csv
import math
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

RATE = 128
CHANNELS = 8
HISTORY_SECONDS = 120
BG = '#06152d'
PANEL = '#0b2750'
PANEL2 = '#0c3161'
CYAN = '#1ce6d5'
BLUE = '#168ef5'
TEXT = '#e8f4ff'
MUTED = '#95b8da'
pg.setConfigOptions(antialias=True, background=PANEL, foreground=MUTED)

STYLE = '''
QMainWindow, QWidget#root { background: #06152d; color: #e8f4ff; }
QWidget { color: #e8f4ff; font-family: 'Segoe UI'; font-size: 12px; }
QFrame#panel { background: #0b2750; border: 1px solid #1a4a7b; border-radius: 12px; }
QFrame#sidebar { background: #081f43; border-right: 1px solid #194673; }
QLabel#heading { font-size: 17px; font-weight: 700; }
QLabel#big { font-size: 23px; font-weight: 700; color: #1ce6d5; }
QLabel#muted { color: #95b8da; }
QPushButton { background: #103c74; border: 1px solid #21548a; border-radius: 7px; padding: 9px 12px; text-align: left; }
QPushButton:hover { background: #1660a8; }
QPushButton:checked { background: #087fd1; border-color: #13c4ec; }
QPushButton#primary { background: #087fd1; font-weight: 700; text-align: center; }
QPushButton#danger { background: #9b284e; text-align: center; }
QComboBox, QSpinBox, QLineEdit { background: #103763; border: 1px solid #24598e; border-radius: 6px; padding: 6px; }
QComboBox QAbstractItemView { background: #103763; }
QScrollArea { border: none; background: transparent; }
'''


def label(text, kind=None):
    x = QLabel(text)
    if kind:
        x.setObjectName(kind)
    x.setWordWrap(True)
    return x


def panel(title, layout=None):
    frame = QFrame()
    frame.setObjectName('panel')
    v = QVBoxLayout(frame)
    v.setContentsMargins(15, 13, 15, 13)
    v.setSpacing(10)
    v.addWidget(label(title, 'heading'))
    if layout:
        v.addLayout(layout)
    return frame, v


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ISLERI CEREPHYTE — Rev. 4.5 | Simulation')
        self.resize(1440, 860)
        self.setMinimumSize(1050, 680)
        self.rate = RATE
        self.capacity = RATE * HISTORY_SECONDS
        self.ts = deque(maxlen=self.capacity)
        self.samples = [deque(maxlen=self.capacity) for _ in range(CHANNELS)]
        self.sample_index = 0
        self.last_tick = time.monotonic()
        self.render_counter = 0
        self.freeze = False
        self.record_file = None
        self.csv_writer = None
        self.record_path = None
        self.record_start = None
        self.markers = []
        self.record_dir = Path.home() / 'Documents' / 'CEREPHYTE_Recordings'
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_name = 'Plant bioelectric experiment'
        self.build_ui()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.update_clock()

    def build_ui(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(216)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(13, 22, 13, 18)
        sv.setSpacing(9)
        sv.addWidget(label('✦  CEREPHYTE', 'heading'))
        sv.addWidget(label('Rev. 4.5  •  ISLERI', 'muted'))
        sv.addSpacing(18)
        self.nav = {}
        names = ['Dashboard', 'Live Signals', 'Analysis', 'Calibration', 'Experiments', 'Recordings', 'AI Insights', 'Settings']
        symbols = ['⌂', '∿', '▥', '⚙', '◇', '◉', '✧', '☷']
        for i, name in enumerate(names):
            b = QPushButton(f'{symbols[i]}   {name}')
            b.setCheckable(True)
            b.clicked.connect(lambda _, idx=i: self.navigate(idx))
            sv.addWidget(b)
            self.nav[i] = b
        sv.addStretch(1)
        sv.addWidget(label('●  SIMULATION MODE', 'muted'))
        sv.addWidget(label('No hardware connected', 'muted'))
        outer.addWidget(side)
        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(18, 13, 18, 14)
        mv.setSpacing(12)
        header = QHBoxLayout()
        brand = QVBoxLayout()
        brand.addWidget(label('CEREPHYTE  /  BIOELECTRIC MONITOR', 'heading'))
        brand.addWidget(label('Independent Society for Laboratory Electrophysiology Research and Instrumentation', 'muted'))
        header.addLayout(brand, 1)
        self.status = label('●  SIMULATED · 128 SPS', 'muted')
        header.addWidget(self.status)
        self.clock = label('', 'muted')
        header.addWidget(self.clock)
        mv.addLayout(header)
        self.stack = QStackedWidget()
        mv.addWidget(self.stack, 1)
        outer.addWidget(main, 1)
        self.build_dashboard()
        self.build_simple_pages()
        self.navigate(0)

    def make_plot(self, title, bottom='Time (s)', left='Amplitude (a.u.)'):
        p = pg.PlotWidget()
        p.setBackground(PANEL)
        p.showGrid(x=True, y=True, alpha=0.17)
        p.setLabel('bottom', bottom)
        p.setLabel('left', left)
        p.getPlotItem().setTitle(title, color=TEXT, size='11pt')
        p.getPlotItem().getViewBox().setMouseEnabled(x=True, y=True)
        return p

    def build_dashboard(self):
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(12)
        left = QVBoxLayout()
        signal_panel, s = panel('LIVE SIGNAL   ●   Real-time simulated bioelectric waveform')
        controls = QHBoxLayout()
        controls.addWidget(label('Channel:'))
        self.channel = QComboBox()
        self.channel.addItems([f'Channel {i+1}' for i in range(CHANNELS)])
        controls.addWidget(self.channel)
        controls.addWidget(label('View:'))
        self.window_combo = QComboBox()
        self.window_combo.addItems(['5 s', '10 s', '30 s', '60 s', '120 s'])
        controls.addWidget(self.window_combo)
        controls.addWidget(label('Gain:'))
        self.gain_combo = QComboBox()
        self.gain_combo.addItems(['1×', '2×', '5×', '10×'])
        controls.addWidget(self.gain_combo)
        controls.addWidget(label('Display LPF:'))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['Off', '10 Hz', '20 Hz', '40 Hz'])
        controls.addWidget(self.filter_combo)
        self.freeze_button = QPushButton('Freeze view')
        self.freeze_button.clicked.connect(self.toggle_freeze)
        controls.addWidget(self.freeze_button)
        s.addLayout(controls)
        self.wave = self.make_plot('', 'Time (s)', 'Simulated voltage (µV)')
        self.wave.setMinimumHeight(270)
        self.curve = self.wave.plot(pen=pg.mkPen(CYAN, width=1.8))
        self.wave.setYRange(-170, 170)
        s.addWidget(self.wave, 1)
        self.signal_footer = label('Waiting for samples...', 'muted')
        s.addWidget(self.signal_footer)
        left.addWidget(signal_panel, 3)
        lower = QHBoxLayout()
        fft_panel, f = panel('FFT SPECTRUM')
        self.fft = self.make_plot('', 'Frequency (Hz)', 'Power (a.u.²/Hz)')
        self.fft_curve = self.fft.plot(pen=pg.mkPen('#d96bff', width=2))
        self.fft.setLogMode(x=False, y=True)
        f.addWidget(self.fft)
        lower.addWidget(fft_panel, 1)
        stats_panel, stv = panel('SIGNAL OVERVIEW')
        self.stats = label('Waiting for samples...')
        self.stats.setFont(QFont('Consolas', 11))
        stv.addWidget(self.stats)
        stv.addStretch()
        lower.addWidget(stats_panel, 1)
        left.addLayout(lower, 2)
        top.addLayout(left, 4)
        right = QVBoxLayout()
        device_panel, d = panel('DEVICE STATUS')
        d.addWidget(label('●  SIMULATED INPUT', 'big'))
        d.addWidget(label('Hardware: Not connected\nSource: Local synthetic generator\nRate: 128 samples/s\nChannels: 8 synthetic channels\nBattery: Not available\nTemperature: Not available', 'muted'))
        right.addWidget(device_panel)
        ai_panel, a = panel('EXPERIMENTAL PLANT ANALYSIS')
        a.addWidget(label('Plant stress: Not evaluated\nPhotosynthesis: Not measured\nHydration: Not measured\n\nElectrical recordings alone do not validate these predictions.', 'muted'))
        right.addWidget(ai_panel)
        right.addStretch()
        top.addLayout(right, 1)
        pv.addLayout(top, 1)
        quick_panel, q = panel('QUICK CONTROLS   /   ACTIVE EXPERIMENT')
        quick = QHBoxLayout()
        self.record_button = QPushButton('●  Start recording')
        self.record_button.setObjectName('primary')
        self.record_button.clicked.connect(self.toggle_record)
        quick.addWidget(self.record_button)
        self.marker_button = QPushButton('◇  Add marker')
        self.marker_button.clicked.connect(self.add_marker)
        quick.addWidget(self.marker_button)
        autoscale = QPushButton('⌁  Auto scale')
        autoscale.clicked.connect(lambda: self.wave.enableAutoRange())
        quick.addWidget(autoscale)
        history = QPushButton('▣  Show history')
        history.clicked.connect(lambda: self.navigate(1))
        quick.addWidget(history)
        self.experiment_label = label('Experiment: Plant bioelectric experiment', 'muted')
        quick.addWidget(self.experiment_label, 1)
        q.addLayout(quick)
        pv.addWidget(quick_panel)
        self.stack.addWidget(page)

    def build_simple_pages(self):
        # Live signals page reuses the same acquisition buffer but has an independent plot.
        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('LIVE SIGNALS  /  HISTORY', 'heading'))
        v.addWidget(label('Pan or zoom with the mouse. Freeze the view on the Dashboard to stop automatic following.', 'muted'))
        self.history_plot = self.make_plot('Buffered history — selected channel', 'Time (s)', 'Simulated voltage (µV)')
        self.history_curve = self.history_plot.plot(pen=pg.mkPen('#32d4ff', width=1.5))
        v.addWidget(self.history_plot)
        self.stack.addWidget(page)

        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('ANALYSIS', 'heading'))
        v.addWidget(label('FFT and summary statistics of the selected simulated channel.', 'muted'))
        self.analysis_text = label('Waiting for samples...')
        v.addWidget(self.analysis_text)
        self.analysis_fft = self.make_plot('Power spectrum', 'Frequency (Hz)', 'Power')
        self.analysis_fft_curve = self.analysis_fft.plot(pen=pg.mkPen('#d96bff', width=2))
        v.addWidget(self.analysis_fft)
        self.stack.addWidget(page)

        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('CALIBRATION', 'heading'))
        v.addWidget(label('Hardware calibration is unavailable in simulation mode. Use reference voltages and calibrated equipment after the real acquisition adapter is implemented.', 'muted'))
        self.stack.addWidget(page)
        v.addStretch()

        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('EXPERIMENTS', 'heading'))
        v.addWidget(label('Experiment name (saved as recording metadata):'))
        name = QLineEdit(self.experiment_name)
        name.textChanged.connect(self.change_experiment)
        v.addWidget(name)
        v.addWidget(label('Markers are written into a separate markers CSV beside the recording.', 'muted'))
        v.addStretch()
        self.stack.addWidget(page)

        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('RECORDINGS', 'heading'))
        self.recording_status = label('Not recording')
        v.addWidget(self.recording_status)
        folder = QPushButton('Choose recording folder')
        folder.clicked.connect(self.choose_folder)
        v.addWidget(folder)
        self.folder_label = label(str(self.record_dir), 'muted')
        v.addWidget(self.folder_label)
        v.addStretch()
        self.stack.addWidget(page)

        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('AI INSIGHTS  /  RESEARCH PREVIEW', 'heading'))
        v.addWidget(label('No plant-health model is loaded. Reliable stress, hydration, or photosynthesis estimates require validated datasets, ground truth, and uncertainty reporting. No fabricated percentages are displayed.', 'muted'))
        v.addStretch()
        self.stack.addWidget(page)

        page = QWidget()
        v = QVBoxLayout(page)
        v.addWidget(label('SETTINGS', 'heading'))
        v.addWidget(label('Simulation sample rate (samples per second):'))
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(16, 512)
        self.rate_spin.setValue(RATE)
        self.rate_spin.valueChanged.connect(self.change_rate)
        v.addWidget(self.rate_spin)
        v.addWidget(label('This setting affects the simulated data source only. Hardware sample rates require explicit device configuration.', 'muted'))
        v.addStretch()
        self.stack.addWidget(page)

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, b in self.nav.items():
            b.setChecked(i == index)
        if index == 1:
            self.refresh_history()

    def update_clock(self):
        self.clock.setText(datetime.now().strftime('%I:%M:%S %p  ·  %d %b %Y'))

    def change_experiment(self, name):
        self.experiment_name = name.strip() or 'Untitled experiment'
        self.experiment_label.setText('Experiment: ' + self.experiment_name)

    def change_rate(self, value):
        if self.record_file:
            QMessageBox.warning(self, 'Recording active', 'Stop recording before changing the sample rate.')
            self.rate_spin.blockSignals(True)
            self.rate_spin.setValue(self.rate)
            self.rate_spin.blockSignals(False)
            return
        self.rate = value
        self.capacity = value * HISTORY_SECONDS
        self.ts = deque(maxlen=self.capacity)
        self.samples = [deque(maxlen=self.capacity) for _ in range(CHANNELS)]
        self.sample_index = 0
        self.last_tick = time.monotonic()
        self.status.setText(f'●  SIMULATED · {value} SPS')

    def choose_folder(self):
        chosen = QFileDialog.getExistingDirectory(self, 'Choose recording folder', str(self.record_dir))
        if chosen:
            self.record_dir = Path(chosen)
            self.folder_label.setText(str(self.record_dir))

    def toggle_record(self):
        if self.record_file:
            self.stop_record()
            return
        try:
            self.record_dir.mkdir(parents=True, exist_ok=True)
            name = datetime.now().strftime('cerephyte_%Y%m%d_%H%M%S.csv')
            self.record_path = self.record_dir / name
            self.record_file = open(self.record_path, 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.record_file)
            self.csv_writer.writerow(['time_s'] + [f'channel_{i+1}_simulated_uV' for i in range(CHANNELS)])
            self.record_start = self.sample_index / self.rate
            self.record_button.setText('■  Stop recording')
            self.record_button.setObjectName('danger')
            self.record_button.style().unpolish(self.record_button)
            self.record_button.style().polish(self.record_button)
            self.recording_status.setText('Recording: ' + str(self.record_path))
        except OSError as e:
            self.record_file = None
            self.csv_writer = None
            QMessageBox.critical(self, 'Recording error', str(e))

    def stop_record(self):
        if not self.record_file:
            return
        self.record_file.close()
        self.record_file = None
        self.csv_writer = None
        self.record_button.setText('●  Start recording')
        self.record_button.setObjectName('primary')
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
        self.recording_status.setText('Saved: ' + str(self.record_path))

    def add_marker(self):
        timestamp = self.sample_index / self.rate
        self.markers.append(timestamp)
        if self.record_path and self.record_file:
            marker_path = self.record_path.with_name(self.record_path.stem + '_markers.csv')
            exists = marker_path.exists()
            with open(marker_path, 'a', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                if not exists:
                    w.writerow(['time_s', 'event'])
                w.writerow([f'{timestamp - self.record_start:.6f}', 'manual marker'])
        self.signal_footer.setText(f'Marker added at t={timestamp:.2f} s (simulation clock)')

    def toggle_freeze(self):
        self.freeze = not self.freeze
        self.freeze_button.setText('Resume live view' if self.freeze else 'Freeze view')
        if not self.freeze:
            self.wave.enableAutoRange(axis='y', enable=False)

    def tick(self):
        now = time.monotonic()
        # Simulation advances based on elapsed time, not the GUI timer's accuracy.
        count = max(0, min(int((now - self.last_tick) * self.rate), self.rate * 2))
        if count:
            idx = np.arange(self.sample_index, self.sample_index + count, dtype=np.float64)
            seconds = idx / self.rate
            all_values = []
            for ch in range(CHANNELS):
                phase = ch * 0.43
                rng = np.random.normal(0, 7, count)
                vals = (43 * np.sin(2 * np.pi * (1.7 + ch * 0.13) * seconds + phase)
                        + 18 * np.sin(2 * np.pi * 0.33 * seconds + phase)
                        + rng)
                self.samples[ch].extend(vals.tolist())
                all_values.append(vals)
            self.ts.extend(seconds.tolist())
            if self.csv_writer:
                for j in range(count):
                    self.csv_writer.writerow([f'{seconds[j] - self.record_start:.6f}'] + [f'{all_values[c][j]:.5f}' for c in range(CHANNELS)])
                self.record_file.flush()
            self.sample_index += count
            self.last_tick += count / self.rate
        self.render_counter += 1
        if self.render_counter % 2 == 0:
            self.render()

    def selected_data(self):
        ch = self.channel.currentIndex()
        t = np.asarray(self.ts, dtype=np.float64)
        y = np.asarray(self.samples[ch], dtype=np.float64)
        filter_name = self.filter_combo.currentText()
        if filter_name != 'Off' and len(y) > 1:
            cutoff = float(filter_name.split()[0])
            alpha = 1 - math.exp(-2 * math.pi * cutoff / self.rate)
            filtered = np.empty_like(y)
            filtered[0] = y[0]
            for i in range(1, len(y)):
                filtered[i] = filtered[i-1] + alpha * (y[i] - filtered[i-1])
            y = filtered
        gain = int(self.gain_combo.currentText().replace('×', ''))
        return t, y * gain

    def render(self):
        t, y = self.selected_data()
        if len(t) < 3:
            return
        window = int(self.window_combo.currentText().split()[0])
        if not self.freeze:
            cut = np.searchsorted(t, t[-1] - window)
            self.curve.setData(t[cut:], y[cut:])
            self.wave.setXRange(max(0, t[-1] - window), max(window, t[-1]), padding=0)
        self.signal_footer.setText(f'{self.rate} simulated samples/s · {len(t)} buffered · {self.sample_index} generated · Display gain only')
        if self.render_counter % 4 == 0:
            self.update_statistics(y)
            if self.stack.currentIndex() == 1:
                self.refresh_history()

    def update_statistics(self, y):
        if len(y) < 8:
            return
        segment = y[-min(len(y), self.rate * 5):]
        mean = float(np.mean(segment))
        rms = float(np.sqrt(np.mean(segment ** 2)))
        peak = float(np.ptp(segment))
        demeaned = segment - mean
        windowed = demeaned * np.hanning(len(segment))
        power = np.abs(np.fft.rfft(windowed)) ** 2 / max(1, len(segment))
        freqs = np.fft.rfftfreq(len(segment), d=1 / self.rate)
        dom = float(freqs[1 + np.argmax(power[1:])]) if len(power) > 1 else 0
        text = (f'Peak-to-peak:  {peak:8.2f} µV\n'
                f'RMS:           {rms:8.2f} µV\n'
                f'Mean:          {mean:8.2f} µV\n'
                f'Dominant freq: {dom:8.2f} Hz\n'
                f'Buffer:        {len(y):8d} points\n\n'
                'Synthetic waveform — not a biological measurement')
        self.stats.setText(text)
        self.analysis_text.setText(text)
        valid = freqs > 0
        self.fft_curve.setData(freqs[valid], np.maximum(power[valid], 1e-12))
        self.analysis_fft_curve.setData(freqs[valid], power[valid])

    def refresh_history(self):
        t, y = self.selected_data()
        if len(t):
            self.history_curve.setData(t, y)
            self.history_plot.enableAutoRange()

    def closeEvent(self, event):
        self.stop_record()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
