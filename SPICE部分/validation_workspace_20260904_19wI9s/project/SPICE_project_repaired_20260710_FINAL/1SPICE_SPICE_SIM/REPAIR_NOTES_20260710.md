# SPICE acceptance and control-path repair — 2026-07-10

## Repaired defects

1. The old fixed-resistance estimator used a zero-intercept scalar slope, `sum(v*i)/sum(i*i)`. Device-macro DC offsets could corrupt a correct 7.2-ohm result into approximately 0.057 ohm.
2. Fixed impedance now uses separate affine sinusoidal fits for voltage and current, including DC intercepts, and reports complex total impedance.
3. Dynamic current-injection cases now use local complex carrier fits with first-order I/Q envelope terms. Instantaneous V/I remains diagnostic only.
4. `simulation_status` and `acceptance_status` are separate. A completed ngspice run is no longer reported as an engineering pass.
5. The runner returns exit code 2 for simulation/post-processing failures and exit code 3 for acceptance failures. `--allow-acceptance-fail` is available only for exploratory sweeps.
6. `simulation_failures.csv`, `acceptance_failures.csv`, and `validation_policy.json` are generated.
7. Missing model-library paths are detected before simulation. The packaged pure-vendor wrapper is the default.
8. Expensive regressions can be split by fixed resistance or modulation frequency. `--no-plots` and `--no-case-csv` reduce post-processing cost.
9. Project/control-path and firmware audit scripts were added.

## Verified repaired results

Pure-vendor 1 mA, 1 kHz electrical-injection checks:

| Target | Complex total impedance | Acceptance |
|---:|---:|---|
| 1 ohm | approximately 1.0537 + j0.3418 ohm | fail: reactive component exceeds policy |
| 7.2 ohm | approximately 7.2487 - j0.00787 ohm | pass |
| 100 ohm | approximately 98.8159 - j5.6054 ohm | fail: reactive component exceeds policy |

The failures above are engineering results, not script failures. The repaired scripts distinguish them correctly.

A dynamic 1-100-ohm, fm=100 Hz, 1 kHz-carrier case was reprocessed with the repaired local complex estimator and failed with large p95 real and imaginary relative errors. This confirms that the previous dynamic-signoff limitation remains; the repair does not hide it.

## Exit codes

```text
0: all selected simulations and acceptance checks passed
2: ngspice or post-processing failure
3: simulations completed, but one or more acceptance checks failed
4: firmware audit requested but no firmware source was supplied
```

## Authoritative outputs

Use `all_summary.csv` columns:

```text
simulation_status
acceptance_status
acceptance_class
acceptance_reasons
ztotal_real_ohm
ztotal_imag_ohm
dynamic_p95_abs_real_rel_error
dynamic_p95_abs_imag_rel
```

Do not use point-wise `reff_pointwise` or netlist `B_REFF` as a primary pass/fail metric.
