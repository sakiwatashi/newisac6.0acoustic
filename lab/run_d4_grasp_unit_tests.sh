#!/usr/bin/env bash
# Zero-GPU unit tests for D4 Track B obs/reward + Track A analyzer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/lab/test_acoustic_grasp_obs_reward.py"
python3 "$ROOT/scripts/analyze_d4_sm_grasp.py" --self-test
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('$ROOT/scripts/d4_grasp_common.py').read_text())"
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('$ROOT/scripts/d4_acoustic_grasp_sm_runner.py').read_text())"
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('$ROOT/scripts/d3_grasp_runner.py').read_text())"
echo "run_d4_grasp_unit_tests: ALL PASSED"
