# v3.2 axis-planned rerun project

This project is intended to regenerate the simulation outputs from ngspice, not to patch old CSV files.

## Main rerun path

```bash
pip install -r requirements.txt
python scripts/check_project.py
python scripts/run_sweeps.py --clean
```

`run_sweeps.py --clean` removes `results/`, regenerates all case netlists, runs ngspice, parses fresh `.dat` output, writes new CSV/summary files, and generates repaired PNG figures.

## Plot-axis planning

The previous figures often looked like straight lines because rare startup spikes or pointwise `V/I` explosions dominated raw min/max limits. v3.2 fixes this at plotting time only; numeric CSV values and metrics remain unmodified.

### Shared x-axis logic

- Overview figure `<case>.png`: full simulation time range.
- Tail figure `<case>_tail.png`: steady-state tail window after soft-start.
- Tail duration is selected from the actual excitation/modulation frequencies:
  - slow modulation: keep enough time to see the trend;
  - high-frequency injection: show several final cycles instead of a dense block.

### Y-axis logic by panel

1. Resistance panel:
   - shows `R desired`, `R command`, `Rx command`, and clipped diagnostic `Reff pointwise`;
   - includes reference levels around `-10`, `0`, `1`, `7.2`, `100`, `110 Ω`;
   - uses robust percentile limits to avoid current-zero spikes.

2. Voltage synthesis panel:
   - shows `SPK`, `DRV`, `VCMD`, `Rx*Iport`;
   - uses symmetric voltage limits centered around zero.

3. Current panel:
   - shows `Iport` and the threshold used for reliable pointwise Reff;
   - uses symmetric current limits.

4. Error panel:
   - shows `synerr`, `cmderr`, `followerr`;
   - uses tight symmetric limits so microvolt/millivolt error is visible.

5. Mechanical panel:
   - shows velocity and displacement in mm;
   - uses symmetric limits.

6. Safety/diagnostic panel:
   - shows clipped `Reff-Rcmd`, `|x|/xmax`, saturation proxy, and current-limit ratio;
   - robust scaling prevents the diagnostic Reff trace from hiding safety curves.

## Replot helper

`python scripts/replot_existing_results.py` is provided only for already-ran results. By default it does not rewrite existing CSV files. Use `--update-derived-csv` only when explicitly needed.
