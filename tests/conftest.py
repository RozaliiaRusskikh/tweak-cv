"""Shared pytest fixtures."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tweakcv.db import Base


@pytest.fixture()
def db_session() -> Generator[Session]:
    """In-memory SQLite session for all DB tests. Tables created fresh per test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


FIXTURE_BASE_RESUME = {
    "name": "Jane Doe",
    "summary": "Senior engineer.",
    "experience": [
        {
            "company": "Acme Corp",
            "role": "Senior Engineer",
            "dates": "2022–Present",
            "bullets": ["Led platform migration", "Reduced latency by 30%"],
        }
    ],
    "skills": ["Python", "Docker", "Kubernetes"],
    "education": [{"institution": "State University", "degree": "B.S. CS", "year": "2018"}],
}

FIXTURE_JD_ANALYSIS = {
    "company": "Beta Inc",
    "role": "Platform Engineer",
    "required_skills": ["Python", "Kubernetes"],
    "preferred_skills": ["Terraform"],
    "keywords": ["Python", "Kubernetes", "Docker", "platform", "latency"],
}
