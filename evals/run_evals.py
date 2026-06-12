"""Offline eval runner — no graph, no Slack, no DB.

Usage:
    uv run python evals/run_evals.py              # heuristic checks only (uses cache)
    uv run python evals/run_evals.py --regen      # call LLM, update cache, then check
    uv run python evals/run_evals.py --threshold 0.9

Default mode (no --regen):
  Loads cached LLM outputs from evals/cache/ and runs all heuristic checks locally.
  Zero API calls — safe to run as many times as you like.

--regen mode:
  Calls the real LLM (analyze + tailor) for each example, saves outputs
  to cache, then checks. Uses GEMINI_API_KEY_EVAL if set in .env, otherwise falls back
  to GEMINI_API_KEY. Run this only when you change a prompt and want fresh outputs.

Pass criteria per example (from dataset.json expected_scores):
  - keyword_coverage >= expected_scores.keyword_coverage_min  (default: 0.8)
  - no_hallucination == expected_scores.no_hallucination       (default True)
  - keyword_coverage <= expected_scores.keyword_coverage_max   (if specified)
  - no_markdown: true — no **bold** or _italic_ in any text field
  - first_person_summary: true — summary uses "I", not candidate's name
  - date_preservation: true — all dates from base resume appear unchanged
  - skills_are_tools: true — no generic activity phrases in skills list

Overall suite passes when >= --threshold of examples pass.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langfuse import Langfuse
from loguru import logger

from tweakcv.harness_loader import LLM_TEMPERATURE, get_prompt, load_harnesses
from tweakcv.nodes.score import _detect_new_entities, compute_keyword_coverage
from tweakcv.schemas import JDAnalysisOutput, TailoredResumeOutput
from tweakcv.settings import settings

DATASET_PATH = Path(__file__).parent / "dataset.json"
HARNESS_PATH = Path(__file__).parent.parent / "tweakcv" / "harness.json"
CACHE_DIR = Path(__file__).parent / "cache"
MIN_SUITE_PASS_RATE = 0.8
_MAX_RETRIES = 3

_GENERIC_SKILL_PHRASES = {
    "frontend development",
    "backend development",
    "web development",
    "mobile development",
    "api integrations",
    "api integration",
    "state management",
    "frontend architecture",
    "backend services",
    "reusable components",
    "real-time data streams",
    "cross-platform",
    "software development",
    "system design",
    "problem solving",
    "algorithm design",
    "communication",
    "team player",
}


def _get_eval_api_key() -> str:
    """Use GEMINI_API_KEY_EVAL if set in .env, otherwise fall back to the main key."""
    if settings.gemini_api_key_eval is not None:
        logger.debug("eval_using_separate_api_key")
        return settings.gemini_api_key_eval.get_secret_value()
    return settings.gemini_api_key.get_secret_value()


def _get_llm(harness_id: str) -> ChatGoogleGenerativeAI:
    harness_data = json.loads(HARNESS_PATH.read_text())
    model_name = next(h["model_name"] for h in harness_data if h["id"] == harness_id)
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=_get_eval_api_key(),
        temperature=LLM_TEMPERATURE,
    )


def _expected(ex: dict, key: str, default: float | bool) -> float | bool:  # type: ignore[type-arg]
    return ex.get("expected_scores", {}).get(key, default)  # type: ignore[no-any-return]


def _invoke_with_retry(llm: object, messages: list) -> object:  # type: ignore[type-arg]
    for attempt in range(_MAX_RETRIES):
        try:
            return llm.invoke(messages)  # type: ignore[attr-defined]
        except Exception as exc:
            msg = str(exc)
            is_retryable = (
                "429" in msg or "503" in msg or "RESOURCE_EXHAUSTED" in msg or "UNAVAILABLE" in msg
            )
            if is_retryable and attempt < _MAX_RETRIES - 1:
                wait = 2**attempt * 15
                logger.warning(
                    f"LLM rate limited — retrying in {wait}s (attempt {attempt + 1}/{_MAX_RETRIES})"
                )
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("unreachable")


# ── heuristic checks (no LLM, no API calls) ──────────────────────────────────


def _check_no_markdown(tailored: dict) -> bool:  # type: ignore[type-arg]
    parts = [tailored.get("summary", "")]
    for job in tailored.get("experience", []):
        parts.extend(job.get("bullets", []))
    combined = " ".join(parts)
    return "**" not in combined and not bool(re.search(r"(?<!\w)_\w", combined))


def _check_first_person(tailored: dict) -> bool:  # type: ignore[type-arg]
    return bool(re.search(r"\bI\b", tailored.get("summary", "")))


def _check_date_preservation(base_resume: dict, tailored: dict) -> bool:  # type: ignore[type-arg]
    base_dates = {job.get("dates", "") for job in base_resume.get("experience", [])}
    tailored_dates = {job.get("dates", "") for job in tailored.get("experience", [])}
    missing = base_dates - tailored_dates
    if missing:
        logger.warning(f"date_preservation_failed missing={missing}")
    return len(missing) == 0


def _check_skills_are_tools(tailored: dict) -> bool:  # type: ignore[type-arg]
    skills = [s.lower() for s in tailored.get("skills", [])]
    violations = [s for s in skills if s in _GENERIC_SKILL_PHRASES]
    if violations:
        logger.warning(f"skills_generic_phrases={violations}")
    return len(violations) == 0


# ── LLM generation (only called with --regen) ────────────────────────────────


def _generate(ex: dict) -> dict:  # type: ignore[type-arg]
    """Call LLM to produce tailored resume + quality judge score. Returns cache payload."""
    jd_text: str = ex["jd_text"]

    # 1. Analyze JD
    llm_analyze = _get_llm("analyze-jd").with_structured_output(JDAnalysisOutput)
    jd_analysis: JDAnalysisOutput = _invoke_with_retry(  # type: ignore[assignment]
        llm_analyze,
        [SystemMessage(content=get_prompt("analyze-jd")), HumanMessage(content=jd_text)],
    )

    # 2. Tailor resume
    llm_tailor = _get_llm("tailor-resume").with_structured_output(TailoredResumeOutput)
    human_content = json.dumps(
        {
            "base_resume": ex["base_resume"],
            "personal": ex.get("personal", {}),
            "jd_analysis": jd_analysis.model_dump(),
            "jd_text": jd_text,
        }
    )
    tailored: TailoredResumeOutput = _invoke_with_retry(  # type: ignore[assignment]
        llm_tailor,
        [SystemMessage(content=get_prompt("tailor-resume")), HumanMessage(content=human_content)],
    )
    tailored_dict = tailored.model_dump()

    return {"tailored": tailored_dict}


def _cache_path(eid: str) -> Path:
    return CACHE_DIR / f"{eid}.json"


def _load_cache(eid: str) -> dict | None:  # type: ignore[type-arg]
    path = _cache_path(eid)
    if path.exists():
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    return None


def _save_cache(eid: str, payload: dict) -> None:  # type: ignore[type-arg]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(eid).write_text(json.dumps(payload, indent=2))


# ── main evaluation logic ─────────────────────────────────────────────────────


def evaluate_example(ex: dict, regen: bool) -> tuple[bool, dict]:  # type: ignore[type-arg]
    eid: str = ex["id"]
    cached = _load_cache(eid)

    if regen or cached is None:
        if cached is None and not regen:
            logger.warning(f"no_cache_found id={eid} — running LLM (use --regen to update cache)")
        logger.info(f"generating id={eid}")
        payload = _generate(ex)
        _save_cache(eid, payload)
    else:
        logger.debug(f"cache_hit id={eid}")
        payload = cached

    tailored_dict: dict = payload["tailored"]  # type: ignore[type-arg]

    kw_coverage = compute_keyword_coverage(ex["expected_keywords"], tailored_dict)
    new_entities = _detect_new_entities(ex["base_resume"], tailored_dict)
    no_hallucination = len(new_entities) == 0
    no_markdown = _check_no_markdown(tailored_dict)
    first_person = _check_first_person(tailored_dict)
    date_ok = _check_date_preservation(ex["base_resume"], tailored_dict)
    skills_ok = _check_skills_are_tools(tailored_dict)

    scores = {
        "keyword_coverage": kw_coverage,
        "no_hallucination": 1.0 if no_hallucination else 0.0,
        "hallucinated_entities": new_entities,
        "no_markdown": 1.0 if no_markdown else 0.0,
        "first_person_summary": 1.0 if first_person else 0.0,
        "date_preservation": 1.0 if date_ok else 0.0,
        "skills_are_tools": 1.0 if skills_ok else 0.0,
    }

    kw_min = float(_expected(ex, "keyword_coverage_min", 0.8))
    kw_max = float(_expected(ex, "keyword_coverage_max", 1.0))
    expect_no_halluc = bool(_expected(ex, "no_hallucination", True))

    checks: list[bool] = [
        kw_coverage >= kw_min,
        kw_coverage <= kw_max,
        no_hallucination == expect_no_halluc,
    ]
    if _expected(ex, "no_markdown", False):
        checks.append(no_markdown)
    if _expected(ex, "first_person_summary", False):
        checks.append(first_person)
    if _expected(ex, "date_preservation", False):
        checks.append(date_ok)
    if _expected(ex, "skills_are_tools", False):
        checks.append(skills_ok)

    return all(checks), scores


def _upload_to_langfuse(langfuse: Langfuse, eid: str, ex: dict, scores: dict) -> None:  # type: ignore[type-arg]
    with contextlib.suppress(Exception):
        langfuse.create_dataset(name="tweakcv-evals")
    langfuse.create_dataset_item(
        dataset_name="tweakcv-evals",
        id=eid,
        input={
            "jd_text": ex["jd_text"],
            "base_resume": ex["base_resume"],
            "expected_keywords": ex["expected_keywords"],
        },
        expected_output=ex.get("expected_scores", {}),
        metadata={
            "id": eid,
            "description": ex.get("description", ""),
        },
    )
    trace_id = langfuse.create_trace_id()
    for name in (
        "keyword_coverage",
        "no_hallucination",
        "no_markdown",
        "first_person_summary",
        "date_preservation",
        "skills_are_tools",
    ):
        value = scores.get(name)
        if value is not None and not isinstance(value, list):
            langfuse.create_score(trace_id=trace_id, name=name, value=float(value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline evals.")
    parser.add_argument("--threshold", type=float, default=MIN_SUITE_PASS_RATE, metavar="0.0-1.0")
    parser.add_argument(
        "--regen",
        action="store_true",
        help="Re-call LLM and update cache (uses GEMINI_API_KEY_EVAL if set)",
    )
    args = parser.parse_args()

    load_harnesses(str(HARNESS_PATH))

    langfuse = Langfuse(
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )

    if args.regen:
        logger.info("regen_mode — LLM will be called for all examples")
    else:
        logger.info("cache_mode — heuristic checks only, no API calls")

    examples: list[dict] = json.loads(DATASET_PATH.read_text())  # type: ignore[type-arg]
    passed_count = 0
    failed_count = 0

    for ex in examples:
        eid = ex["id"]
        logger.info("eval_start id={} — {}", eid, ex.get("description", ""))
        try:
            passed, scores = evaluate_example(ex, regen=args.regen)

            status = "PASS" if passed else "FAIL"
            if passed:
                passed_count += 1
            else:
                failed_count += 1

            logger.info(
                "{} {} | kw={:.0%} halluc={} markdown={} first_person={} dates={} skills={}",
                eid,
                status,
                scores["keyword_coverage"],
                "none"
                if not scores["hallucinated_entities"]
                else f"DETECTED:{scores['hallucinated_entities']}",
                "ok" if scores["no_markdown"] else "FAIL",
                "ok" if scores["first_person_summary"] else "FAIL",
                "ok" if scores["date_preservation"] else "FAIL",
                "ok" if scores["skills_are_tools"] else "FAIL",
            )

            with contextlib.suppress(Exception):
                _upload_to_langfuse(langfuse, eid, ex, scores)

        except Exception as exc:
            logger.error("eval_crashed id={} error={}", eid, exc)
            failed_count += 1

    total = passed_count + failed_count
    pass_rate = passed_count / total if total else 0.0
    logger.info(
        "evals_complete {}/{} passed ({:.0%}) — threshold {:.0%}",
        passed_count,
        total,
        pass_rate,
        args.threshold,
    )

    if pass_rate < args.threshold:
        logger.error("suite_failed — pass rate below {:.0%}", args.threshold)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
