import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QEventLoop, QTimer, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from desktop_dashboard.ui.practice_window import PracticeWindow
from synthetic import fixture


class PracticeUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        import shiboken6
        for widget in self.app.topLevelWidgets():
            widget.close()
            shiboken6.delete(widget)
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def test_import_replace_errors_and_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            window = PracticeWindow()
            path = Path(directory)/'SYNTHETIC-steady.wav'
            fixture(path)
            self.assertTrue(window.import_take(1, path))
            self.assertEqual(window.charts[0].takes[0][0], 1)
            self.assertTrue(window.import_take(0, path))
            self.assertTrue(window.import_take(0, path))
            self.assertEqual(len(window.takes), 2)
            self.assertFalse(window.import_take(1, path.with_name('missing.wav')))
            path.write_text('bad')
            self.assertFalse(window.import_take(1, path))
            self.assertIn('Previous takes retained', window.observations.toPlainText())
            for kind in ('silence', 'noise'):
                fixture(path, kind)
                self.assertTrue(window.import_take(1, path))
                self.assertIn('0% of frames', window.observations.toPlainText())
            path = Path(directory)/'SYNTHETIC-vibrato.wav'
            fixture(path, 'vibrato', rate=44100)
            window.import_take(1, path)
            window.show()
            self.app.processEvents()
            window.grab().save(str(Path(__file__).parents[1]/'practice-preview.png'))

    def test_file_dialog_cancel_and_background_import(self):
        window = PracticeWindow()
        with patch('desktop_dashboard.ui.practice_window.QFileDialog.getOpenFileName', return_value=('', '')):
            window.choose(0)
        self.assertEqual(window.takes, [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC.wav'
            fixture(path)
            with patch('desktop_dashboard.ui.practice_window.QFileDialog.getOpenFileName', return_value=(str(path), '')):
                window.choose(0)
            self.assertFalse(window.buttons[0].isEnabled())
            loop = QEventLoop()
            window.worker.finished.connect(loop.quit)
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
            self.app.processEvents()
            self.assertEqual(len(window.takes), 1)
            self.assertTrue(window.buttons[0].isEnabled())

    def test_dashboard_opens_practice(self):
        from desktop_dashboard.ui.main_window import MainWindow
        window = MainWindow()
        window._open_practice()
        self.assertTrue(window.practice_window.isVisible())
        window._stop_sources()
        window.practice_window.close()
        window.close()
