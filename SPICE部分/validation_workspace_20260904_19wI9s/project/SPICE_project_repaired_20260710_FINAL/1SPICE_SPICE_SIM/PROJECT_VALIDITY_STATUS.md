# Project Validity Status

Date: 2026-06-17

## Current Valid Scope

This project is valid as a surrogate-based ngspice transient validation of the active synthesized impedance / negative-impedance acoustic membrane concept.

The retained numerical sweep results in `results/all_summary.csv` demonstrate the behavior of the repaired ngspice-safe surrogate macro model chain under the recorded sweep conditions. They are not claimed to be pure TI/ADI/STM vendor-macro transient simulation results.

## Interpretation Boundary for `results/all_summary.csv`

The summary table includes explicit provenance columns:

- `model_lib`
- `runtime_model_policy`

For the current retained results:

- `model_lib = official`
- `runtime_model_policy = official_audit_with_ngspice_surrogate_fallback`

This means the run used the official-model preparation and wrapper path, while the transient execution used ngspice-safe surrogate fallback for robust execution. The existing numeric columns should be interpreted as surrogate-model validation results, not as pure official vendor macro results.

## Official-Model Path: Completed

The project currently supports an official-model audit path that can:

- scan retained official/vendor model files;
- identify relevant `.SUBCKT` names;
- record pin-order assumptions in `spice/models/official_model_pin_map.json`;
- generate `spice/models/official_wrapped_models.lib`;
- generate write-only official-path netlists with `scripts/run_sweeps.py --model-lib official`;
- document when ngspice-safe surrogate fallback is used for transient robustness.

The vendor macro files are retained for audit and future replacement work.

## Official-Model Path: Not Yet Completed

The project has not completed a full transient sweep proven to run only on pure official TI/ADI/STM vendor macro models.

The current wrapper path intentionally keeps `ngspice_fallback_to_surrogate` enabled for devices whose vendor PSpice macro syntax or convergence behavior is not yet robust under local ngspice transient execution.

Do not describe the current numerical results as:

- pure official macro transient sweep results;
- full vendor macro validation;
- PCBA-ready proof from vendor macromodels alone.

## PCBA / KiCad / Quilter / Hardware Limits

The present results are useful for validating the active synthesized impedance concept and for preserving a reproducible ngspice experiment record. They are not a substitute for:

- vendor-macro-only transient convergence signoff;
- device thermal and current-limit validation against datasheets;
- PCB parasitic, layout, stability, and protection analysis;
- KiCad / Quilter implementation verification;
- bench measurements on the final amplifier, sensing, and loudspeaker hardware.

Before PCBA release or hardware claims, the official vendor macro path should be completed without surrogate fallback where possible, and the same sweep set should be rerun with logs and provenance preserved.

## Dynamic Validation Update

On 2026-06-17, a full 34-case dynamic transient rerun was completed in a temporary validation copy of the cleaned project. The rerun used:

```text
python scripts\run_sweeps.py --clean --model-lib official
```

The rerun produced 34 rows with `status = ok`, `model_lib = official`, and `runtime_model_policy = official_audit_with_ngspice_surrogate_fallback`. No new failure rows were produced, and no fatal ngspice log patterns were found in the rerun case logs.

This dynamic rerun supports the current surrogate-based transient validation claim. It still does not establish pure official vendor-macro transient validation, because the official-model path intentionally uses ngspice-safe surrogate fallback for robust execution.

## Conclusion

This project is valid as a surrogate-based ngspice transient validation of the active synthesized impedance concept. The included official vendor macro files are audited and mapped, but the current dynamic sweep results are not claimed to be pure vendor-macro transient results. The official-model path currently uses an ngspice-safe surrogate fallback for robust transient execution.
