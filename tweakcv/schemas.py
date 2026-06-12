from pydantic import BaseModel, Field


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
