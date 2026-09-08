# Active acoustic-impedance SPICE project — repaired acceptance path

This project models an externally excited electrodynamic membrane with an active synthetic series impedance. The MCU/DAC generates the requested resistance trajectory; the analog INA149/OPA1656/AD633/OPA548 path performs current-proportional voltage synthesis.

The project does **not** use instantaneous `V(t)/I(t)` as a real-time control variable. Point-wise V/I remains a diagnostic trace only.

## What was repaired

- Fixed impedance is estimated as a complex phasor with fitted DC intercepts.
- Dynamic impedance uses local complex carrier phasors with first-order envelope terms.
- Simulation completion and engineering acceptance are separate fields.
- Failed simulations return exit code 2; failed acceptance returns exit code 3.
- Model-library availability is checked before execution.
- Expensive runs can be split by resistance or modulation frequency.
- Firmware and SPICE control-path audit tools are included.

See `REPAIR_NOTES_20260710.md` and `MCU_CONTROL_CONTRACT.md`.

## Environment

The supplied package contains the project and vendor models, not the ngspice runtime. In the ChatGPT sandbox:

```bash
source /mnt/data/setup_spice_env.sh
```

Python dependencies are listed in `requirements.txt`.

## Structural check and unit tests

```bash
python scripts/check_project.py
python tests/test_validation_metrics.py
```

## One-case smoke regression

From the package root:

```bash
./RUN_QUICK_SMOKE.sh
```

This runs the 7.2-ohm, 1 kHz current-injection case and requires both numerical completion and acceptance pass.

## Fixed resistance signoff, split by resistance

```bash
./RUN_FIXED_SIGNOFF_SPLIT.sh
```

The script runs 1, 5, 7.2, 20, and 100 ohms as separate ngspice jobs, then aggregates them. A final non-zero exit is expected whenever any engineering criterion fails.

Manual example:

```bash
python scripts/run_sweeps.py \
  --clean \
  --results-dir split_fixed_r1 \
  --suite fixed-signoff \
  --case-filter signoff_fixed_r1_ \
  --model-lib official-pure \
  --allow-acceptance-fail \
  --no-plots \
  --no-case-csv
```

## Dynamic signoff, split by modulation frequency

```bash
./RUN_DYNAMIC_SIGNOFF_SPLIT.sh
```

The five jobs use `fm = 10, 30, 100, 300, 1000 Hz` with a 10 kHz carrier. This is intentionally split to isolate convergence and compute cost.

## Reprocess an existing case

```bash
python scripts/postprocess_case.py results_dir/cases/case_name
```

This applies the repaired metrics without rerunning ngspice. Use `--write-derived-csv` or `--plots` only when needed.

## Output interpretation

Primary columns in `all_summary.csv`:

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

Do not use `reff_pointwise` as a primary pass/fail value.

## Firmware audit

No firmware source was included in the supplied archive, so actual MCU behavior is currently `not_auditable`. Run the scanner on the real source tree:

```bash
python scripts/audit_firmware.py /path/to/firmware --json-out firmware_audit.json
```

A static pass is not a substitute for runtime control-flow review, but any instantaneous voltage/current division hit must be reviewed before hardware testing.
