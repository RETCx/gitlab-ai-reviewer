from unittest.mock import Mock

import pytest

import review_job as job
from schemas import Review


@pytest.fixture
def dependencies(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    monkeypatch.setattr(job, "completed_reviews", set())

    mr = Mock(return_value={"state": "opened", "sha": "abc123"})
    diff = Mock(return_value="File: example.py\n+print('hello')")
    llm = Mock(return_value=Review(
        summary="No concrete defects found.",
        findings=[],
        suggested_tests=[],
    ))
    post = Mock(return_value=123)

    monkeypatch.setattr(job, "fetch_mr", mr)
    monkeypatch.setattr(job, "fetch_mr_diff", diff)
    monkeypatch.setattr(job, "review_diff", llm)
    monkeypatch.setattr(job, "post_review", post)

    return mr, llm, post


def test_same_commit_is_posted_only_once(dependencies):
    _, llm, post = dependencies

    job.run_review("RETCx/gitlab-ai-reviewer", 1)
    job.run_review("RETCx/gitlab-ai-reviewer", 1)

    llm.assert_called_once()
    post.assert_called_once_with(
        "RETCx/gitlab-ai-reviewer", 1, llm.return_value
    )


def test_changed_commit_prevents_posting(dependencies):
    mr, llm, post = dependencies
    mr.side_effect = [
        {"state": "opened", "sha": "abc123"},
        {"state": "opened", "sha": "new456"},
    ]

    job.run_review("RETCx/gitlab-ai-reviewer", 1)

    llm.assert_called_once()
    post.assert_not_called()
    assert not job.completed_reviews


def test_llm_failure_prevents_posting(dependencies):
    _, llm, post = dependencies
    llm.side_effect = ValueError("Invalid review output")

    job.run_review("RETCx/gitlab-ai-reviewer", 1)

    llm.assert_called_once()
    post.assert_not_called()
    assert not job.completed_reviews


def test_closed_mr_is_not_reviewed(dependencies):
    mr, llm, post = dependencies
    mr.return_value = {"state": "closed", "sha": "abc123"}

    job.run_review("RETCx/gitlab-ai-reviewer", 1)

    llm.assert_not_called()
    post.assert_not_called()