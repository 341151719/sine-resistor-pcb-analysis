# Historical report notice

Reports in this directory predate the 2026-07-10 acceptance repair. They remain historical engineering evidence, but `status=ok` may mean only that ngspice completed.

New authoritative runs must use the repaired runner and distinguish `simulation_status` from `acceptance_status`. Fixed impedance is now a DC-aware complex phasor; dynamic impedance is evaluated with local carrier phasors. Old point-wise V/I data is diagnostic only.
