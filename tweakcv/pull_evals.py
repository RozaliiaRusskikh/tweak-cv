"""Pull eval examples from Langfuse and write them back to evals/dataset.json.

Use this when you've added or edited examples in the Langfuse UI:

    uv run python -m tweakcv.pull_evals
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from tweakcv.clients import get_langfuse

DATASET_NAME = "tweakcv-evals"
DATASET_PATH = Path(__file__).parent.parent / "evals" / "dataset.json"


def pull() -> None:
    client = get_langfuse()

    try:
        dataset = client.get_dataset(DATASET_NAME)
    except Exception as exc:
        logger.error(f"pull_evals_fetch_failed dataset={DATASET_NAME} error={exc}")
        return

    examples: list[dict[str, Any]] = []
    for item in dataset.items:
        inp: dict[str, Any] = item.input or {}
        expected_output: dict[str, Any] = item.expected_output or {}
        meta: dict[str, Any] = item.metadata or {}

        examples.append(
            {
                "id": meta.get("id", str(item.id)),
                "description": meta.get("description", ""),
                "jd_text": inp.get("jd_text", ""),
                "base_resume": inp.get("base_resume", {}),
                "expected_keywords": inp.get("expected_keywords", []),
                "expected_scores": expected_output,
            }
        )

    DATASET_PATH.write_text(json.dumps(examples, indent=2) + "\n")
    logger.info(f"pull_evals_done count={len(examples)} path={DATASET_PATH}")


if __name__ == "__main__":
    pull()
