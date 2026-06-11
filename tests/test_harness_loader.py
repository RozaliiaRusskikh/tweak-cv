import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import tweakcv.clients as cl
import tweakcv.harness_loader as hl


@pytest.fixture(autouse=True)
def reset_state() -> Generator[None]:
    """Reset module-level harness dict and Langfuse client between tests."""
    original_harnesses = dict(hl._harnesses)
    original_client = cl._langfuse_client
    yield
    hl._harnesses = original_harnesses
    cl._langfuse_client = original_client


def _write_harness_json(path: Path) -> None:
    stub = {"model_name": "gemini-stub", "system_prompt": "stub prompt"}
    data = [
        {
            "id": "analyze-jd",
            "system_prompt": "You are an analyzer.",
            "model_name": "gemini-2.0-flash",
        },
        {"id": "tailor-resume", **stub},
        {"id": "edit-resume", **stub},
        {"id": "quality-judge", **stub},
    ]
    path.write_text(json.dumps(data))


def test_load_harnesses_parses_json() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "harness.json"
        _write_harness_json(p)
        hl.load_harnesses(str(p))
        assert "analyze-jd" in hl._harnesses
        assert hl._harnesses["analyze-jd"]["model_name"] == "gemini-2.0-flash"


def test_load_harnesses_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        hl.load_harnesses("/tmp/nonexistent_harness_12345.json")


def test_get_prompt_returns_langfuse_value_when_available() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "harness.json"
        _write_harness_json(p)
        hl.load_harnesses(str(p))

    mock_client = MagicMock()
    mock_prompt = MagicMock()
    mock_prompt.compile.return_value = "langfuse_prompt_text"
    mock_client.get_prompt.return_value = mock_prompt

    with patch("tweakcv.harness_loader.get_langfuse", return_value=mock_client):
        result = hl.get_prompt("analyze-jd")

    assert result == "langfuse_prompt_text"


def test_get_prompt_falls_back_to_harness_when_langfuse_raises() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "harness.json"
        _write_harness_json(p)
        hl.load_harnesses(str(p))

    mock_client = MagicMock()
    mock_client.get_prompt.side_effect = RuntimeError("network error")

    with patch("tweakcv.harness_loader.get_langfuse", return_value=mock_client):
        result = hl.get_prompt("analyze-jd")

    assert result == "You are an analyzer."
