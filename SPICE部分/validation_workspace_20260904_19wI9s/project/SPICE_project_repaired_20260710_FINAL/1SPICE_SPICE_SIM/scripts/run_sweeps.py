#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run ngspice sweeps for the active acoustic impedance project.

v3 changes:
  1) Soft-started command and acoustic pressure to remove t=0 artifacts.
  2) Electrical current-injection tests with Pamp=0.
  3) Robust metrics: voltage-domain synthesis error, least-squares impedance fit,
     and masked point-wise Reff. Legacy V/I Reff is retained only as a diagnostic.

v3.1 plot-fix changes:
  4) Robust x/y axis limits for all generated PNGs.
  5) Per-case tail-only zoom plots to avoid visually compressed straight-line traces.
  6) Clipped diagnostic Reff plotting; raw CSV values are preserved.

v3.3 Pa-limited sweep changes:
  7) Acoustic stress cases above 5 Pa are removed from the default rerun suite.
     Only Pamp=1 Pa and Pamp=5 Pa stress tests are generated.

v4 acceptance repair:
  8) Fixed impedance uses DC-aware complex phasor fitting.
  9) Dynamic impedance uses local carrier phasors with linear envelope terms.
 10) Simulation completion and engineering acceptance are separate states.
 11) Non-zero exit codes are returned for simulation or acceptance failures.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from validation_metrics import (
    ValidationPolicy,
    apply_acceptance,
    dynamic_complex_impedance,
    fixed_complex_impedance,
)

ROOT = Path(__file__).resolve().parents[1]
NGSPICE_BIN = os.getenv("NGSPICE_BIN", "ngspice")
DEFAULT_MODEL_LIB = str((ROOT / "spice" / "models" / "official_pure_rawps_wrapped_models.lib").resolve())
MODEL_LIB = os.getenv("SPICE_MODEL_LIB", DEFAULT_MODEL_LIB)
MODEL_LIB_CHOICE = "custom" if os.getenv("SPICE_MODEL_LIB") else "official-pure"
RUNTIME_MODEL_POLICY = "custom_model_lib_unclassified" if os.getenv("SPICE_MODEL_LIB") else "official_pure_raw_vendor_macromodels_no_device_surrogate"
POLICY = ValidationPolicy()
SAVE_CASE_CSV = True
GENERATE_PLOTS = True
RESULTS = ROOT / "results"
CASES = RESULTS / "cases"
TEMPLATES = ROOT / "spice" / "circuits"

# Project policy for this v3.3 package: do not generate acoustic stress tests above 5 Pa.
STRESS_PRESSURES_PA = [1, 5]


@dataclass
class SpeakerTS:
    Re: float = 7.2
    Le: float = 0.2e-3
    Bl: float = 4.6
    Mms: float = 5.7e-3
    fs: float = 90.0
    Qms: float = 2.29
    Sd: float = 50e-4
    XMAX: float = 4e-3

    @property
    def w0(self) -> float:
        return 2 * math.pi * self.fs

    @property
    def Cms(self) -> float:
        return 1 / (self.Mms * self.w0 * self.w0)

    @property
    def Rms(self) -> float:
        return self.w0 * self.Mms / self.Qms

    @property
    def Kms(self) -> float:
        return 1 / self.Cms


@dataclass
class SimConfig:
    # Target profile: Rdes = clip(R0 + A1*sin(...) + A2*sin(...), RMIN, RMAX)
    R0: float = 50.5
    A1: float = 49.5
    fm1: float = 100.0
    ph1: float = 0.0
    A2: float = 0.0
    fm2: float = 317.0
    ph2: float = 0.0
    RMIN: float = 1.0
    RMAX: float = 100.0

    # Acoustic pressure excitation.
    Pamp: float = 1.0
    fa: float = 120.0

    # Electrical injection current, injected from ground into SPK.
    ItestAmp: float = 0.0
    ItestFreq: float = 1000.0

    # Soft-start. During the ramp, external Rx is ramped from 0 to Rx_des.
    TSTART: float = 5e-3
    TRAMP: float = 5e-3

    # Transient settings.
    tstop: float = 0.05
    tstep: float = 2e-6

    # Implementation parameters.
    RSH: float = 0.1
    RCL: float = 33.2e3
    IOUT: float = 1.52
    RSNUB: float = 4.7
    CSNUB: float = 47e-9

    # Hardware-realism extensions. Defaults are intentionally near-ideal so the
    # historical case set remains comparable.
    RDRV_PAR: float = 1e-6
    LDRV_PAR: float = 1e-12
    RSPK_PAR: float = 1e-6
    LSPK_PAR: float = 1e-12
    RSPEAKER_SERIES: float = 1e-6
    RSPK_SHORT: float = 1e12
    RSH_SCALE: float = 1.0

    # Latest pure-vendor PCB-fix parameters.
    # RCL is already wired to N18 in the full-component template.
    VOS_I_TRIM: float = -0.496092e-3
    DC_SERVO_ENABLE: float = 1.0
    DC_SERVO_FC: float = 2.0
    DC_SERVO_K: float = 0.2
    DC_SERVO_LIMIT: float = 0.5
    DC_SERVO_C: float = 1e-6
    FIX_SCHED_ENABLE: float = 1.0
    FIX_SCHED_FULL: float = 7.2
    FIX_SCHED_OFF: float = 30.0

    # Dynamic-feedforward compensation. These remain tunable PCB values.
    C_U4A_F: float = 100e-12
    C_U4B_F: float = 220e-12
    R_U4A_LEAD: float = 1e12
    C_U4A_LEAD: float = 1e-15
    R_U4B_LEAD: float = 1e12
    C_U4B_LEAD: float = 1e-15

    # Output stabilization hooks. Defaults keep the old path almost unchanged;
    # PCB should provide Riso and Zobel footprints for hardware tuning.
    RISO_OUT: float = 1e-6
    RZOBEL: float = 1e12
    CZOBEL: float = 100e-9
    REFF_EPS: float = 1e-14


def sf(x: float) -> str:
    return f"{float(x):.12g}"


def safe(x) -> str:
    return str(x).replace("-", "m").replace(".", "p").replace("+", "")


def mapping(spk: SpeakerTS, cfg: SimConfig, datafile: str) -> dict[str, str]:
    d = {k: sf(v) for k, v in asdict(spk).items()}
    d.update({k: sf(v) for k, v in asdict(cfg).items()})
    d["DATAFILE"] = datafile
    d["MODEL_INCLUDE"] = MODEL_LIB
    return d


def render(template: str, spk: SpeakerTS, cfg: SimConfig, datafile: str) -> str:
    txt = template
    for k, v in mapping(spk, cfg, datafile).items():
        txt = txt.replace(f"__{k}__", v)
    if "__" in txt:
        raise ValueError("Unreplaced template marker remains in rendered netlist")
    return txt


def model_metadata() -> dict[str, str]:
    return {
        "model_lib": MODEL_LIB_CHOICE,
        "runtime_model_policy": RUNTIME_MODEL_POLICY,
    }


def check_ngspice() -> str:
    exe = shutil.which(NGSPICE_BIN)
    if not exe:
        raise FileNotFoundError(
            f"ngspice not found. Install ngspice or set NGSPICE_BIN. Current={NGSPICE_BIN!r}"
        )
    r = subprocess.run([NGSPICE_BIN, "-v"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)
    return exe


def read_wrdata(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", engine="python")
    df.columns = [str(c).lower().strip() for c in df.columns]
    drop = []
    seen = set()
    for c in df.columns:
        if c.startswith("time.") or c.startswith("scale.") or c == "index" or c.startswith("unnamed"):
            drop.append(c)
        elif c in seen:
            drop.append(c)
        else:
            seen.add(c)
    if drop:
        df = df.drop(columns=drop)
    if "time" not in df.columns:
        raise RuntimeError(f"No time column in wrdata output: {path}")
    return df


def finite(a) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    return arr[np.isfinite(arr)]


def rms(a) -> float:
    b = finite(a)
    return float(np.sqrt(np.mean(b * b))) if b.size else float("nan")


def amin(a) -> float:
    b = finite(a)
    return float(np.min(b)) if b.size else float("nan")


def amax(a) -> float:
    b = finite(a)
    return float(np.max(b)) if b.size else float("nan")


def amean(a) -> float:
    b = finite(a)
    return float(np.mean(b)) if b.size else float("nan")


def _finite_concat(series_list: Iterable) -> np.ndarray:
    vals = []
    for s in series_list:
        if s is None:
            continue
        try:
            arr = np.asarray(s, dtype=float).ravel()
        except Exception:
            continue
        arr = arr[np.isfinite(arr)]
        if arr.size:
            vals.append(arr)
    if not vals:
        return np.array([], dtype=float)
    return np.concatenate(vals)


def robust_ylim(series_list: Iterable, *, include: Iterable[float] = (),
                qlo: float = 1.0, qhi: float = 99.0,
                pad: float = 0.10, min_span: float = 1e-9,
                symmetric: bool = False, hard: tuple[float | None, float | None] | None = None) -> tuple[float, float] | None:
    """Return readable y-limits that ignore rare spikes but keep important reference values.

    This is intentionally a plotting-only operation. CSV values and summary metrics are not clipped.
    """
    arr = _finite_concat(series_list)
    inc = _finite_concat([list(include)]) if include else np.array([], dtype=float)
    if arr.size == 0 and inc.size == 0:
        return None
    if arr.size:
        lo = float(np.nanpercentile(arr, qlo))
        hi = float(np.nanpercentile(arr, qhi))
    else:
        lo = hi = 0.0
    if inc.size:
        lo = min(lo, float(np.min(inc)))
        hi = max(hi, float(np.max(inc)))
    if not math.isfinite(lo) or not math.isfinite(hi):
        return None
    if symmetric:
        m = max(abs(lo), abs(hi), min_span / 2)
        lo, hi = -m, m
    span = hi - lo
    if span < min_span:
        center = 0.5 * (lo + hi)
        span = max(min_span, abs(center) * 0.2, 1e-6)
        lo, hi = center - 0.5 * span, center + 0.5 * span
    else:
        extra = span * pad
        lo, hi = lo - extra, hi + extra
    if hard is not None:
        h0, h1 = hard
        if h0 is not None:
            lo = max(lo, h0)
        if h1 is not None:
            hi = min(hi, h1)
        if lo >= hi:
            return None
    return lo, hi


def _apply_ylim(ax, series_list: Iterable, **kwargs) -> None:
    lim = robust_ylim(series_list, **kwargs)
    if lim is not None:
        ax.set_ylim(*lim)


def _tail_focus_window_ms(df: pd.DataFrame, cfg: SimConfig | None = None) -> tuple[float, float]:
    t = df["time"].to_numpy(float)
    t0 = float(np.nanmin(t))
    t1 = float(np.nanmax(t))
    tail_start = float(df["tail_start_s"].iloc[0]) if "tail_start_s" in df.columns else 0.5 * t1
    tail_start = max(t0, min(tail_start, t1))
    span = max(t1 - tail_start, 1e-9)
    freqs: list[float] = []
    if cfg is not None:
        if cfg.Pamp and cfg.fa > 0:
            freqs.append(float(cfg.fa))
        if cfg.ItestAmp and cfg.ItestFreq > 0:
            freqs.append(float(cfg.ItestFreq))
        if cfg.A1 and cfg.fm1 > 0:
            freqs.append(float(cfg.fm1))
        if cfg.A2 and cfg.fm2 > 0:
            freqs.append(float(cfg.fm2))
    freqs = [f for f in freqs if math.isfinite(f) and f > 0]
    if not freqs:
        duration = min(span, 0.03)
    else:
        fmin, fmax = min(freqs), max(freqs)
        if fmin < 50:
            # Slow modulation: keep enough time to see the trend, not only a tiny slice.
            duration = min(span, max(0.03, 1.2 / fmin))
        else:
            # Faster excitations: show several final cycles so the traces are not a dense line.
            duration = min(span, max(0.005, min(0.03, 8.0 / fmax)))
    return (max(tail_start, t1 - duration) * 1e3, t1 * 1e3)


def _plot_clipped_reff(df: pd.DataFrame, col: str, qlo: float = 1, qhi: float = 99) -> np.ndarray:
    raw = np.asarray(df[col], dtype=float)
    finite_raw = raw[np.isfinite(raw)]
    if finite_raw.size < 10:
        return raw
    lo, hi = np.nanpercentile(finite_raw, [qlo, qhi])
    if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
        return raw
    return np.clip(raw, lo, hi)


def add_derived(df: pd.DataFrame, spk: SpeakerTS, cfg: SimConfig) -> pd.DataFrame:
    out = df.copy()
    ip = out["v(iport)"].to_numpy(float)
    spk_v = out["v(spk)"].to_numpy(float)
    rt_cmd = out["v(rtarget)"].to_numpy(float)

    # Point-wise V/I is useful only away from current zero-crossings.
    tail_start = max(0.5 * float(out["time"].max()), cfg.TSTART + 3 * cfg.TRAMP)
    tail_mask = out["time"].to_numpy(float) >= tail_start
    ip_tail_pk = float(np.nanmax(np.abs(ip[tail_mask]))) if np.any(tail_mask) else float(np.nanmax(np.abs(ip)))
    i_threshold = max(50e-6, 0.05 * ip_tail_pk)

    reff = np.full_like(ip, np.nan, dtype=float)
    valid = np.abs(ip) >= i_threshold
    with np.errstate(divide="ignore", invalid="ignore"):
        reff[valid] = spk.Re + spk_v[valid] / ip[valid]

    out["reff_pointwise"] = reff
    out["reff_pointwise_plot"] = pd.Series(reff).interpolate(limit_direction="both").to_numpy()
    out["reff_pointwise_err"] = reff - rt_cmd
    out["valid_reff_pointwise"] = valid.astype(int)
    out["iport_threshold_for_reff"] = i_threshold
    out["tail_start_s"] = tail_start
    out["port_power_w"] = spk_v * ip

    if "v(rxnode)" in out.columns:
        out["rx_iport_v"] = out["v(rxnode)"] * out["v(iport)"]
    if "v(synerr)" not in out.columns and "rx_iport_v" in out.columns:
        out["v(synerr)"] = out["v(spk)"] - out["rx_iport_v"]
    if "v(cmderr)" not in out.columns and "v(vcmd)" in out.columns and "rx_iport_v" in out.columns:
        out["v(cmderr)"] = out["v(vcmd)"] - out["rx_iport_v"]

    return out


def summarize(df: pd.DataFrame, spk: SpeakerTS, cfg: SimConfig, name: str, model: str) -> dict:
    """Summarize one completed simulation and apply explicit acceptance policy.

    The legacy point-wise V/I traces remain diagnostic only. Fixed electrical
    impedance uses a DC-aware complex phasor fit. Dynamic electrical impedance
    uses local carrier phasors with a first-order envelope model.
    """
    tail_start = float(df["tail_start_s"].iloc[0]) if "tail_start_s" in df.columns else 0.5 * float(df["time"].max())
    tail = df["time"] >= tail_start
    valid = df.get("valid_reff_pointwise", pd.Series(np.ones(len(df), dtype=int))).astype(bool)
    vt = tail & valid

    rtarget_tail_mean = amean(df.loc[tail, "v(rtarget)"])
    rtarget_tail_rms_dev = rms(df.loc[tail, "v(rtarget)"] - rtarget_tail_mean)
    rx_i = df.loc[tail, "rx_iport_v"] if "rx_iport_v" in df.columns else pd.Series(dtype=float)
    denom_v = max(rms(rx_i), 1e-12)

    s = {
        "case": name,
        "model": model,
        **model_metadata(),
        "status": "ok",  # Backward-compatible simulation completion marker.
        "simulation_status": "completed",
        "tail_start_s": tail_start,
        "softstart_tstart_s": cfg.TSTART,
        "softstart_tramp_s": cfg.TRAMP,
        "pamp_pa": cfg.Pamp,
        "itest_amp_a": cfg.ItestAmp,
        "itest_freq_hz": cfg.ItestFreq,
        "modulation_freq_hz": cfg.fm1 if cfg.A1 != 0 and cfg.A2 == 0 else float("nan"),
        "rtarget_cmd_min_ohm": amin(df["v(rtarget)"]),
        "rtarget_cmd_max_ohm": amax(df["v(rtarget)"]),
        "rtarget_des_min_ohm": amin(df["v(rdes)"]) if "v(rdes)" in df.columns else float("nan"),
        "rtarget_des_max_ohm": amax(df["v(rdes)"]) if "v(rdes)" in df.columns else float("nan"),
        "rx_cmd_min_ohm": amin(df["v(rxnode)"]),
        "rx_cmd_max_ohm": amax(df["v(rxnode)"]),
        "iport_pk_a": amax(np.abs(df["v(iport)"])),
        "iport_pk_tail_a": amax(np.abs(df.loc[tail, "v(iport)"])),
        "iport_dc_tail_a": amean(df.loc[tail, "v(iport)"]),
        "iport_threshold_for_reff_a": float(df["iport_threshold_for_reff"].iloc[0]),
        "vspk_pk_v": amax(np.abs(df["v(spk)"])),
        "vspk_pk_tail_v": amax(np.abs(df.loc[tail, "v(spk)"])),
        "vel_pk_mps": amax(np.abs(df["v(vel)"])),
        "x_pk_m": amax(np.abs(df["v(xnode)"])),
        "xmax_ratio_pk": amax(df["v(xmaxabs)"]),
        "power_port_pk_w": amax(np.abs(df["port_power_w"])),
        "qeff_min": amin(df["v(qnode)"]),
        "qeff_max": amax(df["v(qnode)"]),
        "rem_min": amin(df["v(remnode)"]),
        "rem_max": amax(df["v(remnode)"]),
        "synerr_rms_tail_v": rms(df.loc[tail, "v(synerr)"]) if "v(synerr)" in df.columns else float("nan"),
        "synerr_abs_max_tail_v": amax(np.abs(df.loc[tail, "v(synerr)"])) if "v(synerr)" in df.columns else float("nan"),
        "synerr_norm_rms_tail": (rms(df.loc[tail, "v(synerr)"]) / denom_v) if "v(synerr)" in df.columns else float("nan"),
        "cmderr_rms_tail_v": rms(df.loc[tail, "v(cmderr)"]) if "v(cmderr)" in df.columns else float("nan"),
        "cmderr_abs_max_tail_v": amax(np.abs(df.loc[tail, "v(cmderr)"])) if "v(cmderr)" in df.columns else float("nan"),
        "rtarget_tail_mean_ohm": rtarget_tail_mean,
        "rtarget_tail_rms_dev_ohm": rtarget_tail_rms_dev,
        "reff_pointwise_rms_err_tail_ohm": rms(df.loc[vt, "reff_pointwise_err"]),
        "reff_pointwise_abs_err_tail_max_ohm": amax(np.abs(df.loc[vt, "reff_pointwise_err"])),
        "reff_pointwise_valid_fraction_tail": float(vt.sum() / max(int(tail.sum()), 1)),
    }

    if "v(vsat)" in df.columns:
        s["opa548_vsat_max_v"] = amax(df["v(vsat)"])
    if "v(followerr)" in df.columns:
        s["follow_error_pk_v"] = amax(np.abs(df["v(followerr)"]))
        s["follow_error_rms_tail_v"] = rms(df.loc[tail, "v(followerr)"])
    if "v(ilimratio)" in df.columns:
        s["ilim_ratio_pk"] = amax(df["v(ilimratio)"])
        s["ilim_ratio_tail_pk"] = amax(df.loc[tail, "v(ilimratio)"])

    if "v(iport)" in df.columns and "v(drv)" in df.columns:
        iout = df["v(iport)"].to_numpy(float)
        vdrv = df["v(drv)"].to_numpy(float)
        p_opa_est = np.maximum(18.0 - np.abs(vdrv), 0.0) * np.abs(iout)
        p_rsh = (iout * iout) * cfg.RSH * cfg.RSH_SCALE
        s["opa548_power_est_avg_tail_w"] = amean(p_opa_est[tail.to_numpy()])
        s["opa548_power_est_pk_w"] = amax(p_opa_est)
        s["rshunt_power_avg_tail_w"] = amean(p_rsh[tail.to_numpy()])
        s["rshunt_power_pk_w"] = amax(p_rsh)
    else:
        s["opa548_power_est_avg_tail_w"] = float("nan")
        s["opa548_power_est_pk_w"] = float("nan")
        s["rshunt_power_avg_tail_w"] = float("nan")
        s["rshunt_power_pk_w"] = float("nan")
    s["supply_regen_risk_flag"] = bool(np.nanmin(df["port_power_w"]) < -0.05) if "port_power_w" in df.columns else False

    # Fixed-R electrical injection: primary impedance result is a complex phasor.
    is_fixed_einj = cfg.ItestAmp > 0 and cfg.A1 == 0 and cfg.A2 == 0
    if is_fixed_einj:
        fixed = fixed_complex_impedance(
            df["time"].to_numpy(float),
            df["v(spk)"].to_numpy(float),
            df["v(iport)"].to_numpy(float),
            cfg.ItestFreq,
            spk.Re,
            tail_start,
            POLICY,
        )
        s.update(fixed)
        if fixed.get("phasor_status") == "ok":
            # Keep old columns, now sourced from the correct complex fit.
            s["reff_fit_tail_ohm"] = fixed["ztotal_real_ohm"]
            s["rx_fit_tail_ohm"] = fixed["zsynthetic_real_ohm"]
            s["reff_fit_err_vs_tail_mean_ohm"] = fixed["ztotal_real_ohm"] - rtarget_tail_mean
            s["reff_fit_sample_count"] = int(tail.sum())
        else:
            s["reff_fit_tail_ohm"] = float("nan")
            s["rx_fit_tail_ohm"] = float("nan")
            s["reff_fit_err_vs_tail_mean_ohm"] = float("nan")
            s["reff_fit_sample_count"] = 0

    # Dynamic electrical injection: local complex carrier phasors, not v(t)/i(t).
    is_dynamic_einj = cfg.ItestAmp > 0 and cfg.A1 != 0 and cfg.A2 == 0
    if is_dynamic_einj:
        dyn, rows = dynamic_complex_impedance(
            df["time"].to_numpy(float),
            df["v(spk)"].to_numpy(float),
            df["v(iport)"].to_numpy(float),
            df["v(rtarget)"].to_numpy(float),
            cfg.ItestFreq,
            cfg.fm1,
            spk.Re,
            tail_start,
            POLICY,
        )
        s.update(dyn)
        df.attrs["dynamic_phasor_rows"] = rows

    for key in ["RDRV_PAR", "LDRV_PAR", "RSPK_PAR", "LSPK_PAR", "RSPEAKER_SERIES", "RSPK_SHORT", "RSH_SCALE", "VOS_I_TRIM", "DC_SERVO_ENABLE", "DC_SERVO_FC", "DC_SERVO_K", "DC_SERVO_LIMIT", "FIX_SCHED_ENABLE", "FIX_SCHED_FULL", "FIX_SCHED_OFF", "C_U4A_F", "C_U4B_F", "R_U4A_LEAD", "C_U4A_LEAD", "R_U4B_LEAD", "C_U4B_LEAD", "RISO_OUT", "RZOBEL", "CZOBEL"]:
        s[key.lower()] = getattr(cfg, key)

    return apply_acceptance(s, POLICY)

def plot_case(df: pd.DataFrame, name: str, path: Path, cfg: SimConfig | None = None, *, tail_only: bool = False) -> None:
    """Create readable diagnostic plots.

    The legacy point-wise Reff trace can contain mathematically meaningless spikes near
    current zero-crossings. The plotted version is clipped only for visual scale; the
    CSV and summary metrics keep the original values.
    """
    t = df["time"] * 1e3
    fig, axes = plt.subplots(6, 1, figsize=(13, 14), sharex=True)
    tail_start_ms = float(df["tail_start_s"].iloc[0]) * 1e3 if "tail_start_s" in df.columns else None

    reff_plot = _plot_clipped_reff(df, "reff_pointwise_plot") if "reff_pointwise_plot" in df.columns else None
    reff_err_plot = _plot_clipped_reff(df, "reff_pointwise_err") if "reff_pointwise_err" in df.columns else None

    if "v(rdes)" in df.columns:
        axes[0].plot(t, df["v(rdes)"], label="R desired", lw=1.0, alpha=0.75)
    axes[0].plot(t, df["v(rtarget)"], label="R command after soft-start/RC", lw=1.4)
    if reff_plot is not None:
        axes[0].plot(t, reff_plot, "--", label="Reff pointwise, masked/interp/clipped", lw=1.0)
    axes[0].plot(t, df["v(rxnode)"], ":", label="Rx command", lw=1.0)
    axes[0].set_ylabel("ohm")
    axes[0].legend(ncol=4, fontsize=8)
    axes[0].set_title(name + (" — steady tail zoom" if tail_only else " — overview"))
    _apply_ylim(
        axes[0],
        [df.get("v(rdes)"), df["v(rtarget)"], df["v(rxnode)"], reff_plot],
        include=[-10, 0, 1, 7.2, 100, 110],
        qlo=2, qhi=98, pad=0.08, min_span=5,
    )

    axes[1].plot(t, df["v(spk)"], label="SPK")
    if "v(drv)" in df.columns:
        axes[1].plot(t, df["v(drv)"], label="DRV", alpha=0.8)
    if "v(vcmd)" in df.columns:
        axes[1].plot(t, df["v(vcmd)"], label="VCMD", alpha=0.8)
    if "rx_iport_v" in df.columns:
        axes[1].plot(t, df["rx_iport_v"], "--", label="Rx*Iport", alpha=0.8)
    axes[1].set_ylabel("V")
    axes[1].legend(ncol=4, fontsize=8)
    _apply_ylim(axes[1], [df.get("v(spk)"), df.get("v(drv)"), df.get("v(vcmd)"), df.get("rx_iport_v")], qlo=1, qhi=99, pad=0.12, min_span=1e-4, symmetric=True)

    axes[2].plot(t, df["v(iport)"], label="Iport")
    thr = float(df["iport_threshold_for_reff"].iloc[0]) if "iport_threshold_for_reff" in df.columns else None
    if thr and math.isfinite(thr):
        axes[2].axhline(thr, ls=":", lw=0.8, alpha=0.5)
        axes[2].axhline(-thr, ls=":", lw=0.8, alpha=0.5)
    axes[2].set_ylabel("A")
    axes[2].legend(fontsize=8)
    _apply_ylim(axes[2], [df["v(iport)"]], qlo=1, qhi=99, pad=0.15, min_span=1e-6, symmetric=True)

    err_series = []
    if "v(synerr)" in df.columns:
        axes[3].plot(t, df["v(synerr)"], label="SPK - Rx*Iport")
        err_series.append(df["v(synerr)"])
    if "v(cmderr)" in df.columns:
        axes[3].plot(t, df["v(cmderr)"], label="VCMD - Rx*Iport", alpha=0.8)
        err_series.append(df["v(cmderr)"])
    if "v(followerr)" in df.columns:
        axes[3].plot(t, df["v(followerr)"], label="VCMD - SPK", alpha=0.65)
        err_series.append(df["v(followerr)"])
    axes[3].set_ylabel("error V")
    axes[3].legend(ncol=3, fontsize=8)
    _apply_ylim(axes[3], err_series, qlo=1, qhi=99, pad=0.15, min_span=1e-6, symmetric=True)

    axes[4].plot(t, df["v(vel)"], label="velocity [m/s]")
    axes[4].plot(t, df["v(xnode)"] * 1000, label="x [mm]")
    axes[4].set_ylabel("m/s or mm")
    axes[4].legend(ncol=2, fontsize=8)
    _apply_ylim(axes[4], [df["v(vel)"], df["v(xnode)"] * 1000], qlo=1, qhi=99, pad=0.15, min_span=1e-5, symmetric=True)

    if reff_err_plot is not None:
        axes[5].plot(t, reff_err_plot, label="masked pointwise Reff-Rcmd, clipped")
    axes[5].plot(t, df["v(xmaxabs)"], label="|x|/xmax")
    aux_series = [reff_err_plot, df["v(xmaxabs)"]]
    if "v(vsat)" in df.columns:
        axes[5].plot(t, df["v(vsat)"], label="OPA548 saturation proxy")
        aux_series.append(df["v(vsat)"])
    if "v(ilimratio)" in df.columns:
        axes[5].plot(t, df["v(ilimratio)"], label="|Iout|/Ilim")
        aux_series.append(df["v(ilimratio)"])
    axes[5].set_xlabel("time [ms]")
    axes[5].legend(ncol=4, fontsize=8)
    _apply_ylim(axes[5], aux_series, qlo=2, qhi=98, pad=0.12, min_span=0.02)

    if tail_start_ms is not None:
        for ax in axes:
            ax.axvline(tail_start_ms, color="0.25", lw=0.8, ls="--", alpha=0.45)
            ax.grid(True, alpha=0.3)
    else:
        for ax in axes:
            ax.grid(True, alpha=0.3)

    if tail_only:
        x0, x1 = _tail_focus_window_ms(df, cfg)
        axes[-1].set_xlim(x0, x1)
    else:
        axes[-1].set_xlim(float(t.min()), float(t.max()))

    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)

def run_case(name: str, model: str, cfg: SimConfig, spk: SpeakerTS, write_only: bool = False) -> dict:
    case_dir = CASES / name
    case_dir.mkdir(parents=True, exist_ok=True)
    datafile = f"{name}.dat"
    template_name = {
        "full": "full_component_template.cir",
        "ideal": "ideal_reference_template.cir",
        "beh": "behavioral_chain_template.cir",
    }[model]
    netlist = render((TEMPLATES / template_name).read_text(encoding="utf-8"), spk, cfg, datafile)
    if RUNTIME_MODEL_POLICY == "official_pure_raw_vendor_macromodels_no_device_surrogate":
        # Numerical-only convergence profile for vendor PSpice macromodels under ngspice.
        # This does not replace device macromodel content; it relaxes solver tolerances and
        # adds a tiny node capacitance to avoid internal switch initial-point singularities.
        netlist = netlist.replace(
            ".options reltol=3e-5 abstol=1e-10 vabstol=1e-7 chgtol=1e-14",
            ".options reltol=1e-3 abstol=1e-9 vabstol=1e-6 chgtol=1e-13 trtol=7",
        )
        netlist = netlist.replace(
            ".options gmin=1e-12 rshunt=1e12",
            ".options gmin=1e-10 rshunt=1e10 cshunt=1e-15",
        )
    cir = case_dir / f"{name}.cir"
    cir.write_text(netlist, encoding="utf-8")
    if RUNTIME_MODEL_POLICY == "official_pure_raw_vendor_macromodels_no_device_surrogate":
        (case_dir / ".spiceinit").write_text("set ngbehavior=ps\n", encoding="utf-8")
    (case_dir / f"{name}_config.json").write_text(
        json.dumps({"case": name, "model": model, "speaker": asdict(spk), "config": asdict(cfg)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if write_only:
        return {"case": name, "model": model, **model_metadata(), "status": "written_only", "simulation_status": "written_only", "acceptance_status": "not_evaluated", "acceptance_pass": False, "cir": str(cir)}

    log = case_dir / f"{name}.log"
    r = subprocess.run([NGSPICE_BIN, "-b", "-o", str(log), str(cir)], cwd=case_dir, capture_output=True, text=True)
    if r.returncode != 0:
        return {
            "case": name,
            "model": model,
            **model_metadata(),
            "status": "ngspice_failed",
            "simulation_status": "ngspice_failed",
            "acceptance_status": "not_evaluated",
            "acceptance_pass": False,
            "returncode": r.returncode,
            "log": str(log),
            "stdout": r.stdout[-2000:],
            "stderr": r.stderr[-2000:],
        }

    try:
        df = add_derived(read_wrdata(case_dir / datafile), spk, cfg)
        if SAVE_CASE_CSV:
            df.to_csv(case_dir / f"{name}.csv", index=False)
        summary = summarize(df, spk, cfg, name, model)
        dynamic_rows = df.attrs.get("dynamic_phasor_rows", [])
        if dynamic_rows:
            pd.DataFrame(dynamic_rows).to_csv(case_dir / f"{name}_dynamic_phasor.csv", index=False)
        (case_dir / f"{name}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        if GENERATE_PLOTS:
            plot_case(df, name, case_dir / f"{name}.png", cfg=cfg, tail_only=False)
            plot_case(df, name, case_dir / f"{name}_tail.png", cfg=cfg, tail_only=True)
        return summary
    except Exception as exc:
        return {
            "case": name,
            "model": model,
            **model_metadata(),
            "status": "postprocess_failed",
            "simulation_status": "postprocess_failed",
            "acceptance_status": "not_evaluated",
            "acceptance_pass": False,
            "returncode": 0,
            "log": str(log),
            "error": repr(exc),
        }


def case_list(base: SimConfig) -> list[tuple[str, str, SimConfig]]:
    cases: list[tuple[str, str, SimConfig]] = []

    # Baseline comparisons, now with soft-start.
    cases += [
        ("ideal_single_sine", "ideal", base),
        ("behavioral_single_sine", "beh", base),
        ("full_single_sine", "full", base),
        ("ideal_dual_sine", "ideal", replace(base, A1=30, A2=19.5, fm1=100, fm2=317)),
        ("behavioral_dual_sine", "beh", replace(base, A1=30, A2=19.5, fm1=100, fm2=317)),
        ("full_dual_sine", "full", replace(base, A1=30, A2=19.5, fm1=100, fm2=317)),
    ]

    # Fixed-R acoustic tests.
    for rt in [100, 20, 7.2, 5, 1]:
        cases.append((f"full_fixed_r{safe(rt)}", "full", replace(base, R0=rt, A1=0, A2=0, tstop=0.07)))

    # Modulation-frequency boundary tests.
    for fm in [10, 30, 100, 300, 1000]:
        tstop = 0.15 if fm <= 10 else 0.06
        cases.append((f"full_fm{safe(fm)}", "full", replace(base, fm1=fm, tstop=tstop)))

    # Acoustic frequency tests.
    for fa in [60, 90, 120, 180, 300]:
        cases.append((f"full_acoustic_fa{safe(fa)}", "full", replace(base, fa=fa, tstop=0.07)))

    # Acoustic stress tests are intentionally limited to <= 5 Pa in v3.3.
    for pa in STRESS_PRESSURES_PA:
        cases.append((f"full_stress_pa{safe(pa)}_fixed1ohm", "full", replace(base, R0=1, A1=0, A2=0, Pamp=pa, tstop=0.07)))
        cases.append((f"full_stress_pa{safe(pa)}_mod", "full", replace(base, Pamp=pa, tstop=0.07)))

    # Electrical current-injection tests: Pamp=0, external current source drives SPK.
    # These are the preferred tests for verifying synthetic electrical impedance.
    for rt in [100, 20, 7.2, 5, 1]:
        cases.append((
            f"full_einj_fixed_r{safe(rt)}_f1000",
            "full",
            replace(base, R0=rt, A1=0, A2=0, Pamp=0, ItestAmp=1e-3, ItestFreq=1000, fa=120, tstop=0.04, tstep=1e-6),
        ))
    for freq in [100, 5000]:
        cases.append((
            f"full_einj_fixed_r1_f{safe(freq)}",
            "full",
            replace(base, R0=1, A1=0, A2=0, Pamp=0, ItestAmp=1e-3, ItestFreq=freq, tstop=0.06 if freq <= 100 else 0.04, tstep=1e-6),
        ))
    cases.append((
        "full_einj_single_sine_mod_f1000",
        "full",
        replace(base, Pamp=0, ItestAmp=1e-3, ItestFreq=1000, tstop=0.06, tstep=1e-6),
    ))

    # Current limit margin variant.
    cases.append(("full_single_sine_ilim2a", "full", replace(base, RCL=22.1e3, IOUT=1.99)))
    return cases


def parasitic_case_list(base: SimConfig) -> list[tuple[str, str, SimConfig]]:
    cases: list[tuple[str, str, SimConfig]] = []
    profiles = {
        "typ": dict(RDRV_PAR=0.03, LDRV_PAR=80e-9, RSPK_PAR=0.04, LSPK_PAR=120e-9, RSPEAKER_SERIES=0.08),
        "worst": dict(RDRV_PAR=0.10, LDRV_PAR=250e-9, RSPK_PAR=0.15, LSPK_PAR=500e-9, RSPEAKER_SERIES=0.30, RSH_SCALE=1.02),
    }
    for label, params in profiles.items():
        for rt in [100, 20, 7.2, 5, 1]:
            cases.append((
                f"parasitic_{label}_einj_fixed_r{safe(rt)}_f1000",
                "full",
                replace(base, R0=rt, A1=0, A2=0, Pamp=0, ItestAmp=1e-3, ItestFreq=1000, tstop=0.04, tstep=1e-6, **params),
            ))
        for fm in [10, 100, 1000]:
            tstop = 0.15 if fm <= 10 else 0.06
            cases.append((f"parasitic_{label}_fm{safe(fm)}", "full", replace(base, fm1=fm, tstop=tstop, **params)))
    return cases


def fault_case_list(base: SimConfig) -> list[tuple[str, str, SimConfig]]:
    return [
        ("fault_vk_min_stuck_r1", "full", replace(base, R0=1, A1=0, A2=0, tstop=0.07)),
        ("fault_vk_max_stuck_r100", "full", replace(base, R0=100, A1=0, A2=0, tstop=0.07)),
        ("fault_speaker_open_r1", "full", replace(base, R0=1, A1=0, A2=0, RSPEAKER_SERIES=1e9, tstop=0.04, tstep=1e-6)),
        ("fault_speaker_short_r1", "full", replace(base, R0=1, A1=0, A2=0, RSPK_SHORT=0.05, tstop=0.04, tstep=1e-6)),
        ("fault_rsh_open", "full", replace(base, R0=7.2, A1=0, A2=0, RSH=1e9, tstop=0.02, tstep=1e-6)),
        ("fault_rsh_low_20pct", "full", replace(base, R0=1, A1=0, A2=0, RSH_SCALE=0.8, tstop=0.04, tstep=1e-6)),
        ("fault_rsh_high_20pct", "full", replace(base, R0=1, A1=0, A2=0, RSH_SCALE=1.2, tstop=0.04, tstep=1e-6)),
    ]


def fixed_signoff_case_list(base: SimConfig) -> list[tuple[str, str, SimConfig]]:
    return [
        (
            f"signoff_fixed_r{safe(rt)}_carrier1k",
            "full",
            replace(base, R0=rt, A1=0, A2=0, Pamp=0, ItestAmp=1e-3, ItestFreq=1000, tstop=0.04, tstep=1e-6),
        )
        for rt in [1, 5, 7.2, 20, 100]
    ]


def dynamic_signoff_case_list(base: SimConfig) -> list[tuple[str, str, SimConfig]]:
    cases: list[tuple[str, str, SimConfig]] = []
    for fm, tstop in [(10, 0.15), (30, 0.09), (100, 0.06), (300, 0.04), (1000, 0.03)]:
        cases.append((
            f"signoff_dynamic_fm{safe(fm)}_carrier10k",
            "full",
            replace(base, Pamp=0, ItestAmp=1e-3, ItestFreq=10000, fm1=fm, tstop=tstop, tstep=2e-6),
        ))
    return cases


def selected_cases(base: SimConfig, suite: str) -> list[tuple[str, str, SimConfig]]:
    if suite == "fixed-signoff":
        return fixed_signoff_case_list(base)
    if suite == "dynamic-signoff":
        return dynamic_signoff_case_list(base)
    cases = case_list(base)
    if suite in {"parasitic", "complete"}:
        cases += parasitic_case_list(base)
    if suite in {"fault", "complete"}:
        cases += fault_case_list(base)
    if suite == "default":
        return cases
    if suite == "parasitic":
        return parasitic_case_list(base)
    if suite == "fault":
        return fault_case_list(base)
    return cases


def write_completion_reports(results_dir: Path, summaries: list[dict], suite: str) -> None:
    if not summaries:
        return
    df = pd.DataFrame(summaries)
    reports = results_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    thermal_cols = [
        "case", "status", "opa548_power_est_avg_tail_w", "opa548_power_est_pk_w",
        "rshunt_power_avg_tail_w", "rshunt_power_pk_w", "ilim_ratio_tail_pk",
        "xmax_ratio_pk", "supply_regen_risk_flag",
    ]
    [c for c in thermal_cols if c in df.columns]
    df[[c for c in thermal_cols if c in df.columns]].to_csv(results_dir / "thermal_power_summary.csv", index=False)

    simulation_counts = df.get("simulation_status", df.get("status", pd.Series(dtype=str))).fillna("<missing>").value_counts().to_dict()
    acceptance_counts = df.get("acceptance_status", pd.Series(dtype=str)).fillna("<missing>").value_counts().to_dict()
    model_counts = df.get("runtime_model_policy", pd.Series(dtype=str)).fillna("<missing>").value_counts().to_dict()
    sim_failures = df[df.get("simulation_status", df.get("status", pd.Series(index=df.index, dtype=str))).fillna("") != "completed"]
    acceptance_failures = df[df.get("acceptance_status", pd.Series(index=df.index, dtype=str)).fillna("") == "fail"]
    failures = pd.concat([sim_failures, acceptance_failures]).drop_duplicates(subset=["case"])

    def worst(col: str, largest_abs: bool = False, data: pd.DataFrame | None = None) -> str:
        d = df if data is None else data
        if d.empty or col not in d or d[col].dropna().empty:
            return "N/A"
        series = pd.to_numeric(d[col], errors="coerce")
        series = series.dropna()
        if series.empty:
            return "N/A"
        idx = series.abs().idxmax() if largest_abs else series.idxmax()
        return f"{d.loc[idx, 'case']}: {series.loc[idx]:.6g}"

    full_report = f"""# SPICE 完整运行报告

结果目录：`{results_dir}`

## 运行范围

- suite: `{suite}`
- case 数量：{len(df)}
- 仿真状态统计：{json.dumps(simulation_counts, ensure_ascii=False)}
- 验收状态统计：{json.dumps(acceptance_counts, ensure_ascii=False)}
- 模型策略统计：{json.dumps(model_counts, ensure_ascii=False)}

## 关键最坏值

- 最大 `synerr_norm_rms_tail`：{worst('synerr_norm_rms_tail')}
- 最大 `ilim_ratio_tail_pk`：{worst('ilim_ratio_tail_pk')}
- 最大 `xmax_ratio_pk`：{worst('xmax_ratio_pk')}
- 最大 OPA548 估算峰值功耗：{worst('opa548_power_est_pk_w')}
- 最大 RSHUNT 估算峰值功耗：{worst('rshunt_power_pk_w')}
- 最大固定阻抗实部误差绝对值：{worst('fixed_real_error_ohm')}
- 最大固定阻抗虚部绝对值：{worst('ztotal_imag_ohm', largest_abs=True)}
- 最大动态 p95 实部相对误差：{worst('dynamic_p95_abs_real_rel_error')}
- 最大动态 p95 虚部相对值：{worst('dynamic_p95_abs_imag_rel')}

## 失败情况

失败 case 数量：{len(failures)}

- 仿真失败：`simulation_failures.csv`
- 验收失败：`acceptance_failures.csv`
- 合并失败：`failures.csv`

## 解释边界

当前结果仍按每行 `model_lib` 和 `runtime_model_policy` 解释。只要策略包含 surrogate/fallback，就不能写成纯厂商宏模型 transient signoff。
"""
    (reports / "SPICE_FULL_SWEEP_REPORT_2026-06-24.md").write_text(full_report, encoding="utf-8")

    provenance = f"""# SPICE 模型来源报告

结果目录：`{results_dir}`

## 模型策略统计

{json.dumps(model_counts, ensure_ascii=False, indent=2)}

## 结论

- `local_ngspice_surrogate`：本地 ngspice 兼容代理模型。
- `official_audit_with_ngspice_surrogate_fallback`：官方模型文件已纳入审计和包装路径，但 transient 运行仍使用 ngspice-safe surrogate fallback。
- `official_pure_raw_vendor_macromodels_no_device_surrogate`：使用 raw TI/ADI 厂商宏模型，通过 `.spiceinit: set ngbehavior=ps` 只对 include 库启用 PSpice 兼容；器件不允许 fallback。
- `custom_model_lib_unclassified`：用户指定模型库，必须单独审计。

不得把 fallback/surrogate 结果描述为纯官方厂商宏模型签核。
"""
    (reports / "SPICE_MODEL_PROVENANCE_2026-06-24.md").write_text(provenance, encoding="utf-8")

    parasitic_df = df[df["case"].astype(str).str.startswith("parasitic_")] if "case" in df else pd.DataFrame()
    parasitic_report = f"""# SPICE 寄生参数 sweep 报告

寄生 case 数量：{len(parasitic_df)}

## 最坏值

- 最大 `synerr_norm_rms_tail`：{worst('synerr_norm_rms_tail', data=parasitic_df)}
- 最大 `Reff` 拟合误差绝对值：{worst('reff_fit_err_vs_tail_mean_ohm', largest_abs=True, data=parasitic_df)}
- 最大 `ilim_ratio_tail_pk`：{worst('ilim_ratio_tail_pk', data=parasitic_df)}

寄生参数列已写入 `all_summary.csv`：`rdrv_par`、`ldrv_par`、`rspk_par`、`lspk_par`、`rspeaker_series`、`rspk_short`、`rsh_scale`。
"""
    (reports / "SPICE_PARASITIC_SWEEP_REPORT_2026-06-24.md").write_text(parasitic_report, encoding="utf-8")

    fault_df = df[df["case"].astype(str).str.startswith("fault_")] if "case" in df else pd.DataFrame()
    fault_report = f"""# SPICE 保护和异常工况报告

异常 case 数量：{len(fault_df)}

## 异常 case

{os.linesep.join('- `' + c + '`' for c in fault_df.get('case', pd.Series(dtype=str)).tolist())}

## 需要硬件继续确认

- `VK` 上电默认态和卡死保护。
- 扬声器开路/短路时 OPA548 限流、热和恢复行为。
- RSH1 采样异常时固件/硬件是否能关断。
- 供电回灌是否被电源或钳位路径吸收。
"""
    (reports / "SPICE_PROTECTION_FAULT_REPORT_2026-06-24.md").write_text(fault_report, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-only", action="store_true", help="Generate case netlists/configs without running ngspice")
    ap.add_argument("--clean", action="store_true", help="Delete results/ before running")
    ap.add_argument("--case-filter", default="", help="Substring filter for case names")
    ap.add_argument("--results-dir", default="results", help="Output directory relative to project root or absolute path")
    ap.add_argument("--smoke", action="store_true", help="Write outputs to results_smoke/ so smoke tests do not overwrite full results")
    ap.add_argument("--suite", choices=["default", "parasitic", "fault", "complete", "fixed-signoff", "dynamic-signoff"], default="default", help="Case suite to run")
    ap.add_argument("--allow-acceptance-fail", action="store_true", help="Return zero when simulations complete even if engineering acceptance fails")
    ap.add_argument("--no-plots", action="store_true", help="Skip PNG generation for faster split regressions")
    ap.add_argument("--no-case-csv", action="store_true", help="Keep ngspice .dat and summary only; skip large derived CSV")
    ap.add_argument("--model-lib", default=None, help="SPICE library to include from generated case directories. Use \"official\" for spice/models/official_wrapped_models.lib, or pass a relative/absolute path.")
    args = ap.parse_args()

    global MODEL_LIB, MODEL_LIB_CHOICE, RUNTIME_MODEL_POLICY, RESULTS, CASES, SAVE_CASE_CSV, GENERATE_PLOTS
    SAVE_CASE_CSV = not args.no_case_csv
    GENERATE_PLOTS = not args.no_plots
    if args.model_lib:
        ml = args.model_lib.lower()
        if ml in {"official-pure", "vendor-pure", "pure-official"}:
            MODEL_LIB = str((ROOT / "spice" / "models" / "official_pure_rawps_wrapped_models.lib").resolve())
            MODEL_LIB_CHOICE = "official-pure"
            RUNTIME_MODEL_POLICY = "official_pure_raw_vendor_macromodels_no_device_surrogate"
        elif ml in {"official", "vendor", "official-local", "official-fallback"}:
            MODEL_LIB = str((ROOT / "spice" / "models" / "official_wrapped_models.lib").resolve())
            MODEL_LIB_CHOICE = "official-fallback"
            RUNTIME_MODEL_POLICY = "official_audit_with_ngspice_surrogate_fallback"
        elif ml in {"surrogate", "default"}:
            candidate = ROOT / "spice" / "models" / "ngspice_compatible_macros.lib"
            MODEL_LIB = str(candidate.resolve())
            MODEL_LIB_CHOICE = "local"
            RUNTIME_MODEL_POLICY = "local_ngspice_surrogate"
        else:
            MODEL_LIB = args.model_lib
            MODEL_LIB_CHOICE = "custom"
            RUNTIME_MODEL_POLICY = "custom_model_lib_unclassified"

    model_path = Path(MODEL_LIB)
    if not model_path.is_absolute():
        model_path = (ROOT / model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Selected SPICE model library does not exist: {model_path}")
    MODEL_LIB = str(model_path)

    if args.smoke:
        args.results_dir = "results_smoke"
    out = Path(args.results_dir)
    RESULTS = out if out.is_absolute() else ROOT / out
    CASES = RESULTS / "cases"

    if args.clean and RESULTS.exists():
        shutil.rmtree(RESULTS)
    RESULTS.mkdir(exist_ok=True)
    CASES.mkdir(parents=True, exist_ok=True)

    if not args.write_only:
        check_ngspice()

    spk = SpeakerTS()
    base = SimConfig()
    (RESULTS / "speaker_params.json").write_text(
        json.dumps({**asdict(spk), "w0": spk.w0, "Cms": spk.Cms, "Rms": spk.Rms, "Kms": spk.Kms}, indent=2),
        encoding="utf-8",
    )

    summaries = []
    for name, model, cfg in selected_cases(base, args.suite):
        if args.case_filter and args.case_filter not in name:
            continue
        print(f"RUN {name} [{model}]")
        summaries.append(run_case(name, model, cfg, spk, write_only=args.write_only))

    if not summaries:
        raise SystemExit("No cases matched the requested filter")
    df = pd.DataFrame(summaries)
    df.to_csv(RESULTS / "all_summary.csv", index=False)
    if args.write_only:
        (RESULTS / "validation_policy.json").write_text(json.dumps(POLICY.to_dict(), indent=2), encoding="utf-8")
        print(f"Done (write-only): {RESULTS}")
        return
    sim_fails = df[df.get("simulation_status", df.get("status", pd.Series(dtype=str))).fillna("") != "completed"]
    acceptance_fails = df[df.get("acceptance_status", pd.Series(index=df.index, dtype=str)).fillna("") == "fail"]
    sim_fails.to_csv(RESULTS / "simulation_failures.csv", index=False)
    acceptance_fails.to_csv(RESULTS / "acceptance_failures.csv", index=False)
    pd.concat([sim_fails, acceptance_fails]).drop_duplicates(subset=["case"]).to_csv(RESULTS / "failures.csv", index=False)
    (RESULTS / "validation_policy.json").write_text(json.dumps(POLICY.to_dict(), indent=2), encoding="utf-8")
    write_completion_reports(RESULTS, summaries, args.suite)
    print(f"Done: {RESULTS} | simulation_failures={len(sim_fails)} | acceptance_failures={len(acceptance_fails)}")
    if len(sim_fails):
        raise SystemExit(2)
    if len(acceptance_fails) and not args.allow_acceptance_fail:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
