"""Default settings for reproducible, synthetic FlowFreeze data."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_RANDOM_SEED = 42
DEFAULT_BASE_TIME = "2026-09-01T09:00:00+00:00"
NEXT_MOVE_WINDOW_MINUTES = 5
DEFAULT_CASES_PER_SCENARIO = 100
# Every scenario family is represented in each split. Whole case IDs stay in
# exactly one split so wallet/transaction rows from a case cannot leak across.
SPLIT_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
