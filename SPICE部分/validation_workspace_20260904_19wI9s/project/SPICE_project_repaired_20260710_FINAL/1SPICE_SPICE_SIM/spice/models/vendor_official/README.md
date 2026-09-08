# Official Vendor Model Audit Files

This directory retains the official vendor macro-model source files used for audit:

- `AD633/ad633.cir`
- `OPA548/sbom088c/OPA548.LIB`
- `OPA1656/sbomaw6c/OPA1656.LIB`
- `INA149/sbomc47/ina149.lib`

The corresponding vendor ZIP files are retained where present as source evidence. Redundant vendor example-project files such as schematic projects, symbol libraries, signatures, plots, and PSpice simulation folders have been moved to `archive/vendor_extra/`.

Run from the project root:

```bash
python scripts/prepare_official_models.py
```

The script scans retained `.SUBCKT` definitions, records detected names and pin order, and writes:

```text
spice/models/official_wrapped_models.lib
spice/models/official_model_prepare_report.md
```

Current policy: the official-model path is an audit and wrapper-preparation path. The transient runtime currently uses ngspice-safe surrogate fallback for robust execution. No converted vendor-ngspice copies are retained in the current package.
