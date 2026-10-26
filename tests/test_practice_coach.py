import tempfile
import unittest
import wave
from pathlib import Path
import numpy as np
from desktop_dashboard.practice import analyze
from desktop_dashboard.practice_coach import observation, comparison
from synthetic import fixture


class PracticeCoach(unittest.TestCase):
    def test_supported_drift_has_timestamp_and_no_grade(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC-drift.wav'
            fixture(path, 'drift')
            take = analyze(path)
            text = observation(take)
            self.assertIn('0.28–2.72 s', text)
            self.assertIn('not an intonation or vibrato grade', text)
            self.assertIn('estimated trend changed +', text)
            take.source_start = 12.5
            self.assertIn('12.78–15.22 s (source time)', observation(take))
            self.assertIn('Analyzed duration only', comparison([take, take]))
            take.duration += .75
            self.assertIn('0.75 s longer', comparison([analyze(path), take]))

    def test_no_result_for_silence_noise_octave_short_and_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'SYNTHETIC.wav'
            for kind in ('silence', 'noise', 'octave'):
                fixture(path, kind)
                self.assertIn('No reliable', observation(analyze(path)))
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
                wav.writeframes(np.zeros(100, dtype='<i2').tobytes())
            self.assertIn('No reliable', observation(analyze(path)))
            fixture(path)
            take = analyze(path)
            take.trend[::20] = np.nan
            self.assertIn('No reliable trend', observation(take))
