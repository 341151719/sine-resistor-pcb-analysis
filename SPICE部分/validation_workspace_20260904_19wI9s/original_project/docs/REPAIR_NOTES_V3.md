# Repair notes v3

## Motivation

The v2 project repaired the major wrong-polarity output-current-source issue in the surrogate amplifier macromodels. The uploaded v2 results showed that the false 1.52 A current-limit state disappeared. However, the summary still reported large `Reff` errors in some cases.

Manual inspection showed that those large errors were dominated by the ratio

```text
Reff = Re + V(SPK)/Iport
```

near current zero-crossings. The ratio is numerically ill-conditioned when `Iport` is small and is not a reliable primary pass/fail metric for an acoustically excited, lightly driven system.

## v3 fixes

### 1. Voltage-domain synthesis error

The primary error is now

```text
synerr = V(SPK) - Rx_command(t) * Iport
```

This directly tests the intended synthetic impedance relation without dividing by a near-zero current.

In the full component template:

```spice
B_SYNERR SYNERR 0 V = {V(SPK) - V(RXNODE)*V(IPORT)}
B_CMDERR CMDERR 0 V = {V(VCMD) - V(RXNODE)*V(IPORT)}
```

### 2. Least-squares impedance fit

For fixed-R cases, v3 computes

```text
Rx_fit = sum(VSPK*Iport) / sum(Iport^2)
Reff_fit = Re + Rx_fit
```

This is the correct scalar fit for `VSPK ≈ Rx*Iport` and avoids zero-crossing singularities.

### 3. Masked point-wise Reff

Point-wise `V/I` is retained for plots and diagnostics, but only when

```text
abs(Iport) >= max(50 µA, 5% of tail peak current)
```

The valid fraction is reported as `reff_pointwise_valid_fraction_tail`.

### 4. Soft-start

The target command is now separated into:

- `RDES`: the requested target profile.
- `RXDES`: requested external synthetic impedance.
- `RXNODE`: actual command sent to the analog multiplier after soft-start and filter.
- `RTARGET`: `Re + RXNODE`, the command used for evaluation.

The command path ramps external `Rx` from zero to target:

```spice
BVK_RAW VK_RAW 0 V = {soft(time)*(3.3*V(DAC_R)-0.62)}
```

The acoustic pressure source and electrical injection source are also soft-ramped.

### 5. Electrical current-injection tests

A soft-ramped current source is added at the SPK node:

```spice
B_EINJ 0 SPK I = {soft(time)*ItestAmp*sin(TWOPI*ItestFreq*time)}
```

With `Pamp=0`, these cases directly verify the synthetic impedance loop under a known electrical stimulus.

## Acceptance criteria suggested for v3

For fixed electrical injection tests:

- `abs(reff_fit_err_vs_tail_mean_ohm)` should be small compared with the target.
- `synerr_norm_rms_tail` should be low.
- `ilim_ratio_tail_pk` should be comfortably below 1.
- `opa548_vsat_max_v` should remain 0 or near 0.

For acoustic modulation tests:

- Use `synerr_rms_tail_v` and `synerr_norm_rms_tail` rather than raw point-wise Reff.
- Inspect the plot panel showing `SPK`, `VCMD`, and `Rx*Iport`.
