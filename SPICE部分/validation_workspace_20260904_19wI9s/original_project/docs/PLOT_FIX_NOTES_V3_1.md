# v3.1 plot-axis repair notes

This update fixes the problem where many generated figures looked like a nearly flat straight line because one diagnostic trace or startup spike dominated the axis range.

## What changed

1. **Robust y-limits for all plot panels**
   - Plot limits now use percentile-based scaling rather than raw min/max.
   - Rare startup spikes and point-wise `V/I` explosions no longer compress the useful waveform into a line.
   - Raw CSV values and summary metrics are not clipped; clipping is only for figure display.

2. **Tail-only zoom figures**
   - Every case now writes two figures:
     - `<case>.png`: full overview with the tail-start marker.
     - `<case>_tail.png`: steady-state zoom window after soft-start.
   - The tail window is selected from the case frequencies so 1000 Hz and 5000 Hz traces no longer appear as a dense block or straight line.

3. **Safer Reff plotting**
   - `Reff pointwise` remains a diagnostic only.
   - It is masked around current zero crossings and clipped for plot display as:
     `Reff pointwise, masked/interp/clipped`.
   - Use `synerr`, `cmderr`, `followerr`, and `reff_fit_tail_ohm` for conclusions.

4. **Replot without rerunning ngspice**
   - Added `scripts/replot_existing_results.py`.
   - It regenerates PNGs from existing CSV files.

## Commands

Run full simulation and generate repaired figures:

```bash
python scripts/run_sweeps.py --clean
```

Regenerate figures from existing results without ngspice:

```bash
python scripts/replot_existing_results.py
```

Regenerate only injection-case figures:

```bash
python scripts/replot_existing_results.py --case-filter einj
```

## Interpretation reminder

The repaired plots are intended to make the useful waveform visible. They do not change the physics or the numeric metrics. For final judgment, prioritize:

- `synerr_norm_rms_tail`
- `synerr_rms_tail_v`
- `cmderr_rms_tail_v`
- `follow_error_rms_tail_v`
- `reff_fit_tail_ohm` for fixed-resistance injection tests
- `ilim_ratio_tail_pk`
- `xmax_ratio_pk`
