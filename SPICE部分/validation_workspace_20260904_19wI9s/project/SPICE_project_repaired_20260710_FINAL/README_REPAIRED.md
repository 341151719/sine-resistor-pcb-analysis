# Repaired active acoustic-impedance SPICE project

This package repairs the simulation acceptance path and documents the MCU control contract. It does not claim that the full 1-100 ohm, 10-1000 Hz dynamic target has passed.

## Quick structural and numerical smoke test

```bash
source /mnt/data/setup_spice_env.sh
./RUN_QUICK_SMOKE.sh
```

## Split fixed-resistance signoff

```bash
source /mnt/data/setup_spice_env.sh
./RUN_FIXED_SIGNOFF_SPLIT.sh
```

Each resistance is simulated separately. The final aggregation returns non-zero if any engineering criterion fails.

## Split dynamic signoff

```bash
source /mnt/data/setup_spice_env.sh
./RUN_DYNAMIC_SIGNOFF_SPLIT.sh
```

Each modulation frequency is simulated separately to limit compute and isolate convergence failures.

## Firmware audit

The supplied archive contains no MCU source. Run the scanner on the real firmware tree:

```bash
python 1SPICE_SPICE_SIM/scripts/audit_firmware.py /path/to/stm32/project --json-out firmware_audit.json
```

No firmware source means `not_auditable`, not pass.

See:

- `1SPICE_SPICE_SIM/REPAIR_NOTES_20260710.md`
- `1SPICE_SPICE_SIM/MCU_CONTROL_CONTRACT.md`
- `1SPICE_SPICE_SIM/validation_policy.json` after a run
