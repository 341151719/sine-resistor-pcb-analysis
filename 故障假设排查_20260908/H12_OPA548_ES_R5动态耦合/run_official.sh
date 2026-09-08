#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p results_h12
ngspice -b es_dynamic_loop.cir | tee official_run.log
