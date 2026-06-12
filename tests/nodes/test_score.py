from unittest.mock import patch

import pytest

from tweakcv.nodes.score import (
    _attach_trace_output,
    _detect_new_entities,
    _detect_new_skills,
    compute_edit_fidelity,
    compute_keyword_coverage,
    score,
)

BASE_RESUME = {
    "name": "Jane Doe",
    "summary": "Senior engineer.",
    "experience": [
        {"company": "Acme Corp", "role": "Senior Engineer", "dates": "2022–Present", "bullets": []}
    ],
    "skills": ["Python", "Docker"],
    "education": [{"institution": "State University", "degree": "B.S. CS", "year": "2018"}],
}

TAILORED_WITH_PYTHON = {
    "summary": "Python engineer with Kubernetes experience.",
    "experience": [
        {
            "company": "Acme Corp",
            "role": "Senior Engineer",
            "dates": "2022–Present",
            "bullets": ["Used Python"],
        }
    ],
    "skills": ["Python", "Docker", "Kubernetes"],
    "education": [],
}


# ── keyword_coverage ──────────────────────────────────────────────────────────


def test_kw_coverage_all_covered() -> None:
    keywords = ["Python", "Docker"]
    result = compute_keyword_coverage(keywords, TAILORED_WITH_PYTHON)
    assert result == pytest.approx(1.0)


def test_kw_coverage_none_covered() -> None:
    keywords = ["Terraform", "Rust"]
    result = compute_keyword_coverage(keywords, TAILORED_WITH_PYTHON)
    assert result == pytest.approx(0.0)


def test_kw_coverage_partial() -> None:
    keywords = ["Python", "Terraform"]
    result = compute_keyword_coverage(keywords, TAILORED_WITH_PYTHON)
    assert result == pytest.approx(0.5)


def test_kw_coverage_empty_keywords_returns_one() -> None:
    assert compute_keyword_coverage([], TAILORED_WITH_PYTHON) == pytest.approx(1.0)


# ── hallucination detection ───────────────────────────────────────────────────


def test_detect_new_entities_no_hallucination() -> None:
    # Same company as base
    new = _detect_new_entities(BASE_RESUME, TAILORED_WITH_PYTHON)
    assert all("company:" not in e and "institution:" not in e for e in new)
    # "Kubernetes" has no basis in BASE_RESUME's skills or bullets — flagged
    assert "skill:Kubernetes" in new


def test_detect_new_entities_new_company() -> None:
    tailored_with_fake = dict(TAILORED_WITH_PYTHON)
    tailored_with_fake["experience"] = [
        {"company": "Fake Corp", "role": "Eng", "dates": "2020", "bullets": []}
    ]
    new = _detect_new_entities(BASE_RESUME, tailored_with_fake)
    assert any("company:Fake Corp" in e for e in new)


def test_detect_new_entities_new_institution() -> None:
    tailored_with_fake_edu = dict(TAILORED_WITH_PYTHON)
    tailored_with_fake_edu["education"] = [{"institution": "MIT", "degree": "PhD", "year": "2020"}]
    new = _detect_new_entities(BASE_RESUME, tailored_with_fake_edu)
    assert any("institution:MIT" in e for e in new)


def test_detect_new_skills_renames_not_flagged() -> None:
    base = {**BASE_RESUME, "skills": ["Python", "PostgreSQL", "GPT-4"]}
    tailored = {**TAILORED_WITH_PYTHON, "skills": ["Python", "Postgres", "GPT-4o"]}
    # "Postgres"/"PostgreSQL" and "GPT-4"/"GPT-4o" are renames, not hallucinations
    assert _detect_new_skills(base, tailored) == []


def test_detect_new_skills_grounded_in_bullet_not_flagged() -> None:
    base = {
        **BASE_RESUME,
        "experience": [
            {
                "company": "Acme Corp",
                "role": "Senior Engineer",
                "dates": "2022–Present",
                "bullets": ["Wrote complex SQL queries against PostgreSQL"],
            }
        ],
    }
    tailored = {**TAILORED_WITH_PYTHON, "skills": ["Python", "Docker", "SQL"]}
    # "SQL" isn't in base skills but appears verbatim in an experience bullet
    assert _detect_new_skills(base, tailored) == []


def test_detect_new_skills_unrelated_skill_flagged() -> None:
    tailored = {**TAILORED_WITH_PYTHON, "skills": ["Python", "Docker", "C#", ".NET Core"]}
    new = _detect_new_skills(BASE_RESUME, tailored)
    assert "skill:C#" in new
    assert "skill:.NET Core" in new


# ── needs_retry ───────────────────────────────────────────────────────────────


def test_score_needs_retry_when_coverage_below_threshold() -> None:
    with (
        patch("tweakcv.nodes.score._attach_langfuse_scores"),
        patch("tweakcv.nodes.score._attach_trace_output"),
    ):
        result = score(
            tailored={
                "summary": "nothing relevant",
                "experience": [],
                "skills": [],
                "education": [],
            },
            base_resume=BASE_RESUME,
            keywords=["Python", "Docker", "Kubernetes", "Terraform"],
            langfuse_trace_id="trace1",
        )
    assert result.needs_retry is True


def test_score_no_retry_when_coverage_sufficient() -> None:
    with (
        patch("tweakcv.nodes.score._attach_langfuse_scores"),
        patch("tweakcv.nodes.score._attach_trace_output"),
    ):
        result = score(
            tailored=TAILORED_WITH_PYTHON,
            base_resume=BASE_RESUME,
            keywords=["Python", "Docker"],
            langfuse_trace_id="trace1",
        )
    assert result.needs_retry is False


# ── edit_fidelity ─────────────────────────────────────────────────────────────


def test_edit_fidelity_returns_value_when_previous_provided() -> None:
    before = {"summary": "Old summary", "experience": [], "skills": ["Python"], "education": []}
    after = {
        "summary": "New summary about Python",
        "experience": [],
        "skills": ["Python"],
        "education": [],
    }
    fidelity = compute_edit_fidelity(before, after)
    assert 0.0 <= fidelity <= 1.0


def test_edit_fidelity_identical_resumes_returns_one() -> None:
    resume = {"summary": "Same", "experience": [], "skills": ["Python"], "education": []}
    assert compute_edit_fidelity(resume, resume) == pytest.approx(1.0)


# ── trace output ──────────────────────────────────────────────────────────────


def test_attach_trace_output_sets_observation_input_and_output() -> None:
    with patch("tweakcv.nodes.score.get_langfuse") as mock_get_langfuse:
        mock_span = mock_get_langfuse.return_value.start_observation.return_value
        _attach_trace_output("trace1", BASE_RESUME, ["Python", "Docker"], TAILORED_WITH_PYTHON)

    mock_get_langfuse.return_value.start_observation.assert_called_once_with(
        trace_context={"trace_id": "trace1"},
        name="tailored-resume",
        input={"base_resume": BASE_RESUME, "keywords": ["Python", "Docker"]},
        output=TAILORED_WITH_PYTHON,
    )
    mock_span.end.assert_called_once()


def test_attach_trace_output_swallows_errors() -> None:
    with patch("tweakcv.nodes.score.get_langfuse", side_effect=RuntimeError("boom")):
        _attach_trace_output(
            "trace1", BASE_RESUME, ["Python"], TAILORED_WITH_PYTHON
        )  # must not raise
