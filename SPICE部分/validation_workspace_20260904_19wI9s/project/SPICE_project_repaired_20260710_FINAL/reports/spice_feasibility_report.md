# SPICE feasibility test report

Test date: 2026-07-07
Runtime: Linux x86_64 sandbox, Python 3.13.5
Uploaded packages tested:

- `/mnt/data/ngspice_runtime_linux_x86_64.zip`
- `/mnt/data/spice_python_cp313_linux.zip`

## Result

Feasible for baseline SPICE simulation and Python automation.

The following tests passed:

1. `ngspice` executable launch and version check
2. dynamic library dependency check with `ldd`
3. command-line transient analysis
4. DC operating point analysis
5. AC small-signal analysis
6. binary raw output generation
7. raw parsing with `spicelib`
8. PySpice import and direct `libngspice.so` transient simulation after the stderr handling patch
9. XSPICE code-model path smoke test using `-D xspice_enabled` with a normal RC transient run

## Observed versions

- ngspice: 42
- PySpice: 1.5
- numpy: 2.2.6
- scipy: 1.16.3

## Key numeric checks

- CLI transient RC: `No. of Data Rows : 181`
- DC divider operating point: `v(out) = 2.500000e+00`
- AC RC sweep: `No. of Data Rows : 61`
- raw/spicelib: traces `['time', 'v(in)', 'v(out)', 'i(vin)']`, 181 points
- PySpice transient: 181 points, final `v(out) = 0.004976582241281845`

## Required patches / environment setup

The runtime was initialized under:

- `/mnt/data/spice_runtime`
- `/mnt/data/spice_wheelhouse`
- `/mnt/data/spice_site`
- `/mnt/data/spice_work`
- `/mnt/data/spice_logs`

The environment script is:

```bash
source /mnt/data/setup_spice_env.sh
```

The `spinit` code-model path was patched from the system path to:

```text
/mnt/data/spice_runtime/lib/ngspice
```

PySpice 1.5 initially failed with:

```text
PySpice.Spice.NgSpice.Shared.NgSpiceCommandError: Command 'run' failed
```

The cause was PySpice treating ngspice stderr text such as `Using SPARSE 1.3 as Direct Linear Solver` as fatal. After patching `PySpice/Spice/NgSpice/Shared.py` to treat `Using SPARSE` and `Using KLU` as non-fatal, the PySpice shared-library test passed.

## Caveats

- PySpice still prints `Unsupported Ngspice version 42`; this is a compatibility warning from PySpice 1.5, not a blocking failure in the tested RC transient case.
- OSDI Verilog-A compact model simulation was not fully tested because no real `.osdi` model file was uploaded. The ngspice OSDI command exists, but model-level feasibility requires a concrete `.osdi` library plus its expected `.model` syntax.
- I did not certify a real XSPICE behavioral model circuit. I confirmed the code-model paths are patched and an `xspice_enabled` ngspice run does not break a normal RC transient circuit.

## Re-run command

```bash
bash /mnt/data/test_spice_all_actual.sh
```
