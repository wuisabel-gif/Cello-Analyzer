import unittest
import numpy as np
from benchmarks.yin_pitch import metrics, signals


class BenchmarkMetrics(unittest.TestCase):
    def test_octave_errors_are_scored_without_correction(self):
        result = metrics(np.array([0., 1200., np.nan, np.nan]), np.zeros(4),
                         np.array([True, True, True, False]), np.ones(4, dtype=bool))
        self.assertEqual(result['voiced_coverage'], 2/3)
        self.assertEqual(result['octave_error_frames'], 1)
        self.assertEqual(result['gross_error_frames'], 1)
        self.assertEqual(result['median_abs_cents'], 600)
        self.assertEqual(result['unvoiced_rejection'], 1)

    def test_fixture_ground_truth_and_seed_are_repeatable(self):
        first, second = list(signals()), list(signals())
        self.assertEqual(len(first), 21)
        for a, b in zip(first, second):
            np.testing.assert_array_equal(a.samples, b.samples)
            self.assertLess(np.max(np.abs(a.samples)), 1)
        transition = next(s for s in first if s.transitions)
        self.assertAlmostEqual(transition.frequency[0], 65.4063913251)
        self.assertEqual(transition.frequency[-1], 220)
