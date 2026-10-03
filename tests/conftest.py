from __future__ import annotations

from pathlib import Path

import pytest

from data_generator.generate import generate_dataset
from ml.train import train_models


@pytest.fixture(scope="session")
def generated_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Create a small but fully split synthetic dataset for the test session."""
    root = tmp_path_factory.mktemp("flowfreeze-fixture")
    data_dir = root / "data"
    artifact_dir = root / "artifacts"
    generate_dataset(data_dir, seed=42, cases_per_scenario=6)
    return {
        "data_dir": data_dir,
        "database": data_dir / "flowfreeze.db",
        "artifact_dir": artifact_dir,
    }


@pytest.fixture(scope="session")
def trained_fixture(generated_fixture: dict[str, Path]) -> dict[str, Path]:
    """Train the repository's actual sklearn pipelines once for model tests."""
    train_models(
        generated_fixture["data_dir"],
        generated_fixture["artifact_dir"],
        seed=42,
    )
    return generated_fixture


@pytest.fixture(scope="session")
def fanout_scenario() -> str:
    return "SCN-02-FANOUT-0001"
