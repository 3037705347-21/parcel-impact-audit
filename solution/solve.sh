#!/usr/bin/env bash
set -euo pipefail

install -m 0644 /solution/oracle/model.py /workspace/impact_audit/model.py
install -m 0644 /solution/oracle/linalg.py /workspace/impact_audit/linalg.py
install -m 0644 /solution/oracle/pair.py /workspace/impact_audit/pair.py
install -m 0644 /solution/oracle/cli.py /workspace/impact_audit/cli.py
install -m 0644 /solution/oracle/__init__.py /workspace/impact_audit/__init__.py
install -m 0644 /solution/oracle/__main__.py /workspace/impact_audit/__main__.py
