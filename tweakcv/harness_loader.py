import json
from pathlib import Path
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from tweakcv.clients import get_langfuse
from tweakcv.errors import HarnessNotLoadedError
from tweakcv.settings import settings

_harnesses: dict[str, dict[str, Any]] = {}

_REQUIRED_HARNESSES = {"analyze-jd", "tailor-resume", "edit-resume"}

LLM_TEMPERATURE = 0.3


def load_harnesses(path: str | Path = "tweakcv/harness.json") -> None:
    global _harnesses
    harness_path = Path(path)
    raw: list[dict[str, Any]] = json.loads(harness_path.read_text())
    _harnesses = {entry["id"]: entry for entry in raw}
    missing = _REQUIRED_HARNESSES - set(_harnesses)
    if missing:
        raise HarnessNotLoadedError(f"Missing required harnesses: {missing}")
    logger.info(f"harnesses_loaded count={len(_harnesses)} path={path}")


def get_prompt(harness_id: str) -> str:
    if harness_id not in _harnesses:
        raise HarnessNotLoadedError(
            f"Harness {harness_id!r} not loaded — call load_harnesses() first"
        )
    harness = _harnesses[harness_id]
    try:
        prompt_obj = get_langfuse().get_prompt(harness_id)
        text: str = prompt_obj.compile()
        logger.debug(f"prompt_loaded_langfuse id={harness_id}")
        return text
    except Exception as exc:
        logger.warning(f"prompt_langfuse_fallback id={harness_id} error={exc}")
        return str(harness["system_prompt"])


def get_llm(harness_id: str) -> ChatGoogleGenerativeAI:
    if harness_id not in _harnesses:
        raise HarnessNotLoadedError(
            f"Harness {harness_id!r} not loaded — call load_harnesses() first"
        )
    harness = _harnesses[harness_id]
    return ChatGoogleGenerativeAI(
        model=harness["model_name"],
        google_api_key=settings.gemini_api_key.get_secret_value(),
        temperature=LLM_TEMPERATURE,
    )
