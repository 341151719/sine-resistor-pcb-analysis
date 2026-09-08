# Metrics guide v3

## Primary columns

### `synerr_rms_tail_v`

RMS of:

```text
V(SPK) - Rx_command(t) * Iport
```

after the soft-start/settling window. This is the main voltage-domain check that the synthetic impedance relation is being implemented.

### `synerr_norm_rms_tail`

Normalized version of the synthesis error:

```text
rms(synerr) / rms(Rx_command * Iport)
```

Use this to compare cases with different current amplitudes.

### `reff_fit_tail_ohm`

Least-squares total effective resistance for fixed-R cases:

```text
Re + sum(VSPK*Iport)/sum(Iport^2)
```

This is the preferred resistance estimate for `full_einj_fixed_*` cases.

### `reff_pointwise_rms_err_tail_ohm`

Masked point-wise legacy ratio metric. It is useful for debugging but should not be treated as the main pass/fail criterion.

## Safety columns

### `ilim_ratio_tail_pk`

Peak output current divided by the modeled current limit during the evaluation tail. Values much less than 1 indicate current-limit margin.

### `opa548_vsat_max_v`

Simple saturation proxy for the OPA548 surrogate output. It should normally stay near zero.

### `xmax_ratio_pk`

Peak displacement divided by the ±4 mm excursion limit. Values below 1 are mechanically within the modeled linear displacement range.

## Recommended first plots to inspect

1. `full_einj_fixed_r1_f1000.png`
2. `full_einj_fixed_r100_f1000.png`
3. `full_single_sine.png`
4. `full_dual_sine.png`
5. `full_stress_pa5_mod.png`
