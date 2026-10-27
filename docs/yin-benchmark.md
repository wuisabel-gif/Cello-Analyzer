# Synthetic-only pitch benchmark

This exercises the existing `desktop_dashboard.practice.analyze` implementation;
it is not a second detector. It uses deterministic, generated 16-bit PCM WAVs
in a temporary directory, without devices, user recordings, model downloads,
new dependencies or external services. No fixture audio is committed.

Run from the repository root:

```bash
.venv/bin/python -m benchmarks.yin_pitch --json-path /tmp/cello-yin-current.json
.venv/bin/python -m unittest discover -s tests -p test_yin_benchmark.py -v
```

The 21 cases cover C2/G2/D3/A3 open-string frequencies, the advertised 55 Hz
lower edge, higher pitches through A5, second/third harmonics stronger than the
fundamental, three additional sample rates, an amplitude ramp, a tone below the
quiet gate, approximately 20 dB white noise added to a tone, a known pitch
transition, two seeded white-noise signals and silence. Harmonic amplitudes are
explicit in the generator; the fundamental is present in every tonal mixture.

The machine-readable [baseline](yin-baseline.json) was measured on detector
commit `e32f6fa6e79aabf65a76aca4be24bd9a7b1dd71d` (the tree now merged into
main). Error includes wrong-octave estimates without correcting or discarding
them. Coverage is accepted estimates divided by expected voiced scored frames;
rejection is missing estimates divided by expected unvoiced scored frames.
Octave error means absolute error within 50 cents of one octave (1200 cents).
Gross error means any absolute error over 50 cents. These tolerances describe
this benchmark, not validated musical or teaching thresholds.

## Baseline findings

| Signal family | Coverage / rejection | Error on accepted frames |
| --- | --- | --- |
| Open-string sine tones | 100% coverage | Median absolute error 0.03–0.41 cents |
| A4, E5, A5 sine tones | 100% coverage | Median absolute error 2.46, 5.78, 10.15 cents |
| 55 Hz lower edge | 0% coverage | No estimate; zero octave errors does not mean success |
| C2 / D3 stronger second harmonic | 100% coverage | All 141 scored frames per case are octave errors |
| G2 stronger third harmonic | 100% coverage | All 141 scored frames follow the wrong harmonic (~1905 cents error) |
| Silence, two noise seeds, quiet tone | 100% rejection | No accepted pitch |
| Amplitude ramp and stable portions around transition | 100% coverage | No gross or octave errors |

The harmonic failures carry median periodicity scores of about 0.92–0.98.
This demonstrates why periodicity is not a probability of correct fundamental
pitch and why high coverage alone cannot establish accuracy.

Frames are scored at their 80 ms window centers from 0.1–2.9 seconds. The known
transition at 1.5 seconds excludes centers within ±80 ms (9 frames), reported
explicitly in JSON. Boundary and transition estimates are not claimed accurate;
this is not a note-onset, rhythmic timing or score-alignment benchmark.

## Limits

These idealized cases do not represent real cello bow noise, room acoustics,
inharmonicity, polyphony, instrument resonances or microphone processing. The
signal set is small and deterministic. Improvements on it can overfit this set.
A missing/inaudible fundamental can be inherently ambiguous. Synthetic results
must not be presented as real cello accuracy, intonation grades, validated
vibrato measures, physical-technique judgments or an AI teacher assessment.
