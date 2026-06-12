"""Seed Langfuse prompts from harness.json.

Run once (or any time you want to push local prompts to Langfuse):

    uv run python -m tweakcv.seed_prompts
"""

import json
from pathlib import Path

from loguru import logger

from tweakcv.clients import get_langfuse
from tweakcv.harness_loader import LLM_TEMPERATURE

HARNESS_PATH = Path(__file__).parent / "harness.json"


def seed() -> None:
    client = get_langfuse()
    harnesses: list[dict[str, str]] = json.loads(HARNESS_PATH.read_text())

    for harness in harnesses:
        prompt_id = harness["id"]
        prompt_text = harness["system_prompt"]
        model = harness["model_name"]

        client.create_prompt(
            name=prompt_id,
            prompt=prompt_text,
            config={"model": model, "temperature": LLM_TEMPERATURE},
            labels=["production"],
        )
        logger.info(f"prompt_seeded id={prompt_id}")

    from tweakcv.settings import settings

    logger.info(f"seed_prompts_done count={len(harnesses)} host={settings.langfuse_host}")


if __name__ == "__main__":
    seed()
