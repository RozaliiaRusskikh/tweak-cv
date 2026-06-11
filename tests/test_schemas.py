import pytest
from pydantic import ValidationError

from tweakcv.schemas import (
    JDAnalysisOutput,
    ScoreResult,
    TailoredResumeOutput,
)


def test_jd_analysis_output_valid() -> None:
    obj = JDAnalysisOutput(
        company="Acme",
        role="Engineer",
        required_skills=["Python"],
        preferred_skills=[],
        keywords=["Python", "FastAPI"],
    )
    assert obj.company == "Acme"
    assert len(obj.keywords) == 2


def test_jd_analysis_output_missing_field() -> None:
    with pytest.raises(ValidationError):
        JDAnalysisOutput(role="Engineer", required_skills=[], preferred_skills=[], keywords=[])  # type: ignore[call-arg]


def test_tailored_resume_round_trips_json() -> None:
    data = {
        "summary": "Great engineer",
        "experience": [
            {"company": "Acme", "role": "Eng", "dates": "2020–2022", "bullets": ["Did things"]}
        ],
        "skills": ["Python"],
        "education": [{"institution": "MIT", "degree": "B.S.", "year": "2018"}],
    }
    obj = TailoredResumeOutput.model_validate(data)
    dumped = obj.model_dump()
    assert dumped["summary"] == "Great engineer"
    assert dumped["experience"][0]["company"] == "Acme"


def test_score_result_needs_retry_true_below_threshold() -> None:
    sr = ScoreResult(
        keyword_coverage=0.4,
        no_hallucination=True,
        edit_fidelity=None,
        needs_retry=True,
    )
    assert sr.needs_retry is True
    assert sr.keyword_coverage == pytest.approx(0.4)


def test_score_result_needs_retry_false_above_threshold() -> None:
    sr = ScoreResult(
        keyword_coverage=0.6,
        no_hallucination=True,
        edit_fidelity=None,
        needs_retry=False,
    )
    assert sr.needs_retry is False


def test_score_result_rejects_out_of_range_coverage() -> None:
    with pytest.raises(ValidationError):
        ScoreResult(
            keyword_coverage=1.5,  # > 1.0
            no_hallucination=True,
            edit_fidelity=None,
            needs_retry=False,
        )
