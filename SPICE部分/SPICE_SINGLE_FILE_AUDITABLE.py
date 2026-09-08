#!/usr/bin/env python3
"""Single-file, auditable Python + ngspice model of active acoustic impedance.

Purpose
-------
This file contains the core SPICE circuit, explicit reduced-order dynamic device
models, the electrodynamic loudspeaker, loop-injection points, the test matrix,
the ngspice launcher, and lightweight result checks.  It needs only Python 3.9+
and an ngspice executable; it does not import NumPy/Pandas.

The embedded circuit is an implementation-level *behavioral* reference:

    target R(t) -> DAC-equivalent command VK
                -> current sense (RSHUNT, gain 50)
                -> four-quadrant multiply (ISIG * VK / 10)
                -> post gain 20
                -> bounded power follower
                -> loudspeaker port

Unlike an instantaneous ideal model, every signal-chain block below has finite
gain/bandwidth and named poles.  Supply impedance, shunt/trace inductance, output
isolation and a Zobel are explicit.  VLOOP is a Middlebrook-style series injection
point between controller output VCMD_CTRL and power-stage input VCMD.

It preserves the central control contract V_port = (R_target-Re)*I_port and the
electro-mechanical loudspeaker equations.  The reduced-order parameters are
auditable engineering assumptions, not substitutes for vendor-macromodel/PCB
signoff.  Static analysis must distinguish those two evidence levels.

Examples
--------
    python3 SPICE_SINGLE_FILE_AUDITABLE.py --suite smoke
    python3 SPICE_SINGLE_FILE_AUDITABLE.py --suite all
    python3 SPICE_SINGLE_FILE_AUDITABLE.py --suite stability
    NGSPICE_BIN=/path/to/ngspice python3 SPICE_SINGLE_FILE_AUDITABLE.py --suite all

Exit codes: 0=all selected simulations completed; 2=environment/simulation error.
"""

from __future__ import annotations

import argparse
import cmath
import csv
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, replace


# Core parameters from the requirement package.
@dataclass(frozen=True)
class Speaker:
    # Datasheet constraints retained in this single file even when the lumped
    # low-frequency SPICE model does not directly consume them.
    rated_power_w: float = 30.0
    nominal_impedance_ohm: float = 8.0
    frequency_min_hz: float = 80.0
    frequency_max_hz: float = 20000.0
    sensitivity_db_1w_1m: float = 86.0
    opening_angle_deg_at_4khz: float = 113.0
    magnetic_induction_t: float = 0.95
    magnetic_flux_wb: float = 180e-6
    front_pole_plate_height_m: float = 3e-3
    voice_coil_diameter_m: float = 20e-3
    winding_height_m: float = 6e-3
    cutout_diameter_m: float = 100e-3
    net_weight_kg: float = 0.38
    Re: float = 7.2          # voice-coil DC resistance, ohm
    Le: float = 0.2e-3       # voice-coil inductance, H
    Bl: float = 4.6          # force factor, T*m
    Mms: float = 5.7e-3      # moving mass, kg
    fs: float = 90.0         # resonance frequency, Hz
    Qms: float = 2.29        # mechanical Q
    Sd: float = 0.005        # piston area, m^2
    XMAX: float = 0.004      # one-way excursion limit, m
    Qes_datasheet: float = 0.95
    Qts_datasheet: float = 0.67
    Vas_datasheet_m3: float = 2.3e-3


@dataclass(frozen=True)
class Case:
    name: str
    R0: float = 50.5
    A1: float = 49.5
    fm1: float = 100.0
    ph1: float = 0.0
    A2: float = 0.0
    fm2: float = 317.0
    ph2: float = 0.0
    RMIN: float = 1.0
    RMAX: float = 100.0
    Pamp: float = 0.0
    fa: float = 120.0
    ItestAmp: float = 1e-3
    ItestFreq: float = 1000.0
    TSTART: float = 5e-3
    TRAMP: float = 5e-3
    tstop: float = 0.04
    tstep: float = 1e-6
    RSH: float = 0.1
    RSNUB: float = 4.7
    CSNUB: float = 47e-9
    analysis: str = "tran"
    ACMODE: float = 0.0
    RDRV_PAR: float = 0.03
    LDRV_PAR: float = 80e-9
    RSPK_PAR: float = 0.04
    LSPK_PAR: float = 120e-9
    RSPEAKER_SERIES: float = 0.08
    RISO_OUT: float = 0.05
    RZOBEL: float = 10.0
    CZOBEL: float = 100e-9
    RAIL_R: float = 0.08


# This is the complete embedded SPICE core.  No .include or external model file
# is used.  Voltages at VEL and XNODE represent velocity (m/s) and displacement
# (m), respectively, using the mobility analogy.
SPICE_TEMPLATE = r"""
.title Single-file stability-auditable active acoustic impedance boundary
.options method=gear maxord=2 reltol=3e-5 abstol=1e-10 vabstol=1e-7 chgtol=1e-14
.options gmin=1e-12 rshunt=1e12
.temp 27
.param PI=3.141592653589793 TWOPI=6.283185307179586 TEMP=27

* =======================================================================
* REDUCED-ORDER DEVICE MODELS FOR SEMANTIC/STABILITY REVIEW
* =======================================================================
* These compact models make the stability assumptions visible.  A0/GBW set
* the dominant pole; FP2 exposes the unverified high-frequency pole.  Reviewers
* should sweep FP2, ROUT, rail impedance and parasitics, then confirm conclusions
* with the exact manufacturer revisions before hardware signoff.

* INA149 difference amplifier approximation: gain=1, 500 kHz signal pole,
* 3 MHz second pole, 50 ohm output.  CMRR/feedthrough and overload recovery are
* intentionally not certified by this reduced model.
.subckt INA149_RM INP INN OUT PARAMS: GAIN=1 FP1=500k FP2=3Meg ROUT=50 OFFSET=0
EINA_RAW INA_RAW 0 VALUE={GAIN*(V(INP)-V(INN))+OFFSET}
RINA_P1 INA_RAW INA_P1 1k
CINA_P1 INA_P1 0 {1/(TWOPI*FP1*1k)}
RINA_P2 INA_P1 INA_P2 1k
CINA_P2 INA_P2 0 {1/(TWOPI*FP2*1k)}
RINA_OUT INA_P2 OUT {ROUT}
RINA_LOAD OUT 0 100Meg
.ends INA149_RM

* OPA1656 approximation: A0=31.6 MV/V, GBW=53 MHz => dominant pole 1.677 Hz.
* FP2=80 MHz is an explicit sensitivity parameter; ROUT and rail headroom are
* included.  Slew-rate/distortion/noise require the vendor model or bench data.
.subckt OPA1656_RM INP INN OUT VP VN PARAMS: A0=31.6Meg GBW=53Meg FP2=80Meg ROUT=12 VHEAD=0.25
.param FP1={GBW/A0}
E1656_RAW O1656_RAW 0 VALUE={A0*(V(INP)-V(INN))}
R1656_P1 O1656_RAW O1656_P1 1k
C1656_P1 O1656_P1 0 {1/(TWOPI*FP1*1k)}
R1656_P2 O1656_P1 O1656_P2 1k
C1656_P2 O1656_P2 0 {1/(TWOPI*FP2*1k)}
B1656_CLIP O1656_INT 0 V={min(max(V(O1656_P2),V(VN)+VHEAD),V(VP)-VHEAD)}
R1656_OUT O1656_INT OUT {ROUT}
.ends OPA1656_RM

* AD633 four-quadrant multiplier approximation. W=(X1-X2)*(Y1-Y2)/10+Z.
* The 1 MHz/5 MHz poles and 50 ohm output make multiplier phase explicit.
.subckt AD633_RM X1 X2 Y1 Y2 Z W PARAMS: SCALE=10 FP1=1Meg FP2=5Meg ROUT=50
BMUL_RAW MUL_RAW 0 V={(V(X1)-V(X2))*(V(Y1)-V(Y2))/SCALE+V(Z)}
RMUL_P1 MUL_RAW MUL_P1 1k
CMUL_P1 MUL_P1 0 {1/(TWOPI*FP1*1k)}
RMUL_P2 MUL_P1 MUL_P2 1k
CMUL_P2 MUL_P2 0 {1/(TWOPI*FP2*1k)}
RMUL_OUT MUL_P2 W {ROUT}
RMUL_LOAD W 0 100Meg
.ends AD633_RM

* OPA548 power amplifier approximation. A0=100k, GBW=1 MHz, FP2=2 MHz.
* Voltage headroom and 80 milliohm output resistance are explicit.  IOUT is
* reported by the external probe; exact current-limit foldback, SOA and thermal
* shutdown remain mandatory vendor-model/bench checks.
.subckt OPA548_RM INP INN OUT VP VN PARAMS: A0=100k GBW=1Meg FP2=2Meg ROUT=0.08 VHEAD=2 IOUT=1.52
.param FP1={GBW/A0}
E548_RAW O548_RAW 0 VALUE={A0*(V(INP)-V(INN))}
R548_P1 O548_RAW O548_P1 1k
C548_P1 O548_P1 0 {1/(TWOPI*FP1*1k)}
R548_P2 O548_P1 O548_P2 1k
C548_P2 O548_P2 0 {1/(TWOPI*FP2*1k)}
B548_CLIP O548_INT 0 V={min(max(V(O548_P2),V(VN)+VHEAD),V(VP)-VHEAD)}
R548_OUT O548_INT OUT {ROUT}
.ends OPA548_RM

* =======================================================================
* SPEAKER, COMMAND AND HARDWARE PARAMETERS
* =======================================================================
.param Re=@@Re@@ Le=@@Le@@ Bl=@@Bl@@ Mms=@@Mms@@ fs=@@fs@@ Qms=@@Qms@@
.param Sd=@@Sd@@ XMAX=@@XMAX@@ W0={TWOPI*fs}
.param Cms={1/(Mms*W0*W0)} Rms={W0*Mms/Qms} Kms={1/Cms}

.param R0=@@R0@@ A1=@@A1@@ fm1=@@fm1@@ ph1=@@ph1@@
.param A2=@@A2@@ fm2=@@fm2@@ ph2=@@ph2@@ RMIN=@@RMIN@@ RMAX=@@RMAX@@
.param TSTART=@@TSTART@@ TRAMP=@@TRAMP@@ ACMODE=@@ACMODE@@
.func Rraw(t)   {R0+A1*sin(TWOPI*fm1*t+ph1)+A2*sin(TWOPI*fm2*t+ph2)}
.func Rt_des(t) {min(max(Rraw(t),RMIN),RMAX)}
.func Rx_des(t) {Rt_des(t)-Re}
.func soft(t)   {min(max((t-TSTART)/TRAMP,0),1)}
* ACMODE=1 freezes the time-varying command at R0 for an LTI AC operating point.
.func Rx_cmd(t) {(1-ACMODE)*soft(t)*Rx_des(t)+ACMODE*(R0-Re)}
.func Rt_cmd(t) {Re+Rx_cmd(t)}

.param Pamp=@@Pamp@@ fa=@@fa@@ ItestAmp=@@ItestAmp@@ ItestFreq=@@ItestFreq@@
.param RSH=@@RSH@@ IOUTLIM=1.52
.param RDRV_PAR=@@RDRV_PAR@@ LDRV_PAR=@@LDRV_PAR@@
.param RSPK_PAR=@@RSPK_PAR@@ LSPK_PAR=@@LSPK_PAR@@
.param RSPEAKER_SERIES=@@RSPEAKER_SERIES@@ RISO_OUT=@@RISO_OUT@@
.param RZOBEL=@@RZOBEL@@ CZOBEL=@@CZOBEL@@ RAIL_R=@@RAIL_R@@

* =======================================================================
* NON-IDEAL POWER SUPPLIES; rail current and regeneration are observable
* =======================================================================
VPLUS18_SRC P18_SRC 0 18
RPLUS18 P18_SRC P18 {RAIL_R}
CPLUS18 P18 0 2200u
VMINUS18_SRC N18_SRC 0 -18
RMINUS18 N18_SRC N18 {RAIL_R}
CMINUS18 N18 0 2200u
VPLUS15_SRC P15_SRC 0 15
RPLUS15 P15_SRC P15 0.5
CPLUS15 P15 0 100u
VMINUS15_SRC N15_SRC 0 -15
RMINUS15 N15_SRC N15 0.5
CMINUS15 N15 0 100u

* =======================================================================
* CONTROL PATH: sense -> gain 50 -> multiply by Rx/10 -> gain 20 -> power
* =======================================================================
* Current direction: Iport=(V(SPK)-V(DRV))/RSH, positive from SPK to DRV.
* The selected polarities give VCMD=Rx*Iport.  No instantaneous V/I division
* exists anywhere in the feedback path.

* DAC/level-shift equivalent.  Three visible low-pass sections approximate
* reconstruction filtering plus update/settling delay; sweep 20/80/200 kHz.
BVK_RAW VK_RAW 0 V={Rx_cmd(time)/10}
RVK1 VK_RAW VK1 1k
CVK1 VK1 0 {1/(TWOPI*20k*1k)}
RVK2 VK1 VK2 1k
CVK2 VK2 0 {1/(TWOPI*80k*1k)}
RVK3 VK2 VK 1k
CVK3 VK 0 {1/(TWOPI*200k*1k)}

R_DRV_PAR DRV_SRC DRV_R {RDRV_PAR}
L_DRV_PAR DRV_R DRV {LDRV_PAR}
RSHUNT DRV SPK {RSH}
R_SPK_PAR SPK SPK_R {RSPK_PAR}
L_SPK_PAR SPK_R SPK_LOAD_PORT {LSPK_PAR}
R_SPEAKER_SERIES SPK_LOAD_PORT SPK_LOAD {RSPEAKER_SERIES}

XU_INA SPK DRV VSENSE INA149_RM

* OPA1656 U4A, non-inverting gain 1+49k/1k = 50.
R_U4A_G NFB_A 0 1k
R_U4A_F ISIG NFB_A 49k
C_U4A_F ISIG NFB_A 10p
XU_OPA_ISENSE VSENSE NFB_A ISIG P15 N15 OPA1656_RM
R_ISIG_LOAD ISIG 0 100k

* AD633; Z is reserved for a slow offset servo and is zero in this review model.
V_ZSERVO ZSERVO 0 0
XU_MULT ISIG 0 VK 0 ZSERVO MUL AD633_RM

* OPA1656 U4B, non-inverting gain 1+19k/1k = 20.
R_U4B_G NFB_B 0 1k
R_U4B_F VCMD_CTRL NFB_B 19k
C_U4B_F VCMD_CTRL NFB_B 22p
XU_OPA_POST MUL NFB_B VCMD_CTRL P15 N15 OPA1656_RM
R_VCMD_LOAD VCMD_CTRL 0 100k

* Explicit composite-loop break/injection network.  In transient mode this is
* a 0 V series connection.  In AC mode a huge inductor preserves DC bias while
* opening the loop for AC, and a grounded 1 V source excites the power input.
@@LOOP_NETWORK@@

XU_PWR VCMD SPK PA_OUT P18 N18 OPA548_RM PARAMS: IOUT=1.52
RISO PA_OUT DRV_SRC {RISO_OUT}
RZOBEL DRV_SRC NZOBEL {RZOBEL}
CZOBEL NZOBEL 0 {CZOBEL}
RSNUB PA_OUT NSNUB @@RSNUB@@
CSNUB NSNUB 0 @@CSNUB@@

* =======================================================================
* ELECTRODYNAMIC SPEAKER AND EXTERNAL PRESSURE DRIVE
* =======================================================================
LVC SPK_LOAD NL {Le}
RVC NL NR {Re}
VCOIL NR NEMF 0
BBEMF NEMF 0 V={Bl*V(VEL)}
CMASS VEL 0 {Mms} IC=0
RDAMP VEL 0 {1/Rms}
LCOMP VEL 0 {Cms} IC=0
RMECHLEAK VEL 0 1e9
BPRESS 0 VEL I={(ACMODE+(1-ACMODE)*soft(time))*Sd*Pamp*sin(TWOPI*fa*time)}
BMOTOR VEL 0 I={-Bl*I(VCOIL)}
GVEL XNODE 0 VALUE={V(VEL)}
CX XNODE 0 1 IC=0
RXLEAK XNODE 0 1e12
B_EINJ 0 SPK I={(ACMODE+(1-ACMODE)*soft(time))*ItestAmp*sin(TWOPI*ItestFreq*time)}

* =======================================================================
* OBSERVABILITY AND SAFETY PROBES (never fed back into the controller)
* =======================================================================
B_RTARGET RTARGET 0 V={Rt_cmd(time)}
B_RX RXNODE 0 V={10*V(VK)}
B_IPORT IPORT 0 V={(V(SPK)-V(DRV))/RSH}
B_SYNERR SYNERR 0 V={V(SPK)-V(RXNODE)*V(IPORT)}
B_FOLLOWERR FOLLOWERR 0 V={V(VCMD)-V(SPK)}
B_ILIMRATIO ILIMRATIO 0 V={abs((V(PA_OUT)-V(DRV_SRC))/RISO_OUT)/IOUTLIM}
B_XMAXABS XMAXABS 0 V={abs(V(XNODE))/XMAX}
B_PRAIL PRAIL 0 V={18*(-I(VPLUS18_SRC))+(-18)*(-I(VMINUS18_SRC))}

@@CONTROL@@
.end
""".lstrip()


def num(value: float) -> str:
    return f"{float(value):.12g}"


def render(case: Case, speaker: Speaker, datafile: Path) -> str:
    if case.analysis == "ac":
        control = """.control
set wr_singlescale
set wr_vecnames
op
print v(vk) v(rtarget)
ac dec 80 1 10Meg
wrdata @@DATAFILE@@ frequency v(vcmd_ctrl) v(vcmd) v(spk) v(drv) v(vsense) v(isig) v(mul)
.endc"""
        loop_network = """LLOOP_DC VCMD_CTRL VCMD 1e9
VLOOP VCMD 0 DC 0 AC 1"""
    else:
        control = """.control
set wr_singlescale
set wr_vecnames
tran @@tstep@@ @@tstop@@
wrdata @@DATAFILE@@ time v(rtarget) v(rxnode) v(spk) v(iport) v(synerr) v(xmaxabs) v(followerr) v(ilimratio) v(prail)
.endc"""
        loop_network = "VLOOP VCMD_CTRL VCMD DC 0 AC 0"
    control = control.replace("@@DATAFILE@@", datafile.name)
    control = control.replace("@@tstep@@", num(case.tstep)).replace("@@tstop@@", num(case.tstop))
    values = {
        **asdict(speaker), **asdict(case), "DATAFILE": datafile.name,
        "CONTROL": control, "LOOP_NETWORK": loop_network,
    }
    text = SPICE_TEMPLATE
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", str(value) if isinstance(value, str) else num(value))
    if "@@" in text:
        raise RuntimeError("unreplaced SPICE template marker")
    return text


def solve3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Small Gaussian-elimination solver for the [DC, cos, sin] fit."""
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-30:
            raise ArithmeticError("singular phasor fit")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [x / scale for x in a[col]]
        for row in range(3):
            if row == col:
                continue
            scale = a[row][col]
            a[row] = [a[row][j] - scale * a[col][j] for j in range(4)]
    return [a[i][3] for i in range(3)]


def affine_phasor(times: list[float], values: list[float], freq: float) -> complex:
    """Fit x(t)=dc+a*cos(wt)+b*sin(wt); return the a-j*b phasor."""
    sums = [[0.0] * 3 for _ in range(3)]
    rhs = [0.0] * 3
    omega = 2.0 * math.pi * freq
    for t, y in zip(times, values):
        row = (1.0, math.cos(omega * t), math.sin(omega * t))
        for i in range(3):
            rhs[i] += row[i] * y
            for j in range(3):
                sums[i][j] += row[i] * row[j]
    dc, a, b = solve3(sums, rhs)
    del dc
    return complex(a, -b)


def read_wrdata(path: Path) -> dict[str, list[float]]:
    # wr_singlescale plus an explicit `time` vector produces two time columns.
    columns = {k: [] for k in ("time", "rtarget", "rx", "spk", "iport", "synerr", "xmax")}
    with path.open(encoding="utf-8", errors="replace") as handle:
        next(handle)  # vector-name header
        for line in handle:
            fields = line.split()
            if len(fields) < 8:
                continue
            row = [float(x) for x in fields[:8]]
            for key, value in zip(columns, row[1:8]):
                columns[key].append(value)
    if len(columns["time"]) < 16:
        raise RuntimeError(f"insufficient data rows in {path}")
    return columns


def read_ac_wrdata(path: Path) -> dict[str, object]:
    """Read ngspice complex wrdata and estimate composite return-ratio margins.

    In AC mode VLOOP forces VCMD=1 V while LLOOP_DC opens the return path at AC.
    The auditable return-ratio convention is T=-V(VCMD_CTRL)/V(VCMD).  The sign
    convention is recorded so a reviewer can reverse/check it rather than guess.
    """
    rows: list[tuple[float, complex, complex]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        header = next(handle).lower()
        for line in handle:
            values = [float(x) for x in line.split()]
            # Complex wrdata normally emits: scale.re scale.im, frequency.re/im,
            # v(ctrl).re/im, v(input).re/im.  A real frequency scale may omit
            # the imaginary scale columns; accept both layouts explicitly.
            if len(values) >= 7:
                freq = values[1]
                ctrl = complex(values[3], values[4])
                inp = complex(values[5], values[6])
            elif len(values) >= 5:
                freq = values[1]
                ctrl = complex(values[2], 0.0)
                inp = complex(values[3], 0.0)
            else:
                continue
            if freq > 0 and abs(inp) > 1e-30:
                rows.append((freq, -ctrl / inp, inp))
    if len(rows) < 8:
        raise RuntimeError(f"unrecognized/insufficient AC data in {path}; header={header.strip()!r}")

    freqs = [row[0] for row in rows]
    mags_db = [20.0 * math.log10(max(abs(row[1]), 1e-300)) for row in rows]
    phases = []
    for row in rows:
        phase = math.degrees(cmath.phase(row[1]))
        if phase > 0.0:
            phase -= 360.0
        if phases:
            while phase - phases[-1] > 180.0:
                phase -= 360.0
            while phase - phases[-1] < -180.0:
                phase += 360.0
        phases.append(phase)

    def interpolate_crossings(values: list[float], target: float) -> list[tuple[float, int, float]]:
        found = []
        for index in range(len(values) - 1):
            y0, y1 = values[index] - target, values[index + 1] - target
            if y0 == 0.0 or y0 * y1 < 0.0:
                fraction = 0.0 if y0 == 0.0 else -y0 / (y1 - y0)
                logf = math.log10(freqs[index]) + fraction * (
                    math.log10(freqs[index + 1]) - math.log10(freqs[index])
                )
                found.append((10.0**logf, index, fraction))
        return found

    unity_details = []
    for unity_hz, index, fraction in interpolate_crossings(mags_db, 0.0):
        phase = phases[index] + fraction * (phases[index + 1] - phases[index])
        unity_details.append({
            "frequency_hz": unity_hz,
            "phase_deg": phase,
            "phase_margin_deg": 180.0 + phase,
        })

    phase_cross_details = []
    for phase_cross_hz, index, fraction in interpolate_crossings(phases, -180.0):
        mag_at_cross = mags_db[index] + fraction * (mags_db[index + 1] - mags_db[index])
        phase_cross_details.append({
            "frequency_hz": phase_cross_hz,
            "magnitude_db": mag_at_cross,
            "gain_margin_db": -mag_at_cross,
        })
    return {
        "ac_points": len(rows),
        "return_ratio_db_min": min(mags_db),
        "return_ratio_db_max": max(mags_db),
        "unity_crossings": unity_details,
        "worst_phase_margin_deg": min((x["phase_margin_deg"] for x in unity_details), default=None),
        "phase_crossings": phase_cross_details,
        "worst_gain_margin_db": min((x["gain_margin_db"] for x in phase_cross_details), default=None),
        "margin_method": "all crossings, log-frequency interpolation; T=-V(VCMD_CTRL)/V(VCMD)",
    }


def summarize(case: Case, data: dict[str, list[float]]) -> dict[str, object]:
    result: dict[str, object] = {
        "case": case.name,
        "simulation_status": "completed",
        "rows": len(data["time"]),
        "rtarget_min_ohm": min(data["rtarget"]),
        "rtarget_max_ohm": max(data["rtarget"]),
        "synthetic_error_rms_v": math.sqrt(sum(x * x for x in data["synerr"]) / len(data["synerr"])),
        "xmax_ratio_peak": max(abs(x) for x in data["xmax"]),
    }
    # A meaningful fixed electrical impedance estimate uses a complex phasor,
    # never point-wise V/I.  Re is added because V(SPK)/Iport is the synthesized
    # external impedance in this control convention.
    if case.ItestAmp > 0 and case.A1 == 0 and case.A2 == 0:
        start = max(case.TSTART + case.TRAMP, case.tstop - 20.0 / case.ItestFreq)
        selected = [i for i, t in enumerate(data["time"]) if t >= start]
        t = [data["time"][i] for i in selected]
        v = [data["spk"][i] for i in selected]
        current = [data["iport"][i] for i in selected]
        vp = affine_phasor(t, v, case.ItestFreq)
        ip = affine_phasor(t, current, case.ItestFreq)
        if abs(ip) > 20e-6:
            z = Speaker().Re + vp / ip
            result.update(
                impedance_real_ohm=z.real,
                impedance_imag_ohm=z.imag,
                impedance_magnitude_ohm=abs(z),
                impedance_phase_deg=math.degrees(cmath.phase(z)),
            )
    return result


def case_matrix(suite: str) -> list[Case]:
    smoke = Case("smoke_fixed_7p2", R0=7.2, A1=0.0, A2=0.0)
    if suite == "smoke":
        return [smoke]

    if suite == "stability":
        return [
            Case(f"loop_fixed_r{str(target).replace('.', 'p')}", R0=target, A1=0.0, A2=0.0,
                 ItestAmp=0.0, analysis="ac", ACMODE=1.0)
            for target in (1.0, 5.0, 7.2, 20.0, 100.0)
        ]

    cases: list[Case] = []
    for target in (1.0, 5.0, 7.2, 20.0, 100.0):
        tag = str(target).replace(".", "p")
        cases.append(Case(f"fixed_r{tag}_carrier1k", R0=target, A1=0.0, A2=0.0))
    for fm, stop in ((10.0, 0.15), (30.0, 0.09), (100.0, 0.06), (300.0, 0.04), (1000.0, 0.03)):
        cases.append(Case(f"dynamic_fm{int(fm)}_carrier10k", fm1=fm, ItestFreq=10000.0, tstop=stop, tstep=2e-6))
    cases.extend(
        [
            Case("acoustic_single_sine", Pamp=1.0, ItestAmp=0.0, tstop=0.08, tstep=2e-6),
            Case("acoustic_dual_sine", A1=30.0, A2=19.5, fm1=100.0, fm2=317.0,
                 Pamp=1.0, ItestAmp=0.0, tstop=0.08, tstep=2e-6),
        ]
    )
    return cases


def locate_ngspice() -> str:
    requested = os.environ.get("NGSPICE_BIN", "ngspice")
    found = shutil.which(requested)
    if not found:
        raise FileNotFoundError(
            f"ngspice not found (NGSPICE_BIN={requested!r}); install it or set NGSPICE_BIN"
        )
    check = subprocess.run([found, "-v"], capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError(f"ngspice -v failed: {check.stderr.strip()}")
    return found


def datasheet_consistency(speaker: Speaker) -> dict[str, float | str]:
    """Expose rather than hide the internal T/S inconsistency.

    The circuit derives Cms and Rms from Mms/fs/Qms.  Qes, Qts and Vas are
    independent datasheet values and therefore must be compared, not silently
    treated as simultaneously exact.  rho/c are nominal room-air assumptions.
    """
    rho_air = 1.204
    sound_speed = 343.0
    omega = 2.0 * math.pi * speaker.fs
    cms = 1.0 / (speaker.Mms * omega * omega)
    rms = omega * speaker.Mms / speaker.Qms
    qes_model = omega * speaker.Mms * speaker.Re / (speaker.Bl * speaker.Bl)
    qts_model = 1.0 / (1.0 / speaker.Qms + 1.0 / qes_model)
    vas_model = rho_air * sound_speed * sound_speed * speaker.Sd * speaker.Sd * cms
    return {
        "scope": "low-frequency lumped consistency audit; not a radiation/reflection model",
        "Cms_model_m_per_n": cms,
        "Rms_model_n_s_per_m": rms,
        "Qes_model": qes_model,
        "Qes_datasheet": speaker.Qes_datasheet,
        "Qts_model": qts_model,
        "Qts_datasheet": speaker.Qts_datasheet,
        "Vas_model_m3": vas_model,
        "Vas_datasheet_m3": speaker.Vas_datasheet_m3,
    }


def run_case(ngspice: str, output: Path, case: Case) -> dict[str, object]:
    case_dir = output / case.name
    case_dir.mkdir(parents=True, exist_ok=True)
    netlist = case_dir / f"{case.name}.cir"
    logfile = case_dir / f"{case.name}.log"
    datafile = case_dir / f"{case.name}.dat"
    netlist.write_text(render(case, Speaker(), datafile), encoding="utf-8")
    completed = subprocess.run(
        # cwd is already case_dir.  Basenames keep this valid even when the
        # caller supplied a relative --output directory.
        [ngspice, "-b", "-o", logfile.name, netlist.name],
        cwd=case_dir,
        capture_output=True,
        text=True,
    )
    if completed.returncode or not datafile.exists() or datafile.stat().st_size == 0:
        return {
            "case": case.name,
            "simulation_status": "ngspice_failed",
            "returncode": completed.returncode,
            "log": str(logfile.resolve()),
        }
    if case.analysis == "ac":
        result = {"case": case.name, "simulation_status": "completed", **read_ac_wrdata(datafile)}
    else:
        result = summarize(case, read_wrdata(datafile))
    result["returncode"] = completed.returncode
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("smoke", "all", "stability"), default="smoke")
    parser.add_argument("--output", type=Path, default=Path("single_file_spice_results"))
    args = parser.parse_args()

    try:
        ngspice = locate_ngspice()
    except Exception as exc:
        print(f"ENVIRONMENT ERROR: {exc}", file=sys.stderr)
        return 2

    args.output.mkdir(parents=True, exist_ok=True)
    consistency = datasheet_consistency(Speaker())
    (args.output / "model_assumptions.json").write_text(
        json.dumps({"speaker": asdict(Speaker()), "derived_consistency": consistency}, indent=2),
        encoding="utf-8",
    )
    print("MODEL CONSISTENCY:", json.dumps(consistency, ensure_ascii=False), flush=True)
    cases = case_matrix(args.suite)
    results: list[dict[str, object]] = []
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case.name}", flush=True)
        try:
            result = run_case(ngspice, args.output, case)
        except Exception as exc:
            result = {"case": case.name, "simulation_status": "postprocess_failed", "error": repr(exc)}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    summary_json = args.output / "summary.json"
    summary_json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = sorted({key for row in results for key in row})
    with (args.output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    failures = [row for row in results if row.get("simulation_status") != "completed"]
    print(f"RESULT: cases={len(results)} completed={len(results)-len(failures)} failures={len(failures)}")
    print(f"OUTPUT: {args.output.resolve()}")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
