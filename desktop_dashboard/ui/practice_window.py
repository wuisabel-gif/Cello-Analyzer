import numpy as np
from PySide6.QtCore import QRectF, QPointF, QThread, Signal, Qt
from PySide6.QtGui import QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QInputDialog, QTextEdit, QDoubleSpinBox
from desktop_dashboard.practice import analyze
from desktop_dashboard.practice_coach import observation, comparison
from desktop_dashboard.ui.widgets import ACCENT, ACCENT_ALT, TEXT, MUTED, SURFACE_ELEVATED


class ComparisonChart(QWidget):
    def __init__(self, title, field):
        super().__init__()
        self.title, self.field, self.takes = title, field, []
        self.setMinimumHeight(150)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), SURFACE_ELEVATED)
        p.setPen(TEXT)
        p.drawText(12, 20, self.title)
        rect = QRectF(65, 38, self.width()-85, self.height()-65)
        p.setPen(MUTED)
        p.drawRect(rect)
        if not self.takes:
            return
        duration = max(t.duration for _, t in self.takes)
        finite = [getattr(t, self.field)[np.isfinite(getattr(t, self.field))] for _, t in self.takes]
        values = np.concatenate(finite)
        if not len(values):
            p.drawText(rect, Qt.AlignCenter, "No valid measurement frames")
            return
        low, high = (float(values.min()), float(values.max())) if len(values) else (-1, 1)
        if high-low < 2:
            low, high = low-1, high+1
        p.drawText(4, 48, f'{high:.0f}')
        p.drawText(4, int(rect.bottom()), f'{low:.0f}')
        p.drawText(65, self.height()-7, f'0 s • Excerpt axis • end {duration:.2f} s')
        for slot, take in self.takes:
            color = [ACCENT, ACCENT_ALT][slot]
            path, connected = QPainterPath(), False
            for time, value in zip(take.time, getattr(take, self.field)):
                if not np.isfinite(value):
                    connected = False
                    continue
                point = QPointF(rect.left()+time/duration*rect.width(), rect.bottom()-(value-low)/(high-low)*rect.height())
                if connected:
                    path.lineTo(point)
                else:
                    path.moveTo(point)
                connected = True
            p.setPen(QPen(color, 2))
            p.drawPath(path)


class AnalysisWorker(QThread):
    result = Signal(int, object, str)

    def __init__(self, index, path, parent, start=0., duration=30.):
        super().__init__(parent)
        self.index, self.path = index, path
        self.start_seconds, self.duration_seconds = start, duration

    def run(self):
        try:
            self.result.emit(self.index, analyze(self.path, self.start_seconds, self.duration_seconds), '')
        except (OSError, ValueError) as exc:
            self.result.emit(self.index, None, str(exc))


class PracticeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Local practice comparison')
        self.resize(1000, 850)
        self.takes = []
        self.worker = None
        self.buttons = []
        layout = QVBoxLayout(self)
        title = QLabel('Sustained note • compare two local takes')
        title.setStyleSheet('font-size: 24px; font-weight: bold')
        layout.addWidget(title)
        note = QLabel('Offline • WAV ≤60 s / 32 MB • MOV audio excerpt ≤60 s via installed FFmpeg\nPitch relative to A3 (220 Hz), not a target-note grade. Relative RMS is not SPL.\nPlots start at each excerpt’s zero; cues use source timestamps. No score or onset alignment. Short variation is not a validated vibrato assessment.')
        note.setWordWrap(True)
        layout.addWidget(note)
        excerpt_controls = QHBoxLayout()
        self.excerpt_start = QDoubleSpinBox()
        self.excerpt_start.setRange(0, 86400)
        self.excerpt_start.setDecimals(2)
        self.excerpt_start.setSuffix(' s')
        self.excerpt_duration = QDoubleSpinBox()
        self.excerpt_duration.setRange(.1, 60)
        self.excerpt_duration.setValue(30)
        self.excerpt_duration.setDecimals(2)
        self.excerpt_duration.setSuffix(' s')
        for control in (QLabel('MOV only • start'), self.excerpt_start,
                        QLabel('duration (max 60 s)'), self.excerpt_duration):
            excerpt_controls.addWidget(control)
        layout.addLayout(excerpt_controls)
        buttons = QHBoxLayout()
        for index in range(2):
            button = QPushButton(f'Import take {index+1}')
            button.clicked.connect(lambda checked=False, i=index: self.choose(i))
            buttons.addWidget(button)
            self.buttons.append(button)
        layout.addLayout(buttons)
        self.legend = QLabel('Purple: take 1 • Gold: take 2 • Import the same sustained-note exercise.')
        self.legend.setTextFormat(Qt.PlainText)
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)
        self.charts = [ComparisonChart(title, field) for title, field in [
            ('Pitch trend • 0.5 s median • cents relative to A3', 'trend'),
            ('Short variation around trend • cents • gaps indicate uncertainty', 'variation'),
            ('Relative loudness shape • dB below each take’s peak RMS', 'loudness')]]
        for chart in self.charts:
            layout.addWidget(chart)
        self.observations = QTextEdit()
        self.observations.setReadOnly(True)
        self.observations.setMaximumHeight(180)
        self.observations.setPlaceholderText("Local practice cues appear after import; no external AI is used.")
        layout.addWidget(self.observations)
        self.setStyleSheet('QWidget {background:#171717;color:#f3f1f8} QPushButton {background:#574064;padding:10px} QTextEdit {background:#232323} QDoubleSpinBox, QDoubleSpinBox QLineEdit {background-color:#232323;color:#f3f1f8;padding:6px}')

    def choose(self, index):
        path, accepted = QInputDialog.getText(self, 'Import local WAV or MOV audio', 'Paste a local .wav or .mov path (supports ~/):')
        if accepted and path.strip():
            path = path.strip()
            for button in self.buttons:
                button.setEnabled(False)
            self.observations.setPlainText('Analyzing local audio excerpt…')
            self.worker = AnalysisWorker(index, path, self, self.excerpt_start.value(), self.excerpt_duration.value())
            self.worker.result.connect(self._receive)
            self.worker.finished.connect(self._finished)
            self.worker.start()

    def _finished(self):
        for button in self.buttons:
            button.setEnabled(True)
        self.worker.deleteLater()
        self.worker = None

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _receive(self, index, take, error):
        if error:
            self.observations.setPlainText(f'Import failed: {error}\nPrevious takes retained.')
            return False
        self._set_take(index, take)
        return True

    def import_take(self, index, path, start=0., duration=30.):
        try:
            take = analyze(path, start, duration)
        except (OSError, ValueError) as exc:
            self.observations.setPlainText(f'Import failed: {exc}\nPrevious takes retained.')
            return False
        return self._receive(index, take, "")

    def _set_take(self, index, take):
        while len(self.takes) <= index:
            self.takes.append(None)
        self.takes[index] = take
        active = [(i,t) for i,t in enumerate(self.takes) if t is not None]
        for chart in self.charts:
            chart.takes = active
            chart.update()
        self.legend.setText('Purple: take 1 • Gold: take 2\n' + ' • '.join(f'Take {i+1}: {t.name} ({t.duration:.2f} s)' for i,t in enumerate(self.takes) if t))
        self.observations.setPlainText('\n\n'.join(f'Take {i+1}: {observation(t)}' for i,t in enumerate(self.takes) if t) + '\n\n' + comparison(self.takes))
        return True


def main():
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    window = PracticeWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
