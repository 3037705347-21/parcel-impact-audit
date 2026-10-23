#!/usr/bin/env bash
set -u

REWARD_FILE=/logs/verifier/reward.txt
STATUS_FILE=/logs/verifier/verification-status.txt
JUNIT_FILE=/logs/verifier/junit.xml
SITE_PACKAGES=/tmp/verifier-site
TRUSTED_PYTHON=/usr/local/bin/python3
TRUSTED_TIMEOUT=/usr/bin/timeout
mkdir -p /logs/verifier "$SITE_PACKAGES"
cp -R \
  /usr/local/lib/python3.12/site-packages/pip \
  /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
  "$SITE_PACKAGES"/

write_stopped() {
  chmod 0644 "$REWARD_FILE" "$STATUS_FILE" 2>/dev/null || true
  echo "0" > "$REWARD_FILE"
  echo "INCOMPLETE: verifier stopped before scoring" > "$STATUS_FILE"
  chmod 0444 "$REWARD_FILE" "$STATUS_FILE"
}

write_stopped
trap 'write_stopped' EXIT
trap 'write_stopped; exit 130' INT TERM HUP

if ! env -i \
  PATH=/usr/local/bin:/usr/bin:/bin \
  HOME=/tmp \
  PYTHONPATH="$SITE_PACKAGES:/tests" \
  PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  "$TRUSTED_PYTHON" -S -m pip install \
    --target "$SITE_PACKAGES" \
    --no-cache-dir \
    --disable-pip-version-check \
    --require-hashes \
    --only-binary=:all: \
    -r /tests/requirements.txt \
    --quiet; then
  write_stopped
  exit 0
fi

cd /workspace
env -i \
  PATH=/usr/local/bin:/usr/bin:/bin \
  HOME=/tmp \
  PYTHONPATH="$SITE_PACKAGES:/tests" \
  PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  "$TRUSTED_TIMEOUT" --signal=TERM --kill-after=10s 240s \
  "$TRUSTED_PYTHON" -S -s -P -B -m pytest \
    -p no:cacheprovider \
    --junitxml "$JUNIT_FILE" \
    /tests/test_outputs.py -vv

if ! env -i \
  PATH=/usr/local/bin:/usr/bin:/bin \
  HOME=/tmp \
  PYTHONPATH="$SITE_PACKAGES:/tests" \
  PYTHONNOUSERSITE=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  "$TRUSTED_PYTHON" -S -s -P -B \
    /tests/score.py "$JUNIT_FILE" "$REWARD_FILE" "$STATUS_FILE"; then
  write_stopped
  exit 0
fi

trap - EXIT INT TERM HUP
exit 0
