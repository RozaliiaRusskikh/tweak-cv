import re

from pydantic import BaseModel, Field, field_validator


class JDAnalysisOutput(BaseModel):
    company: str
    role: str
    required_skills: list[str]
    preferred_skills: list[str]
    keywords: list[str]


class ExperienceEntry(BaseModel):
    company: str
    role: str
    dates: str
    bullets: list[str]

    @field_validator("dates")
    @classmethod
    def _collapse_whitespace(cls, v: str) -> str:
        """Collapse embedded newlines/extra spaces — the LLM sometimes wraps date
        ranges onto two lines (e.g. "Mar 2022 \\n– Present"), which breaks the
        single-line date layout in the rendered resume."""
        return re.sub(r"\s+", " ", v).strip()


class EducationEntry(BaseModel):
    institution: str
    degree: str
    year: str


class TailoredResumeOutput(BaseModel):
    summary: str
    experience: list[ExperienceEntry]
    skills: list[str]
    education: list[EducationEntry]


class ScoreResult(BaseModel):
    keyword_coverage: float = Field(ge=0.0, le=1.0)
    no_hallucination: bool
    edit_fidelity: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_retry: bool
