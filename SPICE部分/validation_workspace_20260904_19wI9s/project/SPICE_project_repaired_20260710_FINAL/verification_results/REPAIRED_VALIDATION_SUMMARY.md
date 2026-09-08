# Repaired SPICE validation summary

## Fixed electrical impedance, 1 mA at 1 kHz

| Target ohm | Re{Z} ohm | Im{Z} ohm | Acceptance | Reason |
|---:|---:|---:|---|---|
| 0.9993 | 1.05369 | +0.341832 | fail | fixed_imag=0.341832ohm>0.1ohm |
| 4.999 | 5.04557 | +0.122007 | pass |  |
| 7.199 | 7.2487 | -0.00787426 | pass |  |
| 20 | 20.0008 | -0.766657 | pass |  |
| 99.99 | 98.8159 | -5.60541 | fail | fixed_imag=5.60541ohm>4.99942ohm |

## Dynamic electrical impedance

Case: `signoff_dynamic_fm100_carrier10k`

- Simulation: `completed`
- Acceptance: `fail`
- Carrier/modulation ratio: `100`
- Valid local phasor windows: `599`
- Median absolute real relative error: `0.217463`
- P95 absolute real relative error: `0.6981`
- Median absolute imaginary relative value: `0.451762`
- P95 absolute imaginary relative value: `1.74919`
- Reason: `dynamic_p95_real_rel=0.6981>0.1; dynamic_p95_imag_rel=1.74919>0.1`

## Control and firmware audit

- SPICE control path: pass. MCU/DAC generates the target trajectory; AD633 performs target-times-current synthesis. Diagnostic instantaneous V/I is downstream and not fed back.
- Firmware: not auditable. No MCU source files are present in the supplied archive.
- Quick smoke: pass.

## Interpretation

The repaired scripts correctly distinguish numerical completion from engineering acceptance. They do not convert the existing dynamic-tracking limitation into a false pass.
