#!/usr/bin/env bash
set -euo pipefail

# Render's build image is the source of truth for the demo snapshot. Keep the
# seed configurable, but deterministic by default so every deploy is reviewable.
SEED="${RANDOM_SEED:-42}"
python -m data_generator.generate --seed "$SEED"
python -m ml.train --seed "$SEED"

# Keep startup independent of an interactive shell and fail the build if the
# generated runtime inputs are missing.
test -s data/flowfreeze.db
test -s ml/artifacts/fraud_model.joblib
test -s ml/artifacts/next_move_model.joblib
