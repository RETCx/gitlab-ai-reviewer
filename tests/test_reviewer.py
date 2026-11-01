import sys

import httpx
import pytest
from pydantic import ValidationError

import post_review
import review_diff


def test_invalid_llm_output_is_rejected(monkeypatch):
    def fake_post(*args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
            ),
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"summary": "Missing required fields"}'
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr(review_diff.httpx, "post", fake_post)

    with pytest.raises(ValidationError):
        review_diff.review_diff("sample diff", "fake-key", "fake-model")


def test_llm_timeout_is_reported(monkeypatch):
    def fake_post(*args, **kwargs):
        raise httpx.ReadTimeout("Simulated timeout")

    monkeypatch.setattr(review_diff.httpx, "post", fake_post)

    with pytest.raises(httpx.ReadTimeout):
        review_diff.review_diff("sample diff", "fake-key", "fake-model")


def test_preview_does_not_post(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "review.json").write_text(
        '{"summary": "No defects found", '
        '"findings": [], "suggested_tests": []}',
        encoding="utf-8",
    )

    def forbidden_post(*args, **kwargs):
        pytest.fail("Preview must not send an HTTP request")

    monkeypatch.setattr(post_review.httpx, "post", forbidden_post)
    monkeypatch.setattr(sys, "argv", ["post_review.py"])

    post_review.main()

    assert "No defects found" in capsys.readouterr().out