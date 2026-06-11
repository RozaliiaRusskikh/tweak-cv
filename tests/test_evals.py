"""Integration eval tests — require real Gemini credentials.

Skipped in normal test runs. Run explicitly with:

    uv run pytest tests/test_evals.py -m evals -v

Pass criteria per example (from dataset.json expected_scores):
  - keyword_coverage >= expected_scores.keyword_coverage_min  (default 0.8)
  - keyword_coverage <= expected_scores.keyword_coverage_max  (default 1.0)
  - no_hallucination == expected_scores.no_hallucination       (default True)

Overall suite: >= 80% of examples must pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DATASET_PATH = Path(__file__).parent.parent / "evals" / "dataset.json"
HARNESS_PATH = Path(__file__).parent.parent / "tweakcv" / "harness.json"
MIN_SUITE_PASS_RATE = 0.8

_examples: list[dict] = json.loads(DATASET_PATH.read_text())  # type: ignore[type-arg]


def _setup() -> None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tweakcv.harness_loader import load_harnesses

    load_harnesses(str(HARNESS_PATH))


def _run_example(ex: dict) -> tuple[float, bool, list[str]]:  # type: ignore[type-arg]
    from langchain_core.messages import HumanMessage, SystemMessage

    from tweakcv.harness_loader import get_llm, get_prompt
    from tweakcv.nodes.score import _detect_new_entities, compute_keyword_coverage
    from tweakcv.schemas import JDAnalysisOutput, TailoredResumeOutput

    analyze_llm = get_llm("analyze-jd").with_structured_output(JDAnalysisOutput)
    jd_analysis: JDAnalysisOutput = analyze_llm.invoke(  # type: ignore[assignment]
        [SystemMessage(content=get_prompt("analyze-jd")), HumanMessage(content=ex["jd_text"])]
    )

    tailor_llm = get_llm("tailor-resume").with_structured_output(TailoredResumeOutput)
    tailored: TailoredResumeOutput = tailor_llm.invoke(  # type: ignore[assignment]
        [
            SystemMessage(content=get_prompt("tailor-resume")),
            HumanMessage(
                content=json.dumps(
                    {
                        "base_resume": ex["base_resume"],
                        "jd_analysis": jd_analysis.model_dump(),
                        "jd_text": ex["jd_text"],
                    }
                )
            ),
        ]
    )

    tailored_dict = tailored.model_dump()
    kw = compute_keyword_coverage(ex["expected_keywords"], tailored_dict)
    new_entities = _detect_new_entities(ex["base_resume"], tailored_dict)
    return kw, len(new_entities) == 0, new_entities


@pytest.mark.evals
@pytest.mark.parametrize("example", _examples, ids=[e["id"] for e in _examples])
def test_eval_example(example: dict) -> None:  # type: ignore[type-arg]
    """Each example must meet its own expected_scores thresholds."""
    _setup()

    scores = example.get("expected_scores", {})
    kw_min: float = float(scores.get("keyword_coverage_min", 0.8))
    kw_max: float = float(scores.get("keyword_coverage_max", 1.0))
    expect_no_halluc: bool = bool(scores.get("no_hallucination", True))

    kw, no_halluc, new_entities = _run_example(example)

    assert no_halluc == expect_no_halluc, (
        f"Hallucination check failed for {example['id']}: {new_entities}"
    )
    assert kw >= kw_min, f"keyword_coverage {kw:.0%} < {kw_min:.0%} for {example['id']}"
    assert kw <= kw_max, (
        f"keyword_coverage {kw:.0%} > {kw_max:.0%} for {example['id']} "
        f"(model may be hallucinating keywords)"
    )


@pytest.mark.evals
def test_eval_suite_pass_rate() -> None:
    """At least 80% of examples must pass their individual thresholds."""
    _setup()

    failures: list[str] = []

    for ex in _examples:
        scores = ex.get("expected_scores", {})
        kw_min: float = float(scores.get("keyword_coverage_min", 0.8))
        kw_max: float = float(scores.get("keyword_coverage_max", 1.0))
        expect_no_halluc: bool = bool(scores.get("no_hallucination", True))

        try:
            kw, no_halluc, new_entities = _run_example(ex)
            if kw < kw_min or kw > kw_max or no_halluc != expect_no_halluc:
                failures.append(
                    f"{ex['id']}: kw={kw:.0%} (expected {kw_min:.0%}–{kw_max:.0%})"
                    + (f" hallucination:{new_entities}" if new_entities else "")
                )
        except Exception as exc:
            failures.append(f"{ex['id']}: crashed — {exc}")

    pass_rate = (len(_examples) - len(failures)) / len(_examples)
    assert pass_rate >= MIN_SUITE_PASS_RATE, (
        f"Suite pass rate {pass_rate:.0%} below {MIN_SUITE_PASS_RATE:.0%}.\n"
        "Failed:\n" + "\n".join(f"  - {f}" for f in failures)
    )
