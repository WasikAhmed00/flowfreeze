"""Default settings for reproducible, synthetic FlowFreeze data."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_RANDOM_SEED = 42
DEFAULT_BASE_TIME = "2026-09-01T09:00:00+00:00"
NEXT_MOVE_WINDOW_MINUTES = 5

SPLIT_BY_SCENARIO_FAMILY = {
    # Keeping scenario families together prevents near-duplicate flows crossing splits.
    "direct_fraud": "train",
    "fanout": "train",
    "multi_hop": "train",
    "mixed_balance": "train",
    "rapid_cashout": "validation",
    "fanout_cashout": "test",
    "false_positive": "validation",
    "wrong_recipient": "test",
}
