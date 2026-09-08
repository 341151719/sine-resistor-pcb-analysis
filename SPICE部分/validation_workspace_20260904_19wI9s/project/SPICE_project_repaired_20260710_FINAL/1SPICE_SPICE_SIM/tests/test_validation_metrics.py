#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validation_metrics import (  # noqa: E402
    ValidationPolicy,
    dynamic_complex_impedance,
    fixed_complex_impedance,
)


def test_fixed_complex_fit_rejects_dc_bias_error() -> None:
    policy = ValidationPolicy()
    fs = 200_000
    f = 1000.0
    t = np.arange(0, 0.05, 1 / fs)
    current = 8e-3 + 1e-3 * np.sin(2 * np.pi * f * t)
    zsynthetic = 0.05 + 0.25j
    # For i=Ipk*sin(wt), multiplication by a complex impedance is formed from
    # the analytic components: real part in phase and imaginary part quadrature.
    carrier_sin = 1e-3 * np.sin(2 * np.pi * f * t)
    carrier_cos = 1e-3 * np.cos(2 * np.pi * f * t)
    voltage = 0.06 + zsynthetic.real * carrier_sin + zsynthetic.imag * carrier_cos
    result = fixed_complex_impedance(t, voltage, current, f, 7.2, 0.01, policy)
    assert result["phasor_status"] == "ok"
    assert abs(result["ztotal_real_ohm"] - 7.25) < 1e-4
    # Sign follows the exp(+jwt) phasor convention used by the fitter.
    assert abs(abs(result["ztotal_imag_ohm"]) - 0.25) < 1e-4

    # The old no-intercept slope is badly biased by DC offsets.
    old = 7.2 + float(np.sum(voltage * current) / np.sum(current * current))
    assert abs(old - result["ztotal_real_ohm"]) > 0.5


def test_dynamic_local_phasor_tracks_resistance_envelope() -> None:
    policy = ValidationPolicy(min_dynamic_windows=8)
    dt = 2e-6
    t = np.arange(0, 0.08, dt)
    fm = 100.0
    fc = 10_000.0
    rt = 50.5 + 30.0 * np.sin(2 * np.pi * fm * t)
    current_ac = 1e-3 * np.sin(2 * np.pi * fc * t)
    current = 5e-3 + current_ac
    voltage = 0.02 + (rt - 7.2) * current_ac
    metrics, rows = dynamic_complex_impedance(t, voltage, current, rt, fc, fm, 7.2, 0.02, policy)
    assert metrics["dynamic_phasor_status"] == "ok"
    assert len(rows) >= 8
    assert metrics["dynamic_p95_abs_real_rel_error"] < 0.03
    assert metrics["dynamic_p95_abs_imag_rel"] < 0.03


if __name__ == "__main__":
    test_fixed_complex_fit_rejects_dc_bias_error()
    test_dynamic_local_phasor_tracks_resistance_envelope()
    print("validation metric tests passed")
