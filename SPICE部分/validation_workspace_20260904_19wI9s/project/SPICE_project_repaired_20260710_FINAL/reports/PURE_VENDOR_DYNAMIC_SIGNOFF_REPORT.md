# Pure-vendor dynamic signoff report — phase-sliced

## Scope

- Pure vendor model policy: `official_pure_raw_vendor_macromodels_no_device_surrogate`; device-level surrogate fallback is not used.
- Implemented fixes: OPA548 `RCL` referenced to `N18`; current-sense input offset trim; slow DC servo at AD633 Z node with low-resistance scheduling.
- Additional diagnostic-only stabilisation: pointwise `B_REFF` now uses smooth bounded division; signoff uses postprocessed lock-in metrics, not this diagnostic node.
- Dynamic target: `Rtarget(t)=clip(50.5 + 49.5 sin(2π fm t + phase), 1, 100) Ω`, `fm=10/30/100/300/1000Hz`.
- Electrical tracking is phase-sliced at low, high, positive-slope midpoint, and negative-slope midpoint. Carrier current injection is `1mA @ 10kHz`.
- Acoustic safety is phase-sliced at low, high, and positive-slope midpoint. External pressure is `1Pa @ 300Hz`, no electrical injection.

## Acceptance criteria

- Electrical local lock-in: median relative error ≤ 12%, p95 relative error ≤ 35%, median imaginary component ≤ 8.0Ω.
- Safety: |mean(Iport)| ≤ 12.0mA, `ilim_ratio_tail_pk≤0.5`, `xmax_ratio_pk≤0.5`, `opa548_vsat_max≤0.2V`.

## Result

- Completed cases: 35/35.
- Overall pass: 16/35.
- Electrical tracking pass: 1/20.
- Acoustic safety pass: 15/15.

## Curated signoff table

| case                                 | class                       | status   | overall_pass   | safety_pass   |   track_pass |   valid_windows |   median_abs_rel_err |   p95_abs_rel_err |   median_abs_imag_ohm |   dc_iport_tail_mA |   ilim_ratio_tail_pk |   xmax_ratio_pk |   opa548_vsat_max_v |
|:-------------------------------------|:----------------------------|:---------|:---------------|:--------------|-------------:|----------------:|---------------------:|------------------:|----------------------:|-------------------:|---------------------:|----------------:|--------------------:|
| dyn_einj_fm10_low_carrier10k         | electrical_dynamic_tracking | ok       | True           | True          |            1 |              45 |            0.0895127 |          0.141148 |               2.03829 |           -8.18282 |           0.00666028 |     0.00220552  |                   0 |
| dyn_einj_fm10_mid_up_carrier10k      | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.236122  |          0.238708 |              37.6494  |           -6.97565 |           0.00481423 |     0.000773167 |                   0 |
| dyn_einj_fm10_high_carrier10k        | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.240502  |          0.242729 |              42.1825  |           -6.91558 |           0.00473055 |     0.000950201 |                   0 |
| dyn_einj_fm10_mid_down_carrier10k    | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.155003  |          0.184696 |               6.63003 |           -8.87234 |           0.00678451 |     0.00117191  |                   0 |
| dyn_einj_fm30_low_carrier10k         | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.229356  |          0.24401  |              32.0105  |           -7.18008 |           0.00528338 |     0.00101877  |                   0 |
| dyn_einj_fm30_mid_up_carrier10k      | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.243058  |          0.245985 |              45.4392  |           -6.90375 |           0.00477439 |     0.00092569  |                   0 |
| dyn_einj_fm30_high_carrier10k        | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.191731  |          0.223955 |              12.8317  |           -7.98924 |           0.00657713 |     0.000864662 |                   0 |
| dyn_einj_fm30_mid_down_carrier10k    | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.180104  |          1.49584  |               2.86899 |           -7.00482 |           0.00619822 |     0.00226789  |                   0 |
| dyn_einj_fm100_low_carrier10k        | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.216964  |          1.47667  |               9.38256 |           -6.57626 |           0.00729413 |     0.00144885  |                   0 |
| dyn_einj_fm100_mid_up_carrier10k     | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.239409  |          2.42786  |              29.5834  |           -6.16309 |           0.00729026 |     0.00144343  |                   0 |
| dyn_einj_fm100_high_carrier10k       | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.234822  |          0.247684 |              34.6615  |           -7.29928 |           0.0067698  |     0.00119214  |                   0 |
| dyn_einj_fm100_mid_down_carrier10k   | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.234865  |          1.20685  |              15.763   |           -6.28652 |           0.00735944 |     0.00119433  |                   0 |
| dyn_einj_fm300_low_carrier10k        | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.257853  |          2.11857  |              22.8426  |           -6.07168 |           0.00717784 |     0.00102757  |                   0 |
| dyn_einj_fm300_mid_up_carrier10k     | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.26323   |          0.93551  |              24.2412  |           -5.76184 |           0.00711461 |     0.00102558  |                   0 |
| dyn_einj_fm300_high_carrier10k       | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.265786  |          2.18667  |              23.333   |           -6.05619 |           0.00713422 |     0.000978647 |                   0 |
| dyn_einj_fm300_mid_down_carrier10k   | electrical_dynamic_tracking | ok       | False          | True          |            0 |              45 |            0.259928  |          2.28253  |              22.9933  |           -6.06972 |           0.00710403 |     0.00102329  |                   0 |
| dyn_einj_fm1000_low_carrier10k       | electrical_dynamic_tracking | ok       | False          | True          |            0 |              32 |            0.438649  |          3.69752  |              11.5747  |           -7.08789 |           0.00688966 |     0.000633449 |                   0 |
| dyn_einj_fm1000_mid_up_carrier10k    | electrical_dynamic_tracking | ok       | False          | True          |            0 |              26 |            0.526416  |          2.18236  |              14.3255  |           -7.23423 |           0.00697208 |     0.000646312 |                   0 |
| dyn_einj_fm1000_high_carrier10k      | electrical_dynamic_tracking | ok       | False          | True          |            0 |              32 |            0.453603  |          3.10998  |               7.99549 |           -7.10248 |           0.00689125 |     0.000643723 |                   0 |
| dyn_einj_fm1000_mid_down_carrier10k  | electrical_dynamic_tracking | ok       | False          | True          |            0 |              32 |            0.414227  |          0.917879 |              11.7682  |           -7.23901 |           0.00693438 |     0.000644477 |                   0 |
| dyn_acoustic_fm10_low_fa300_pa1      | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -8.77167 |           0.00616319 |     0.00219967  |                   0 |
| dyn_acoustic_fm10_high_fa300_pa1     | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.96712 |           0.00463998 |     0.00101837  |                   0 |
| dyn_acoustic_fm10_mid_up_fa300_pa1   | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.94322 |           0.00460757 |     0.000811805 |                   0 |
| dyn_acoustic_fm30_low_fa300_pa1      | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.98511 |           0.00481596 |     0.00107894  |                   0 |
| dyn_acoustic_fm30_high_fa300_pa1     | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -7.21904 |           0.00602936 |     0.00166958  |                   0 |
| dyn_acoustic_fm30_mid_up_fa300_pa1   | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -7.05372 |           0.00491159 |     0.000972126 |                   0 |
| dyn_acoustic_fm100_low_fa300_pa1     | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.55047 |           0.00653634 |     0.00131183  |                   0 |
| dyn_acoustic_fm100_high_fa300_pa1    | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.82774 |           0.00685532 |     0.00141313  |                   0 |
| dyn_acoustic_fm100_mid_up_fa300_pa1  | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.51333 |           0.00629381 |     0.00141893  |                   0 |
| dyn_acoustic_fm300_low_fa300_pa1     | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.43944 |           0.00657228 |     0.000956082 |                   0 |
| dyn_acoustic_fm300_high_fa300_pa1    | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -6.11907 |           0.0065138  |     0.00109661  |                   0 |
| dyn_acoustic_fm300_mid_up_fa300_pa1  | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -5.97877 |           0.00662826 |     0.00107578  |                   0 |
| dyn_acoustic_fm1000_low_fa300_pa1    | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -7.0728  |           0.006498   |     0.000705839 |                   0 |
| dyn_acoustic_fm1000_high_fa300_pa1   | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -7.09048 |           0.00651634 |     0.000704158 |                   0 |
| dyn_acoustic_fm1000_mid_up_fa300_pa1 | acoustic_dynamic_safety     | ok       | True           | True          |          nan |             nan |          nan         |        nan        |             nan       |           -7.05704 |           0.00648402 |     0.000701354 |                   0 |

## Interpretation

Not all cases passed. Failed rows identify remaining limitations: either lock-in impedance tracking error, residual DC bias/safety, or missing/ngspice failure. Do not claim full dynamic signoff until those rows are corrected.

## Boundary of this signoff

A long `fm=10Hz` full-cycle pure-vendor transient was attempted and ngspice completed 90068 rows, but long full-cycle vendor macro postprocessing hit the execution time limit. The phase-sliced method covers endpoint and maximum-slope operating points with short vendor-macro transients and is the practical method for expensive TI/ADI macro-model regression.