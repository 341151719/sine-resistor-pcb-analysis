#!/usr/bin/env python3
"""Reproduce current/transfer/startup checks; no hardware root-cause sign-off."""
import json
import math
import os
from pathlib import Path
import re
import subprocess


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "早期错误复现"
OUTPUT = HERE / "results_reassessment"
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def metric(log, name):
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*({NUMBER})", log, re.M | re.I)
    if not match or not math.isfinite(float(match[1])):
        raise RuntimeError(f"Missing or non-finite measurement: {name}")
    return float(match[1])


def simulate(name, deck, measurements):
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / f"{name}.cir").write_text(deck, encoding="utf-8")
    # BASE provides .spiceinit (PSpice compatibility) and relative model includes.
    # Saved diagnostic decks must also be run with BASE as the working directory.
    result = subprocess.run(
        [os.environ.get("NGSPICE", "ngspice"), "-b"], input=deck,
        cwd=BASE, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=60, check=False,
    )
    (OUTPUT / f"{name}.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode or re.search(
        r"^\s*(?:fatal error|error[: ]|.*simulation\(s\) aborted)|timestep too small",
        result.stdout, re.M | re.I,
    ):
        raise RuntimeError(f"Simulation failed: {name}; see {OUTPUT}")
    return {key: metric(result.stdout, key) for key in measurements}


def main():
    summary = {"status": "running", "scope": "model evidence, not hardware sign-off"}
    OUTPUT.mkdir(exist_ok=True)
    summary_path = OUTPUT / "summary.json"
    # Invalidate any earlier successful summary before starting a new run.
    summary_path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
    try:
        summary["rail_current"] = {}
        for amplitude in (1, 2, 3, 4):
            deck = (BASE / f"02_opa_on_105k_amp{amplitude}V.cir").read_text(encoding="utf-8")
            values = simulate(f"current_{amplitude}V", deck,
                              ("out_pp", "ip_draw_pk", "in_draw_pk", "ip_draw_avg", "in_draw_avg"))
            if not (0 < values["ip_draw_avg"] < values["ip_draw_pk"]
                    and 0 < values["in_draw_avg"] < values["in_draw_pk"]):
                raise RuntimeError("Unexpected rail-current polarity or peak/mean ordering")
            summary["rail_current"][str(amplitude)] = values

        common = (BASE / "fault_fixed_common.inc").read_text(encoding="utf-8")
        ac = "* 105 kHz small-signal transfer\n.param R16VAL=39k\n" + common + """
.control
set noaskquit
alter @VINPUT[acmag]=1
ac lin 1 105k 105k
let gainmag=mag(v(TP8))
let gainphase=180/PI*ph(v(TP8))
print gainmag gainphase
quit
.endc
.end
"""
        summary["ac_105k"] = simulate("ac_105k", ac, ("gainmag", "gainphase"))
        if not 35 < summary["ac_105k"]["gainmag"] < 45:
            raise RuntimeError("Unexpected nominal 105 kHz gain; review topology/model")

        summary["startup"] = {}
        for amplitude in (0.25, -0.25):
            for method in ("gear", "trap"):
                body, replacements = re.subn(
                    r"^VINPUT .*", f"VINPUT SRC 0 PULSE(0 {amplitude} 10u 20n 20n 10u 1)",
                    common, flags=re.M,
                )
                if replacements != 1 or common.count("method=gear") != 1:
                    raise RuntimeError("Shared deck changed; review diagnostic transformation")
                body = body.replace("method=gear", f"method={method}")
                deck = "* Finite large-start pulse, fixed-OFF topology\n.param R16VAL=39k\n" + body + """
.control
set noaskquit
tran 0.05u 5m 0 0.05u
meas tran latepp PP v(TP8) from=4.5m to=5m
meas tran earlypp PP v(TP8) from=10u to=100u
quit
.endc
.end
"""
                name = f"startup_{'pos' if amplitude > 0 else 'neg'}_{method}"
                values = simulate(name, deck, ("latepp", "earlypp"))
                # Detect accidentally missing stimulation and loss of the observed baseline.
                if not (values["earlypp"] > 5 and 0 <= values["latepp"] < 1e-3):
                    raise RuntimeError(f"Startup response changed: {name}; inspect waveform")
                summary["startup"][name] = values

        summary["feedback_105k_sinusoidal"] = []
        for capacitance_pf in (0, 22, 47, 68, 100, 220):
            zf = 39000 / (1 + 2j * math.pi * 105000 * 39000 * capacitance_pf * 1e-12)
            beta = 1000 / (1000 + zf)
            summary["feedback_105k_sinusoidal"].append({
                "cfb_pf": capacitance_pf, "magnitude": abs(beta),
                "phase_deg": math.degrees(math.atan2(beta.imag, beta.real)),
                "vminus_vpp_for_18vpp_sine": 18 * abs(beta),
            })
        summary["status"] = "checks_passed_root_cause_unresolved"
    except Exception as error:
        summary.update(status="failed", error=str(error))
        raise
    finally:
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
