"""Deterministic measurement cues; no model, teacher claims or external service."""
import numpy as np


def observation(take):
    valid = np.isfinite(take.pitch)
    coverage = float(valid.mean()) if len(valid) else 0
    if valid.sum() < 15 or coverage < .6:
        return 'No reliable pitch observation: too little periodic audio. Try a clean, single sustained note.'
    if np.ptp(take.pitch[valid]) > 600:
        return 'No reliable pitch observation: large register changes or possible octave errors. Check a single sustained note.'
    # Report only the longest continuous supported interval, never across gaps.
    indices = np.flatnonzero(np.isfinite(take.trend))
    runs = np.split(indices, np.flatnonzero(np.diff(indices) != 1)+1)
    interval = max(runs, key=len)
    if len(interval) < 51:
        return 'No reliable trend observation: need at least one second of continuous supported trend.'
    first, last = interval[0], interval[-1]
    trend = take.trend[interval]
    change = np.median(trend[-10:]) - np.median(trend[:10])
    residual = take.variation[interval]
    spread = np.percentile(residual, 90)-np.percentile(residual, 10)
    return (f'{take.time[first]+take.source_start:.2f}–{take.time[last]+take.source_start:.2f} s (source time): estimated trend changed {change:+.1f} cents '
            f'(end-window medians); short variation had a middle-80% span of {spread:.1f} cents. '
            f'{coverage:.0%} of frames passed the periodicity gate. '
            'Listen back to this interval and repeat with the same setup. '
            'This is a measurement cue, not an intonation or vibrato grade.')


def comparison(takes):
    if len(takes) != 2 or any(t is None for t in takes):
        return 'Import both takes to compare file durations.'
    difference = takes[1].duration-takes[0].duration
    return (f'Analyzed duration only: take 2 is {abs(difference):.2f} s '
            f'{"longer" if difference >= 0 else "shorter"} than take 1. '
            'This includes leading/trailing silence; it does not measure musical timing.')
