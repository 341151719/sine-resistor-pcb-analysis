# Web/source check summary

These notes are for model-selection traceability. They are not a redistribution of vendor models.

- TI confirms OPA548 PSpice/TINA models are available and unencrypted on the web.
- The OPA548 datasheet documents the adjustable output-current limit equation and capacitive-load drive considerations.
- Analog Devices documents AD633 as a complete four-quadrant multiplier with output relation `W = (X1-X2)(Y1-Y2)/10 + Z`.
- TI documents INA149 as a high-common-mode difference amplifier with 500 kHz bandwidth.
- TI documents OPA1656 as a high-bandwidth audio op amp with 53 MHz GBW and 100 mA output current capability.

Because vendor model downloads can require license acceptance, this project does not bundle proprietary macro files. Use `scripts/fetch_vendor_models.py` as a source checklist and replace the surrogate subcircuits locally.
