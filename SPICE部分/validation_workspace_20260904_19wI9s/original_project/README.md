# Active acoustic impedance v3.3 — ≤5 Pa acoustic-stress rerun project

This is a complete rerun-oriented project. It keeps the v3.2 axis-planned plotting fixes and removes all acoustic stress tests above 5 Pa from the default sweep suite.

## What is changed

- Robust `YLIM` planning for every panel using percentile-based display limits.
- Separate overview and steady-state tail zoom figures for every case.
- Pointwise `Reff` is plotted as a clipped diagnostic only; raw CSV values are preserved.
- `run_sweeps.py --clean` regenerates all netlists, reruns ngspice, parses fresh data, and creates new figures. It does not patch old CSV files.
- Optional `replot_existing_results.py` can redraw already-ran CSV outputs, but by default it does not rewrite CSV files.
- Acoustic stress cases are now limited to `Pamp = 1 Pa` and `Pamp = 5 Pa`; higher-pressure acoustic stress cases are not generated.

## Run full simulation from scratch

```bash
pip install -r requirements.txt
python scripts/check_project.py
python scripts/run_sweeps.py --clean
```

## Generate netlists only, without ngspice

```bash
python scripts/run_sweeps.py --clean --write-only
```

## Run only electrical-injection cases

```bash
python scripts/run_sweeps.py --clean --case-filter einj
```

## Optional: redraw existing results only

```bash
python scripts/replot_existing_results.py
```

This optional helper is not the main path. The main path is always `run_sweeps.py --clean`.

## Read figures

For conclusions, prioritize:

- `synerr_norm_rms_tail`
- `synerr_rms_tail_v`
- `cmderr_rms_tail_v`
- `follow_error_rms_tail_v`
- `reff_fit_tail_ohm` for fixed-resistance injection tests
- `ilim_ratio_tail_pk`
- `xmax_ratio_pk`

Do not use `Reff pointwise` as the primary success criterion. It is a masked/interpolated/clipped diagnostic for visualization only.


## v3.3 acoustic-stress scope

The default sweep suite intentionally excludes all acoustic stress cases with `Pamp > 5 Pa`.
Remaining acoustic stress cases are:

- `full_stress_pa1_fixed1ohm`
- `full_stress_pa1_mod`
- `full_stress_pa5_fixed1ohm`
- `full_stress_pa5_mod`

This does not change the electrical-injection cases, baseline modulation cases, or acoustic frequency sweep cases.
