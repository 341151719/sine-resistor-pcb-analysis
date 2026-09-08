# TI/ADI pure vendor macro transient signoff status

## Scope

This work converts the uploaded `1SPICE_SPICE_SIM` project from an `official audit + surrogate fallback` path to a strict `official-pure` path for the four device macromodels used by the full chain:

- ADI AD633 multiplier: raw `spice/models/vendor_official/AD633/ad633.cir`
- TI OPA548 power op amp: raw `spice/models/vendor_official/OPA548/sbom088c/OPA548.LIB`
- TI OPA1656 audio op amp: raw `spice/models/vendor_official/OPA1656/sbomaw6c/OPA1656.LIB`
- TI INA149 difference amplifier: raw `spice/models/vendor_official/INA149/sbomc47/ina149.lib`

No device-level surrogate fallback is used in the `official-pure` wrapper. The only remaining local block is `DAC_STM32G431_SURR`, which is a command/control waveform source rather than a TI/ADI analog macromodel.

## Implemented files

- `spice/models/official_pure_rawps_wrapped_models.lib`
- patched `scripts/run_sweeps.py`
  - adds `--model-lib official-pure`
  - emits per-case `.spiceinit` containing `set ngbehavior=ps`
  - uses raw vendor files instead of statically converted VSWITCH files
  - adds numerical-only convergence options for vendor PSpice macros under ngspice
- `/mnt/data/evaluate_official_pure_rawps_wrappers.py`
- `/mnt/data/build_official_pure_rawps.py`
- `/mnt/data/1SPICE_official_pure/wrapper_eval/wrapper_eval_summary.csv`
- `/mnt/data/1SPICE_official_pure/official_pure_full_chain_smoke_summary.csv`

## Key technical correction

The earlier static `vendor_official_ngspice` conversion path was not sufficient for signoff. In particular, the INA149 model includes PSpice `VSWITCH` constructs. Static conversion to ngspice `SW(VT,VH)` produced transient initial-point failures or an incorrect saturated output. Running the raw vendor include under ngspice PSpice compatibility mode (`set ngbehavior=ps`) fixes the INA149 wrapper test.

Therefore the correct ngspice path is:

```spice
* .spiceinit in each case directory
set ngbehavior=ps
```

and the model library should include the raw vendor files:

```spice
.include "vendor_official/AD633/ad633.cir"
.include "vendor_official/OPA548/sbom088c/OPA548.LIB"
.include "vendor_official/OPA1656/sbomaw6c/OPA1656.LIB"
.include "vendor_official/INA149/sbomc47/ina149.lib"
```

## Single-device wrapper transient results

All four official-pure device wrappers pass transient smoke tests.

| Part | Status | Measured | Expected |
|---|---|---:|---|
| AD633 | pass | 0.607297037 V | 0.45–0.75 V |
| OPA548 | pass | 1.00260631 V | 0.70–1.30 V |
| OPA1656 | pass | 1.00049697 V | 0.80–1.30 V |
| INA149 | pass | 0.100036935 V | 0.05–0.15 V |

This means the raw TI/ADI macromodels can be loaded and can run transient smoke cases in the current ngspice environment.

## Full-chain official-pure smoke results

The full chain now runs to completion under `--model-lib official-pure`, but the impedance-synthesis performance does not yet pass. These are execution-pass but metric-fail results.

| Case | Status | Target mean Ω | Fitted Reff Ω | Error Ω | Main issue |
|---|---|---:|---:|---:|---|
| `full_einj_fixed_r7p2_f1000` | ngspice ok | 7.198579 | 0.000132 | -7.198447 | synthetic loop collapses to near-zero effective impedance |
| `full_fixed_r7p2` | ngspice ok | 7.198579 | 0.004178 | -7.194401 | same near-zero effective impedance |
| `full_fixed_r1` | ngspice ok | 0.999262 | 0.004174 | -0.995088 | does not synthesize target 1 Ω |
| `full_fixed_r100` | ngspice ok | 99.988350 | 7.385041 | -92.603309 | cannot synthesize high target impedance |

The `status=ok` field only means ngspice completed and output data were parsed. It is not a signoff pass. The metric columns show that the current full-loop design is not yet validated with pure TI/ADI device macromodels.

## Current conclusion

`official-pure` infrastructure is now implemented and the four official device macromodel wrappers pass single-device transient tests.

Full-chain pure vendor transient signoff is not complete. The current full-chain official-pure runs complete, but fail the impedance performance target. The likely next engineering task is not downloading more models; it is redesigning/tuning the analog chain for the real vendor macro behavior, especially the INA149/OPA1656/OPA548 loop gain, compensation, and command scaling under closed-loop operation.

## Recommended next steps

1. Add an internal probe case for each stage of the full loop:
   - INA149 output `VSENSE` versus `SPK-DRV`
   - OPA1656 current-sense gain `ISIG/VSENSE`
   - AD633 output `MUL = ISIG*VK/10`
   - post-gain output `VCMD/MUL`
   - OPA548 follower error `VCMD-SPK`

2. Run these stage-probe cases under both surrogate and official-pure libraries and compare stage gain/phase.

3. Reduce loop bandwidth and add explicit compensation before attempting the 10–1000 Hz modulation signoff matrix.

4. Use split execution for all heavy work:
   - first fixed `Rtarget = 7.2 Ω`
   - then fixed `1 Ω`, `5 Ω`, `20 Ω`, `100 Ω`
   - then single-sine `fm = 10, 30, 100, 300, 1000 Hz`
   - then dual-sine cases
   - then acoustic-frequency cases

5. For vendor-native signoff, export the local subcircuits into PSpice for TI / Cadence PSpice for the TI devices and LTspice for ADI-device-local checks. The Linux sandbox can do ngspice compatibility signoff; it cannot run the Windows GUI vendor-native tools directly.

## Upload/download status

No additional model file is needed for the current ngspice official-pure path. The required raw AD633, OPA548, OPA1656, and INA149 model files are already present in the uploaded project.

If strict vendor-native signoff is required, upload one of the following after running externally:

- PSpice for TI project/netlist/log/output for the TI-device local chain; or
- LTspice `.asc/.cir/.raw/.log` local checks for AD633 or any ADI-specific subchain; or
- a Cadence PSpice exported netlist and transient output for the whole chain if you have a licensed environment.
