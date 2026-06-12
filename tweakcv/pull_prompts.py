"""Pull production prompts from Langfuse and write them back to harness.json.

Use this when you've edited prompts in the Langfuse UI and want harness.json
to reflect those changes:

    uv run python -m tweakcv.pull_prompts
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from tweakcv.clients import get_langfuse

HARNESS_PATH = Path(__file__).parent / "harness.json"


def pull() -> None:
    client = get_langfuse()
    harnesses: list[dict[str, Any]] = json.loads(HARNESS_PATH.read_text())

    updated = 0
    for harness in harnesses:
        prompt_id = harness["id"]
        try:
            prompt_obj = client.get_prompt(prompt_id, label="production", cache_ttl_seconds=0)
            fetched_text: str = prompt_obj.compile()
            if fetched_text != harness["system_prompt"]:
                harness["system_prompt"] = fetched_text
                updated += 1
                logger.info(f"prompt_updated id={prompt_id}")
            else:
                logger.info(f"prompt_in_sync id={prompt_id}")
        except Exception as exc:
            logger.warning(f"prompt_fetch_failed id={prompt_id} error={exc}")

    HARNESS_PATH.write_text(json.dumps(harnesses, indent=2) + "\n")
    logger.info(f"pull_prompts_done updated={updated} total={len(harnesses)}")


if __name__ == "__main__":
    pull()
