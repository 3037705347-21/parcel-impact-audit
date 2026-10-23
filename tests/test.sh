#!/usr/bin/env bash
set -u

reward_file=/logs/verifier/reward.txt
JUNIT_FILE=/logs/verifier/junit.xml
mkdir -p /logs/verifier

write_reward_zero() {
  chmod 0644 "$reward_file" 2>/dev/null || true
  echo "0" > "$reward_file"
  chmod 0444 "$reward_file"
}

write_reward_zero

trap 'write_reward_zero' EXIT
trap 'write_reward_zero; exit 130' INT TERM HUP

if ! python -m pip install --user --no-cache-dir --disable-pip-version-check \
  --require-hashes --only-binary=:all: -r /tests/requirements.txt; then
  write_reward_zero
  exit 0
fi

cd /workspace
timeout 240s python -m pytest -vv --junitxml "$JUNIT_FILE" /tests/test_outputs.py

if ! test -s "$JUNIT_FILE"; then
  write_reward_zero
  exit 0
fi

python3 - "$JUNIT_FILE" "$reward_file" <<'PY'
import os
import sys
import xml.etree.ElementTree as ET

report_path, reward_path = sys.argv[1:]
groups = {
    "C1": (0.14, "test_c1_"),
    "C2": (0.18, "test_c2_"),
    "C3": (0.10, "test_c3_"),
    "C4": (0.10, "test_c4_"),
    "C5": (0.30, "test_c5_"),
    "E2E": (0.18, "test_e2e_"),
}
if not os.path.isfile(report_path) or os.path.getsize(report_path) == 0:
    statuses = {}
else:
    try:
        tree = ET.parse(report_path)
        statuses = {}
        for case in tree.findall(".//testcase"):
            name = case.attrib.get("name", "")
            failed = case.find("failure") is not None or case.find("error") is not None
            skipped = case.find("skipped") is not None
            statuses[name] = not failed and not skipped
    except (OSError, ET.ParseError):
        statuses = {}

weighted_total = 0.0
INCOMPLETE = not statuses
for weight, prefix in groups.values():
    relevant = [passed for name, passed in statuses.items() if name.startswith(prefix)]
    if not relevant:
        INCOMPLETE = True
    elif all(relevant):
        weighted_total += weight

if INCOMPLETE:
    weighted_total = 0.0
weighted_total = min(1.0, max(0.0, weighted_total))
os.chmod(reward_path, 0o644)
with open(reward_path, "w", encoding="utf-8") as handle:
    handle.write(f"{weighted_total:.6f}\n")
os.chmod(reward_path, 0o444)
PY

trap - EXIT INT TERM HUP
exit 0
