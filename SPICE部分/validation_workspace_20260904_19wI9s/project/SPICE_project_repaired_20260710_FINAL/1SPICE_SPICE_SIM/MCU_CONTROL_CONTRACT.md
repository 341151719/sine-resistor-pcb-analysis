# MCU control contract

## Required runtime role

The MCU/DAC is permitted to generate only the bounded target-resistance trajectory:

```text
Rtarget(t) in [1 ohm, 100 ohm]
Rx(t) = Rtarget(t) - Re_est
```

The real-time impedance synthesis path is:

```text
measured current -> analog scale -> AD633 multiply by Rx command -> VCMD -> OPA548
```

The firmware must not implement a fast feedback loop based on instantaneous:

```text
R_est(t) = Vspk(t) / Iport(t)
```

because Iport crosses zero, the port impedance is complex, and division noise/phase error can enter the power loop.

## Permitted MCU measurements

The MCU may sample voltage and current for telemetry, logging, slow calibration, RMS protection, temperature estimation, and offline/slow lock-in impedance estimation. Any division must occur only after coherent windowing or complex phasor extraction, with current-amplitude qualification.

## Required protections

Firmware should independently supervise current, output saturation, DC current, temperature/power integral, target bounds, and target slew rate. A protection decision must not be based on a single instantaneous V/I sample.

## Audit status of supplied package

No C/C++/assembly/STM32 project files were supplied. Therefore the actual MCU firmware is not auditable from this archive. `scripts/audit_firmware.py` is included for the firmware source tree when available. A `not_auditable` result is not a pass.
