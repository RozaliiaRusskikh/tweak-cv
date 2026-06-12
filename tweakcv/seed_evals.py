"""Seed Langfuse dataset from evals/dataset.json.

Run once (or any time dataset.json changes):

    uv run python -m tweakcv.seed_evals
"""

import json
from pathlib import Path

from loguru import logger

from tweakcv.clients import get_langfuse

DATASET_NAME = "tweakcv-evals"
DATASET_PATH = Path(__file__).parent.parent / "evals" / "dataset.json"


def seed() -> None:
    client = get_langfuse()
    examples: list[dict] = json.loads(DATASET_PATH.read_text())  # type: ignore[type-arg]

    client.create_dataset(
        name=DATASET_NAME,
        description="Labelled JD + base resume examples for offline eval runs",
    )

    for ex in examples:
        client.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=ex["id"],
            input={
                "jd_text": ex["jd_text"],
                "base_resume": ex["base_resume"],
                "expected_keywords": ex["expected_keywords"],
            },
            expected_output=ex.get("expected_scores", {}),
            metadata={
                "id": ex["id"],
                "description": ex.get("description", ""),
            },
        )
        logger.info(f"eval_item_seeded id={ex['id']}")

    logger.info(f"seed_evals_done count={len(examples)} dataset={DATASET_NAME}")


if __name__ == "__main__":
    seed()
