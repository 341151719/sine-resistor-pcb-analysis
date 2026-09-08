#!/usr/bin/env python3
"""Numerically robust SPICE acceptance metrics.

Design rules implemented here:
- Never use instantaneous v(t)/i(t) as a control or primary acceptance metric.
- Fixed impedance is estimated from affine sinusoidal fits with a DC intercept.
- Dynamic impedance is estimated from local complex carrier phasors with a
  first-order envelope term, then compared against Rtarget at each window.
- Simulation completion and engineering acceptance are separate states.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ValidationPolicy:
    fixed_real_rel_tol: float = 0.05
    fixed_real_abs_tol_ohm: float = 0.10
    fixed_imag_rel_tol: float = 0.05
    fixed_imag_abs_tol_ohm: float = 0.10
    dynamic_p95_real_rel_tol: float = 0.10
    dynamic_p95_imag_rel_tol: float = 0.10
    min_dynamic_carrier_ratio: float = 10.0
    dc_iport_abs_limit_a: float = 0.020
    ilim_ratio_limit: float = 0.80
    xmax_ratio_limit: float = 0.80
    vsat_limit_v: float = 0.10
    min_phasor_current_a: float = 20e-6
    min_fixed_cycles: int = 8
    max_fixed_cycles: int = 40
    dynamic_window_cycles: float = 1.0
    dynamic_step_cycles: float = 0.5
    min_dynamic_windows: int = 12

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_xy(*arrays: np.ndarray) -> tuple[np.ndarray, ...]:
    converted = [np.asarray(a, dtype=float).ravel() for a in arrays]
    if not converted:
        return tuple()
    n = min(len(a) for a in converted)
    converted = [a[:n] for a in converted]
    mask = np.ones(n, dtype=bool)
    for a in converted:
        mask &= np.isfinite(a)
    return tuple(a[mask] for a in converted)


def _weighted_lstsq(A: np.ndarray, y: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    if weights is not None:
        w = np.sqrt(np.asarray(weights, dtype=float))
        A = A * w[:, None]
        y = y * w
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef


def affine_sine_phasor(
    time_s: np.ndarray,
    signal: np.ndarray,
    freq_hz: float,
    *,
    weights: np.ndarray | None = None,
) -> dict[str, float | complex]:
    """Fit x(t)=dc+a*cos(wt)+b*sin(wt), returning phasor a-j*b."""
    t, x = _finite_xy(time_s, signal)
    if t.size < 8 or not math.isfinite(freq_hz) or freq_hz <= 0:
        return {"ok": False, "dc": float("nan"), "phasor": complex(np.nan, np.nan), "rms_residual": float("nan"), "n": int(t.size)}
    if weights is not None:
        weights = np.asarray(weights, dtype=float).ravel()[: len(np.asarray(time_s).ravel())]
        finite_mask = np.isfinite(np.asarray(time_s, float).ravel()) & np.isfinite(np.asarray(signal, float).ravel())
        weights = weights[finite_mask]
    w = 2.0 * np.pi * freq_hz
    A = np.column_stack([np.ones_like(t), np.cos(w * t), np.sin(w * t)])
    coef = _weighted_lstsq(A, x, weights)
    fit = A @ coef
    residual = x - fit
    return {
        "ok": True,
        "dc": float(coef[0]),
        "phasor": complex(float(coef[1]), float(-coef[2])),
        "rms_residual": float(np.sqrt(np.mean(residual * residual))),
        "n": int(t.size),
    }


def local_affine_envelope_phasor(
    time_s: np.ndarray,
    signal: np.ndarray,
    freq_hz: float,
    center_s: float,
) -> dict[str, float | complex]:
    """Fit a carrier whose DC and I/Q envelope are locally linear.

    x(t)=d0+d1*tau + (a0+a1*tau)cos(wt) + (b0+b1*tau)sin(wt)
    The returned center phasor is a0-j*b0. This suppresses bias from a rapidly
    changing target resistance without requiring instantaneous division.
    """
    t, x = _finite_xy(time_s, signal)
    if t.size < 12:
        return {"ok": False, "dc": float("nan"), "phasor": complex(np.nan, np.nan), "n": int(t.size), "rms_residual": float("nan")}
    tau = t - float(center_s)
    wt = 2.0 * np.pi * freq_hz * t
    c = np.cos(wt)
    s = np.sin(wt)
    A = np.column_stack([np.ones_like(t), tau, c, s, tau * c, tau * s])
    # Hann weighting reduces edge sensitivity while preserving the center value.
    phase = (t - t.min()) / max(float(t.max() - t.min()), 1e-15)
    weights = np.maximum(0.05, 0.5 - 0.5 * np.cos(2 * np.pi * phase))
    coef = _weighted_lstsq(A, x, weights)
    fit = A @ coef
    residual = x - fit
    return {
        "ok": True,
        "dc": float(coef[0]),
        "phasor": complex(float(coef[2]), float(-coef[3])),
        "n": int(t.size),
        "rms_residual": float(np.sqrt(np.mean(residual * residual))),
    }


def fixed_complex_impedance(
    time_s: np.ndarray,
    voltage_v: np.ndarray,
    current_a: np.ndarray,
    freq_hz: float,
    series_resistance_ohm: float,
    tail_start_s: float,
    policy: ValidationPolicy,
) -> dict[str, Any]:
    t, v, i = _finite_xy(time_s, voltage_v, current_a)
    if t.size < 16 or freq_hz <= 0:
        return {"phasor_status": "not_evaluated", "phasor_reason": "insufficient_data_or_invalid_frequency"}
    t_end = float(np.max(t))
    available_cycles = max(0.0, (t_end - tail_start_s) * freq_hz)
    cycles = int(min(policy.max_fixed_cycles, math.floor(available_cycles)))
    if cycles < policy.min_fixed_cycles:
        return {
            "phasor_status": "not_evaluated",
            "phasor_reason": f"only_{available_cycles:.3g}_tail_cycles_available",
            "phasor_cycles": available_cycles,
        }
    start = max(float(tail_start_s), t_end - cycles / freq_hz)
    m = t >= start
    vf = affine_sine_phasor(t[m], v[m], freq_hz)
    inf = affine_sine_phasor(t[m], i[m], freq_hz)
    ip = complex(inf["phasor"])
    vp = complex(vf["phasor"])
    if not vf["ok"] or not inf["ok"] or abs(ip) < policy.min_phasor_current_a:
        return {
            "phasor_status": "not_evaluated",
            "phasor_reason": "carrier_current_too_small_or_fit_failed",
            "carrier_current_peak_a": abs(ip),
        }
    zsynthetic = vp / ip
    ztotal = series_resistance_ohm + zsynthetic
    return {
        "phasor_status": "ok",
        "phasor_frequency_hz": float(freq_hz),
        "phasor_cycles": int(cycles),
        "carrier_current_peak_a": float(abs(ip)),
        "carrier_voltage_peak_v": float(abs(vp)),
        "iport_dc_fit_a": float(inf["dc"]),
        "vspk_dc_fit_v": float(vf["dc"]),
        "i_fit_residual_rms_a": float(inf["rms_residual"]),
        "v_fit_residual_rms_v": float(vf["rms_residual"]),
        "zsynthetic_real_ohm": float(zsynthetic.real),
        "zsynthetic_imag_ohm": float(zsynthetic.imag),
        "ztotal_real_ohm": float(ztotal.real),
        "ztotal_imag_ohm": float(ztotal.imag),
        "ztotal_mag_ohm": float(abs(ztotal)),
        "ztotal_phase_deg": float(np.degrees(np.angle(ztotal))),
    }


def dynamic_complex_impedance(
    time_s: np.ndarray,
    voltage_v: np.ndarray,
    current_a: np.ndarray,
    target_ohm: np.ndarray,
    carrier_hz: float,
    modulation_hz: float,
    series_resistance_ohm: float,
    tail_start_s: float,
    policy: ValidationPolicy,
) -> tuple[dict[str, Any], list[dict[str, float]]]:
    t, v, i, rt = _finite_xy(time_s, voltage_v, current_a, target_ohm)
    if t.size < 32 or carrier_hz <= 0 or modulation_hz <= 0:
        return ({"dynamic_phasor_status": "not_evaluated", "dynamic_phasor_reason": "invalid_frequency_or_insufficient_data"}, [])
    ratio = carrier_hz / modulation_hz
    window = policy.dynamic_window_cycles / carrier_hz
    step = policy.dynamic_step_cycles / carrier_hz
    half = 0.5 * window
    first = max(float(tail_start_s) + half, float(t.min()) + half)
    last = float(t.max()) - half
    if last <= first:
        return ({"dynamic_phasor_status": "not_evaluated", "dynamic_phasor_reason": "tail_too_short", "carrier_to_mod_ratio": ratio}, [])

    centers = np.arange(first, last + 0.25 * step, step)
    rows: list[dict[str, float]] = []
    for center in centers:
        m = (t >= center - half) & (t <= center + half)
        if int(np.sum(m)) < 16:
            continue
        vf = local_affine_envelope_phasor(t[m], v[m], carrier_hz, center)
        inf = local_affine_envelope_phasor(t[m], i[m], carrier_hz, center)
        if not vf["ok"] or not inf["ok"]:
            continue
        ip = complex(inf["phasor"])
        if abs(ip) < policy.min_phasor_current_a:
            continue
        z = series_resistance_ohm + complex(vf["phasor"]) / ip
        rtarget = float(np.interp(center, t, rt))
        scale = max(abs(rtarget), 1.0)
        rows.append({
            "time_s": float(center),
            "rtarget_ohm": rtarget,
            "ztotal_real_ohm": float(z.real),
            "ztotal_imag_ohm": float(z.imag),
            "real_error_ohm": float(z.real - rtarget),
            "real_rel_error": float((z.real - rtarget) / scale),
            "imag_rel": float(z.imag / scale),
            "carrier_current_peak_a": float(abs(ip)),
            "iport_dc_fit_a": float(inf["dc"]),
            "vspk_dc_fit_v": float(vf["dc"]),
        })

    if len(rows) < policy.min_dynamic_windows:
        return ({
            "dynamic_phasor_status": "not_evaluated",
            "dynamic_phasor_reason": f"only_{len(rows)}_valid_windows",
            "carrier_to_mod_ratio": float(ratio),
            "dynamic_valid_windows": int(len(rows)),
        }, rows)

    real_rel = np.abs([r["real_rel_error"] for r in rows])
    imag_rel = np.abs([r["imag_rel"] for r in rows])
    imag_abs = np.abs([r["ztotal_imag_ohm"] for r in rows])
    metrics = {
        "dynamic_phasor_status": "ok" if ratio >= policy.min_dynamic_carrier_ratio else "low_carrier_ratio",
        "dynamic_phasor_reason": "" if ratio >= policy.min_dynamic_carrier_ratio else "carrier_to_modulation_ratio_below_policy",
        "carrier_to_mod_ratio": float(ratio),
        "dynamic_valid_windows": int(len(rows)),
        "dynamic_median_abs_real_rel_error": float(np.median(real_rel)),
        "dynamic_p95_abs_real_rel_error": float(np.percentile(real_rel, 95)),
        "dynamic_median_abs_imag_rel": float(np.median(imag_rel)),
        "dynamic_p95_abs_imag_rel": float(np.percentile(imag_rel, 95)),
        "dynamic_median_abs_imag_ohm": float(np.median(imag_abs)),
        "dynamic_p95_abs_imag_ohm": float(np.percentile(imag_abs, 95)),
        "dynamic_rtarget_min_ohm": float(min(r["rtarget_ohm"] for r in rows)),
        "dynamic_rtarget_max_ohm": float(max(r["rtarget_ohm"] for r in rows)),
        "dynamic_ztotal_real_min_ohm": float(min(r["ztotal_real_ohm"] for r in rows)),
        "dynamic_ztotal_real_max_ohm": float(max(r["ztotal_real_ohm"] for r in rows)),
    }
    return metrics, rows


def safety_acceptance(summary: dict[str, Any], policy: ValidationPolicy) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    dc = abs(float(summary.get("iport_dc_tail_a", 0.0)))
    ilim = float(summary.get("ilim_ratio_tail_pk", 0.0))
    xmax = float(summary.get("xmax_ratio_pk", 0.0))
    vsat = float(summary.get("opa548_vsat_max_v", 0.0))
    if math.isfinite(dc) and dc > policy.dc_iport_abs_limit_a:
        reasons.append(f"dc_iport={dc:.6g}A>{policy.dc_iport_abs_limit_a:.6g}A")
    if math.isfinite(ilim) and ilim > policy.ilim_ratio_limit:
        reasons.append(f"ilim_ratio={ilim:.6g}>{policy.ilim_ratio_limit:.6g}")
    if math.isfinite(xmax) and xmax > policy.xmax_ratio_limit:
        reasons.append(f"xmax_ratio={xmax:.6g}>{policy.xmax_ratio_limit:.6g}")
    if math.isfinite(vsat) and vsat > policy.vsat_limit_v:
        reasons.append(f"vsat_margin_violation={vsat:.6g}V>{policy.vsat_limit_v:.6g}V")
    return not reasons, reasons


def apply_acceptance(summary: dict[str, Any], policy: ValidationPolicy) -> dict[str, Any]:
    """Attach acceptance_status without changing simulation_status."""
    out = dict(summary)
    safety_ok, reasons = safety_acceptance(out, policy)
    out["safety_pass"] = bool(safety_ok)

    target_mean = float(out.get("rtarget_tail_mean_ohm", float("nan")))
    fixed_status = out.get("phasor_status")
    dyn_status = out.get("dynamic_phasor_status")

    if fixed_status == "ok":
        real_error = abs(float(out["ztotal_real_ohm"]) - target_mean)
        imag_error = abs(float(out["ztotal_imag_ohm"]))
        real_tol = max(policy.fixed_real_abs_tol_ohm, policy.fixed_real_rel_tol * max(abs(target_mean), 1.0))
        imag_tol = max(policy.fixed_imag_abs_tol_ohm, policy.fixed_imag_rel_tol * max(abs(target_mean), 1.0))
        out["fixed_real_error_ohm"] = real_error
        out["fixed_real_tolerance_ohm"] = real_tol
        out["fixed_imag_tolerance_ohm"] = imag_tol
        if real_error > real_tol:
            reasons.append(f"fixed_real_error={real_error:.6g}ohm>{real_tol:.6g}ohm")
        if imag_error > imag_tol:
            reasons.append(f"fixed_imag={imag_error:.6g}ohm>{imag_tol:.6g}ohm")
        out["acceptance_class"] = "fixed_electrical_impedance"
    elif dyn_status in {"ok", "low_carrier_ratio"}:
        p95_real = float(out.get("dynamic_p95_abs_real_rel_error", float("inf")))
        p95_imag = float(out.get("dynamic_p95_abs_imag_rel", float("inf")))
        ratio = float(out.get("carrier_to_mod_ratio", 0.0))
        if ratio < policy.min_dynamic_carrier_ratio:
            reasons.append(f"carrier_ratio={ratio:.6g}<{policy.min_dynamic_carrier_ratio:.6g}")
        if p95_real > policy.dynamic_p95_real_rel_tol:
            reasons.append(f"dynamic_p95_real_rel={p95_real:.6g}>{policy.dynamic_p95_real_rel_tol:.6g}")
        if p95_imag > policy.dynamic_p95_imag_rel_tol:
            reasons.append(f"dynamic_p95_imag_rel={p95_imag:.6g}>{policy.dynamic_p95_imag_rel_tol:.6g}")
        out["acceptance_class"] = "dynamic_electrical_impedance"
    else:
        out["acceptance_class"] = "safety_only"

    out["acceptance_pass"] = bool(not reasons)
    out["acceptance_status"] = "pass" if not reasons else "fail"
    out["acceptance_reasons"] = "; ".join(reasons)
    return out
