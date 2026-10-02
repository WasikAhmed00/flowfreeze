"""Restore the seeded synthetic FlowFreeze data and SQLite demo database."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_generator.config import DEFAULT_DATA_DIR, DEFAULT_RANDOM_SEED
from data_generator.generate import generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    counts = generate_dataset(args.data_dir, args.seed)
    print(f"Demo data reset at {args.data_dir.resolve()} (seed={args.seed}): {counts}")


if __name__ == "__main__":
    main()
