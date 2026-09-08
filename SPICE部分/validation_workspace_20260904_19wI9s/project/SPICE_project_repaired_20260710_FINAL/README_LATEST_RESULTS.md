> **2026-07-10 repair notice:** The acceptance and complex-impedance calculations have been replaced. Historical numeric reports below are retained for context only. Use `README_REPAIRED.md`, `1SPICE_SPICE_SIM/REPAIR_NOTES_20260710.md`, and `verification_results/` for current interpretation.

# 1SPICE_SPICE_SIM latest pure-vendor package — 2026-07-07

## 1. What this package contains

This is the latest SPICE project package after the pure-vendor debug and PCB-fix discussion. It contains:

- `1SPICE_SPICE_SIM/`: latest runnable project files.
- `1SPICE_SPICE_SIM/spice/circuits/full_component_template.cir`: latest full-chain template.
- `1SPICE_SPICE_SIM/scripts/run_sweeps.py`: latest runner with the new trim/servo/output-stability parameters exposed.
- `1SPICE_SPICE_SIM/spice/models/official_pure_rawps_wrapped_models.lib`: pure-vendor wrapper library.
- `1SPICE_SPICE_SIM/spice/models/vendor_official/`: raw vendor macromodel files included from the original project archive.
- `reports/`: result reports and PCB-decision tables from the previous validation work.
- `RUN_QUICK_SMOKE.sh`: quick smoke regression script.

This package does not include the ngspice runtime or Python wheelhouse. In the ChatGPT sandbox those are separate files:

- `ngspice_runtime_linux_x86_64.zip`
- `spice_python_cp313_linux.zip`

## 2. Included circuit changes

The current full-component template includes these changes and hooks:

1. **OPA548 RCL fix**: `RCL ILIM N18`, not ground.
2. **Current-sense offset trim**: `VOS_I_TRIM` subtracts input-referred current-sense offset before the OPA1656 sense amplifier.
3. **Slow DC servo**: low-pass/integrating `IPORT` path injects bounded correction into AD633 `Z` node.
4. **Trim/servo scheduling**: `FIXW(RTARGET)` fades trim/servo action outside the low-resistance region.
5. **U4A/U4B compensation exposed**: `C_U4A_F`, `C_U4B_F` are parameters, not hard-coded-only values.
6. **Lead-lag placeholders**: optional `R_U4A_LEAD/C_U4A_LEAD` and `R_U4B_LEAD/C_U4B_LEAD` branches are present and default off.
7. **OPA548 output stability hooks**: optional `RISO_OUT` and Zobel `RZOBEL/CZOBEL` path are present and default near-off.
8. **More stable Reff diagnostic**: diagnostic `B_REFF` uses an epsilon-regularized expression to avoid zero-current singularities.

## 3. Current confirmed status

### Confirmed effective

- SPICE runtime feasibility: ngspice, raw output, spicelib, and PySpice paths were validated earlier.
- Pure-vendor wrapper smoke tests: AD633, OPA548, OPA1656, and INA149 were made runnable under ngspice compatibility mode.
- OPA548 RCL reference correction is mandatory and effective.
- Current-sense offset trim is effective, especially for low target resistance.
- Slow DC servo is effective for reducing low-resistance DC bias, but it is not yet a final all-range bias solution.
- U4A/U4B compensation reduction is directionally effective for dynamic tracking, but not enough for complete dynamic signoff.
- Acoustic dynamic safety cases passed in previous validation.

### Not yet signoff-passed

- Full pure-vendor dynamic impedance tracking is **not** fully signed off.
- Previous dynamic signoff result: electrical dynamic tracking passed only `1/20` baseline cases; fast-compensation screening improved to `6/20`, but still did not pass all cases.
- Final U4A/U4B compensation values are not frozen.
- Lead-lag values, Zobel values, VCMD clamp threshold, servo gain/bandwidth, and trim scheduling still require board-level and SPICE iteration.

## 4. Important numeric findings from previous validation

- With RCL corrected, fixed-R AC Reff recovered approximately to:
  - target `1Ω` -> about `1.05Ω`
  - target `7.2Ω` -> about `7.25Ω`
  - target `100Ω` -> about `99Ω`
- Current-sense trim + slow DC servo reduced low-R DC bias, e.g. `Rtarget=1Ω` improved from roughly `42mA` to roughly `3.6mA` in the earlier curated test.
- `Rtarget=7.2Ω` and `100Ω` still retained mA-level DC bias, so the servo is useful but not final.
- Dynamic tracking failure is dominated by feedforward phase/bandwidth error, not by gross OPA548 saturation, current limit, or speaker excursion.

## 5. PCB decision summary

Hard changes:

1. Connect OPA548 RCL to `-18V/N18`, not ground.
2. Add current-sense trim injection point.
3. Add AD633 `Z` trim/servo injection point.
4. Make U4A/U4B feedback capacitors replaceable.
5. Reserve U4A/U4B lead-lag DNP branches.
6. Reserve OPA548 output Riso and Zobel footprints.
7. Add test points: SPK, DRV/PA_OUT, IPORT, VSENSE, VSENSE_TRIM, ISIG, VK, MUL, ZSERVO, IPDC, VCMD, ILIM, supply rails.

Do not freeze yet:

- U4A/U4B final compensation values.
- Lead-lag RC values.
- DC servo gain/bandwidth/limit.
- VCMD clamp threshold.
- Rtarget minimum clamp.
- Whether AD633 remains final or is replaced by digital multiplication / closed-loop impedance servo.

## 6. How to run

From a shell where ngspice is already available:

```bash
cd <package-root>
./RUN_QUICK_SMOKE.sh
```

Or manually:

```bash
cd <package-root>/1SPICE_SPICE_SIM
python scripts/run_sweeps.py --clean --results-dir results_smoke_fixed_r7p2 --case-filter full_fixed_r7p2 --model-lib official-pure
```

For the ChatGPT sandbox environment, initialize ngspice first using the existing `/mnt/data/setup_spice_env.sh` if present:

```bash
source /mnt/data/setup_spice_env.sh
```

## 7. Interpretation warning

The package is the latest **engineering debug and PCB-fix baseline**, not a final passed dynamic signoff. It is suitable for guiding PCB revisions and for continuing SPICE iterations. It should not be represented as final production signoff until the dynamic tracking matrix passes with the chosen compensation/servo values.
