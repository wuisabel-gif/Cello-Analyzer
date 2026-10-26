import numpy as np
from PySide6.QtCore import QRectF, QPointF, QThread, Signal, Qt
from PySide6.QtGui import QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit
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
        p.drawText(65, self.height()-7, f'0 s • File-start axis • end {duration:.2f} s')
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

    def __init__(self, index, path, parent):
        super().__init__(parent)
        self.index, self.path = index, path

    def run(self):
        try:
            self.result.emit(self.index, analyze(self.path), '')
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
        note = QLabel('Offline • 16-bit PCM WAV • max 60 s / 32 MB\nPitch relative to A3 (220 Hz), not a target-note grade. Relative RMS is not SPL.\nFile starts are aligned; no score or onset alignment. Short variation is not a validated vibrato assessment.')
        note.setWordWrap(True)
        layout.addWidget(note)
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
        self.setStyleSheet('QWidget {background:#171717;color:#f3f1f8} QPushButton {background:#574064;padding:10px} QTextEdit {background:#232323}')

    def choose(self, index):
        path, _ = QFileDialog.getOpenFileName(self, 'Import local WAV', '', 'WAV (*.wav)')
        if path:
            for button in self.buttons:
                button.setEnabled(False)
            self.observations.setPlainText('Analyzing local WAV…')
            self.worker = AnalysisWorker(index, path, self)
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

    def import_take(self, index, path):
        try:
            take = analyze(path)
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
