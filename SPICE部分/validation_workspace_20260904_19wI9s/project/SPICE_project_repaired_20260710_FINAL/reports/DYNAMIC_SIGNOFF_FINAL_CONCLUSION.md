# Pure-vendor dynamic signoff final conclusion

## Executive conclusion

The dynamic pure-vendor signoff was completed as a verification activity, but it **does not pass as a full dynamic impedance-tracking signoff** with the present analog forward-path compensation.

What passed:

- All 35 phase-sliced pure-vendor cases completed with TI/ADI raw vendor macromodels and no device-level surrogate fallback.
- The acoustic external-pressure safety/stability set passed: 15/15.
- No tested acoustic dynamic case hit current limit, saturation, or excursion limit.
- The previously required fixes are in place: OPA548 RCL to `N18`, current-sense offset trim, and slow DC servo.

What did not pass:

- Electrical dynamic impedance tracking at `1mA @ 10kHz` carrier passed only 1/20 with the baseline compensation.
- The failure mode is not current limit or displacement; it is phase/reactive error in `Vspk/Iport` under dynamic modulation.

## Baseline dynamic signoff result

- Completed cases: 35/35
- Overall pass: 16/35
- Electrical tracking pass: 1/20
- Acoustic safety pass: 15/15

Median electrical tracking relative error by modulation frequency:

|      |        0 |
|-----:|---------:|
|   10 | 0.195563 |
|  100 | 0.234843 |
| 1000 | 0.446126 |
|   30 | 0.210543 |
|  300 | 0.261579 |

Median electrical imaginary component by modulation frequency, Ω:

|      |       0 |
|-----:|--------:|
|   10 | 22.1397 |
|  100 | 22.6732 |
| 1000 | 11.6715 |
|   30 | 22.4211 |
|  300 | 23.1631 |

## Fast compensation screening

I also screened a non-final compensation variant by reducing the two feedback capacitors:

```spice
C_U4A_F ISIG NFB_A 100p -> 10p
C_U4B_F VCMD NFB_B 220p -> 22p
```

This is **not** kept as the project default, because it is not yet fully signed off. It is useful as root-cause evidence.

- Electrical tracking pass improved from 1/20 to 6/20.
- Low/moderate `fm` median relative error improved strongly.
- `fm=300Hz` and `fm=1000Hz` still fail mainly on p95 relative error and residual imaginary component.

Fast-comp median electrical tracking relative error by modulation frequency:

|      |         0 |
|-----:|----------:|
|   10 | 0.0152437 |
|  100 | 0.0344349 |
| 1000 | 0.444852  |
|   30 | 0.0193578 |
|  300 | 0.095201  |

Fast-comp median electrical imaginary component by modulation frequency, Ω:

|      |       0 |
|-----:|--------:|
|   10 | 4.93579 |
|  100 | 5.14509 |
| 1000 | 8.27188 |
|   30 | 4.99748 |
|  300 | 5.24337 |

## Interpretation

The three requested fixes are effective for stability, DC safety reduction, and fixed-R/safety behavior, but they are not sufficient for complete dynamic impedance tracking. The remaining limitation is the analog forward path bandwidth/phase:

```text
INA149 / OPA1656 current-sense path
+ AD633 multiplier path
+ OPA1656 post-gain path
+ OPA548 follower path
= enough phase lag at 10 kHz carrier to make the synthetic impedance partially reactive.
```

The fast-cap screening proves this: reducing compensation capacitors greatly reduces the imaginary component and relative error, so the root cause is dynamic loop compensation rather than the speaker model or RCL wiring.

## Required next design step to make it pass

To obtain a true pass, the design needs one of these changes:

1. Add a properly compensated phase-lead / bandwidth extension network around the current-sense and post-gain stages, then rerun the same 35-case signoff.
2. Move from open-loop feedforward multiplication to closed-loop impedance servo using `E = Rx(t)*Iport - Vspk`.
3. Move multiplication into MCU/DSP/DAC and keep the pure-vendor signoff for the analog power/sense chain.

The least invasive next attempt is a compensation-design sweep, not another DC trim sweep. The useful sweep dimensions are:

```text
C_U4A_F = 5p / 10p / 22p / 47p / 100p
C_U4B_F = 10p / 22p / 47p / 100p / 220p
optional lead zero across R_U4B_F
carrier = 1k / 5k / 10k / 20k
fm = 10 / 30 / 100 / 300 / 1000Hz
```

## Files

- Baseline report: `PURE_VENDOR_DYNAMIC_SIGNOFF_REPORT.md`
- Baseline signoff table: `dynamic_signoff_table.csv`
- Baseline lock-in summary: `dynamic_lockin_summary.csv`
- Fast compensation screening: `/mnt/data/1SPICE_pure_vendor_dynamic_fastcomp/`
- Repro scripts: `/mnt/data/dynamic_signoff_resume.py`, `/mnt/data/run_dynamic_phase_sliced_signoff.py`
