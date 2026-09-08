# Repair notes v2 — full-component loop false current-limit bug

Date: 2026-05-22

## Symptom in uploaded results

The ideal and behavioral cases tracked `Rtarget` correctly, while every `full_*` case showed almost the same current and voltage regardless of the target resistance:

- `full_fixed_r100`, `full_fixed_r20`, `full_fixed_r7p2`, `full_fixed_r5`, `full_fixed_r1` all reported `Iport_pk` near the configured OPA548 current limit.
- `Reff` error was approximately the target value itself, meaning the measured synthesized impedance was near zero instead of tracking the command.
- This cannot be a physical acoustic effect because a 1 Pa pressure input in the ideal/behavioral models only produced milliamps, not ampere-level current-limit behavior.

## Root cause

The v1 surrogate macromodels used behavioral current sources for op-amp and buffer outputs, for example conceptually:

```spice
BOUT OUT 0 I = {(Vtarget - V(OUT))/ROUT}
```

In SPICE, positive current for a source declared as `BOUT OUT 0 I=...` flows from `OUT` to ground, so a positive value *sinks* current and tends to pull `OUT` downward. Therefore the above expression is the wrong polarity for a voltage-output buffer.

Correct polarity is:

```spice
BOUT OUT 0 I = {(V(OUT) - Vtarget)/ROUT}
```

When `Vtarget > V(OUT)`, this expression becomes negative, so current is injected from ground into `OUT`, raising the output node.

The sign error was present in the surrogate output stages of:

- `OPA548_NG_SURR`
- `OPA1656_NG_SURR`
- `INA149_NG_SURR`
- `AD633_NG_SURR`

The result was a false positive-feedback/current-limit condition in the full-component loop.

## What changed

1. Replaced the v1 macro output-stage expressions with corrected current-source polarity.
2. Replaced the previous current-source dominant-pole/slew proxy with simpler voltage-command plus RC-pole blocks to avoid additional current-source sign ambiguity.
3. Kept a copy of the v1 library as `spice/models/ngspice_compatible_macros_faulty_legacy.lib` for reproducibility.
4. Added `FOLLOWERR = VCMD - SPK` and `ILIMRATIO = |Iout|/Ilim` probes to `full_component_template.cir`.
5. Added static polarity regression checks to `scripts/check_project.py`.

## How to verify after repair

Run:

```bash
python scripts/check_project.py
python scripts/run_sweeps.py --clean
```

In `results/all_summary.csv`, the repaired full cases should be judged by these columns:

- `reff_rms_err_tail_ohm` should be close to the behavioral case, not tens of ohms.
- `ilim_ratio_pk` should be far below 1 for the low-pressure baseline cases.
- `follow_error_pk_v` should remain small unless the case intentionally drives saturation.
- `iport_pk_a` should return to the milliamps range for 1 Pa baseline acoustic excitation.

## What this repair does not prove

The included macros are still ngspice-compatible surrogate models, not official thermal/package-accurate vendor models. Before PCB generation or Quilter/KiCad handoff, replace the surrogates with vendor macromodels where licenses allow, then repeat the same sweep set.
