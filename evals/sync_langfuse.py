"""Push prompts and eval dataset to Langfuse.

Usage:
    uv run python evals/sync_langfuse.py            # sync prompts + dataset
    uv run python evals/sync_langfuse.py --prompts  # prompts only
    uv run python evals/sync_langfuse.py --dataset  # dataset only
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langfuse import Langfuse
from loguru import logger

from tweakcv.harness_loader import LLM_TEMPERATURE
from tweakcv.settings import settings

HARNESS_PATH = Path(__file__).parent.parent / "tweakcv" / "harness.json"
DATASET_PATH = Path(__file__).parent / "dataset.json"
DATASET_NAME = "tweakcv-evals"


def sync_prompts(langfuse: Langfuse) -> None:
    harnesses: list[dict] = json.loads(HARNESS_PATH.read_text())  # type: ignore[type-arg]
    for h in harnesses:
        name = h["id"]
        prompt_text = h["system_prompt"]
        try:
            langfuse.create_prompt(
                name=name,
                prompt=prompt_text,
                labels=["production"],
                type="text",
                config={"model_name": h.get("model_name", ""), "temperature": LLM_TEMPERATURE},
            )
            logger.info(f"prompt_synced id={name}")
        except Exception as exc:
            logger.warning(f"prompt_sync_failed id={name} error={exc}")


def sync_dataset(langfuse: Langfuse) -> None:
    with contextlib.suppress(Exception):
        langfuse.create_dataset(
            name=DATASET_NAME,
            description="TweakCV offline eval examples — keyword coverage, hallucination, format checks",
        )
        logger.info(f"dataset_created name={DATASET_NAME}")

    examples: list[dict] = json.loads(DATASET_PATH.read_text())  # type: ignore[type-arg]
    for ex in examples:
        try:
            langfuse.create_dataset_item(
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
            logger.info(f"dataset_item_synced id={ex['id']}")
        except Exception as exc:
            logger.warning(f"dataset_item_failed id={ex['id']} error={exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync prompts and eval dataset to Langfuse.")
    parser.add_argument("--prompts", action="store_true", help="Sync prompts only")
    parser.add_argument("--dataset", action="store_true", help="Sync dataset only")
    args = parser.parse_args()

    do_all = not args.prompts and not args.dataset

    langfuse = Langfuse(
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )

    if do_all or args.prompts:
        logger.info("Syncing prompts to Langfuse...")
        sync_prompts(langfuse)

    if do_all or args.dataset:
        logger.info("Syncing eval dataset to Langfuse...")
        sync_dataset(langfuse)

    langfuse.flush()
    logger.info("sync_complete")


if __name__ == "__main__":
    main()
