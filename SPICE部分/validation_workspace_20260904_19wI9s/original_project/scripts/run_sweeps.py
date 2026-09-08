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

ROOT = Path(__file__).resolve().parents[1]
NGSPICE_BIN = os.getenv("NGSPICE_BIN", "ngspice")
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


def sf(x: float) -> str:
    return f"{float(x):.12g}"


def safe(x) -> str:
    return str(x).replace("-", "m").replace(".", "p").replace("+", "")


def mapping(spk: SpeakerTS, cfg: SimConfig, datafile: str) -> dict[str, str]:
    d = {k: sf(v) for k, v in asdict(spk).items()}
    d.update({k: sf(v) for k, v in asdict(cfg).items()})
    d["DATAFILE"] = datafile
    d["MODEL_INCLUDE"] = "../../../spice/models/ngspice_compatible_macros.lib"
    return d


def render(template: str, spk: SpeakerTS, cfg: SimConfig, datafile: str) -> str:
    txt = template
    for k, v in mapping(spk, cfg, datafile).items():
        txt = txt.replace(f"__{k}__", v)
    if "__" in txt:
        raise ValueError("Unreplaced template marker remains in rendered netlist")
    return txt


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


def least_squares_reff(df: pd.DataFrame, spk: SpeakerTS, tail: pd.Series) -> tuple[float, float, int]:
    """Return total effective resistance Re + Rx_fit from Vspk ≈ Rx_fit*Iport."""
    ip = df.loc[tail, "v(iport)"].to_numpy(float)
    v = df.loc[tail, "v(spk)"].to_numpy(float)
    finite_mask = np.isfinite(ip) & np.isfinite(v)
    ip = ip[finite_mask]
    v = v[finite_mask]
    if ip.size == 0:
        return float("nan"), float("nan"), 0
    # Avoid meaningless fit when current is almost zero.
    pk = float(np.nanmax(np.abs(ip)))
    thr = max(50e-6, 0.02 * pk)
    m = np.abs(ip) >= thr
    ip = ip[m]
    v = v[m]
    denom = float(np.sum(ip * ip))
    if ip.size < 8 or denom <= 1e-24:
        return float("nan"), float("nan"), int(ip.size)
    rx_fit = float(np.sum(v * ip) / denom)
    return spk.Re + rx_fit, rx_fit, int(ip.size)


def summarize(df: pd.DataFrame, spk: SpeakerTS, cfg: SimConfig, name: str, model: str) -> dict:
    tail_start = float(df["tail_start_s"].iloc[0]) if "tail_start_s" in df.columns else 0.5 * float(df["time"].max())
    tail = df["time"] >= tail_start
    valid = df.get("valid_reff_pointwise", pd.Series(np.ones(len(df), dtype=int))).astype(bool)
    vt = tail & valid

    reff_fit, rx_fit, fit_n = least_squares_reff(df, spk, tail)
    rtarget_tail_mean = amean(df.loc[tail, "v(rtarget)"])
    rtarget_tail_rms_dev = rms(df.loc[tail, "v(rtarget)"] - rtarget_tail_mean)

    rx_i = df.loc[tail, "rx_iport_v"] if "rx_iport_v" in df.columns else pd.Series(dtype=float)
    denom_v = max(rms(rx_i), 1e-12)

    s = {
        "case": name,
        "model": model,
        "status": "ok",
        "tail_start_s": tail_start,
        "softstart_tstart_s": cfg.TSTART,
        "softstart_tramp_s": cfg.TRAMP,
        "pamp_pa": cfg.Pamp,
        "itest_amp_a": cfg.ItestAmp,
        "itest_freq_hz": cfg.ItestFreq,
        "rtarget_cmd_min_ohm": amin(df["v(rtarget)"]),
        "rtarget_cmd_max_ohm": amax(df["v(rtarget)"]),
        "rtarget_des_min_ohm": amin(df["v(rdes)"]) if "v(rdes)" in df.columns else float("nan"),
        "rtarget_des_max_ohm": amax(df["v(rdes)"]) if "v(rdes)" in df.columns else float("nan"),
        "rx_cmd_min_ohm": amin(df["v(rxnode)"]),
        "rx_cmd_max_ohm": amax(df["v(rxnode)"]),
        "iport_pk_a": amax(np.abs(df["v(iport)"])),
        "iport_pk_tail_a": amax(np.abs(df.loc[tail, "v(iport)"])),
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

        # Robust primary metrics.
        "synerr_rms_tail_v": rms(df.loc[tail, "v(synerr)"]) if "v(synerr)" in df.columns else float("nan"),
        "synerr_abs_max_tail_v": amax(np.abs(df.loc[tail, "v(synerr)"])) if "v(synerr)" in df.columns else float("nan"),
        "synerr_norm_rms_tail": (rms(df.loc[tail, "v(synerr)"]) / denom_v) if "v(synerr)" in df.columns else float("nan"),
        "cmderr_rms_tail_v": rms(df.loc[tail, "v(cmderr)"]) if "v(cmderr)" in df.columns else float("nan"),
        "cmderr_abs_max_tail_v": amax(np.abs(df.loc[tail, "v(cmderr)"])) if "v(cmderr)" in df.columns else float("nan"),

        # Robust least-squares resistance estimate, most useful for fixed-R injection tests.
        "reff_fit_tail_ohm": reff_fit,
        "rx_fit_tail_ohm": rx_fit,
        "reff_fit_err_vs_tail_mean_ohm": reff_fit - rtarget_tail_mean if math.isfinite(reff_fit) else float("nan"),
        "rtarget_tail_mean_ohm": rtarget_tail_mean,
        "rtarget_tail_rms_dev_ohm": rtarget_tail_rms_dev,
        "reff_fit_sample_count": fit_n,

        # Masked pointwise V/I metrics. Still diagnostic, not primary.
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
    return s


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
    cir = case_dir / f"{name}.cir"
    cir.write_text(netlist, encoding="utf-8")
    (case_dir / f"{name}_config.json").write_text(
        json.dumps({"case": name, "model": model, "speaker": asdict(spk), "config": asdict(cfg)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if write_only:
        return {"case": name, "model": model, "status": "written_only", "cir": str(cir)}

    log = case_dir / f"{name}.log"
    r = subprocess.run([NGSPICE_BIN, "-b", "-o", str(log), str(cir)], cwd=case_dir, capture_output=True, text=True)
    if r.returncode != 0:
        return {
            "case": name,
            "model": model,
            "status": "ngspice_failed",
            "returncode": r.returncode,
            "log": str(log),
            "stdout": r.stdout[-2000:],
            "stderr": r.stderr[-2000:],
        }

    df = add_derived(read_wrdata(case_dir / datafile), spk, cfg)
    df.to_csv(case_dir / f"{name}.csv", index=False)
    summary = summarize(df, spk, cfg, name, model)
    (case_dir / f"{name}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_case(df, name, case_dir / f"{name}.png", cfg=cfg, tail_only=False)
    plot_case(df, name, case_dir / f"{name}_tail.png", cfg=cfg, tail_only=True)
    return summary


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-only", action="store_true", help="Generate case netlists/configs without running ngspice")
    ap.add_argument("--clean", action="store_true", help="Delete results/ before running")
    ap.add_argument("--case-filter", default="", help="Substring filter for case names")
    args = ap.parse_args()

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
    for name, model, cfg in case_list(base):
        if args.case_filter and args.case_filter not in name:
            continue
        print(f"RUN {name} [{model}]")
        summaries.append(run_case(name, model, cfg, spk, write_only=args.write_only))

    df = pd.DataFrame(summaries)
    df.to_csv(RESULTS / "all_summary.csv", index=False)
    fails = df[df["status"].fillna("") != "ok"] if "status" in df else pd.DataFrame()
    fails.to_csv(RESULTS / "failures.csv", index=False)
    print("Done:", RESULTS)


if __name__ == "__main__":
    main()
