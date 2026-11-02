# GitLab AI Reviewer

A Python proof of concept that reviews GitLab merge requests using an LLM
and posts structured feedback as a merge request comment.

## Workflow

1. GitLab sends a merge request webhook.
2. FastAPI verifies the webhook signature and timestamp.
3. A background task checks that the merge request is open.
4. The service fetches the diff and requests a review from OpenRouter.
5. Pydantic validates the structured review.
6. The service checks that the source commit is unchanged before posting.
7. The review is posted as a GitLab merge request comment.

## Features

- GitLab REST API integration.
- Signed webhook verification using Standard Webhooks.
- GPT-5 Mini through OpenRouter.
- JSON schema output with Pydantic validation.
- Background review processing.
- Duplicate review prevention within a running process.
- Source commit and merge request state checks before posting.
- Logging of review outcomes and total processing duration.
- Automated tests and GitLab CI.

## Setup

The CI environment uses Python 3.12.

From Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

## Run tests

```bat
python -m pytest -q
```

The current suite contains 10 tests covering:

- Invalid LLM output and request timeout.
- CLI preview without publishing.
- Valid, modified, and unsigned webhook requests.
- Duplicate reviews.
- Source commit changes during a review.
- LLM failures and closed merge requests.

Tests mock external API calls and do not require real credentials.

## Run the webhook service

```bat
python run_server.py
```

The launcher prompts for missing credentials:

| Variable | Purpose |
| --- | --- |
| GITLAB_WEBHOOK_SIGNING_SECRET | Signing token from the GitLab webhook |
| GITLAB_TOKEN | GitLab personal access token with the api scope |
| OPENROUTER_API_KEY | OpenRouter API key |

The default model is `openai/gpt-5-mini`.
Set `OPENROUTER_MODEL` to override it.

The launcher enables automatic reviews with `AUTO_REVIEW_ENABLED=1`.

## Connect GitLab

In another terminal:

```bat
cloudflared tunnel --url http://127.0.0.1:8000
```

In GitLab, open Settings > Webhooks and configure:

- URL: the generated HTTPS URL followed by `/webhooks/gitlab`
- Trigger: Merge request events only
- Authentication: generate a signing token and use the same token in the service
- SSL verification: enabled

The application currently allows the project `RETCx/gitlab-ai-reviewer`.
Change the project check in `app.py` when using another project.

Keep the service and tunnel running. Update the GitLab webhook URL whenever
the temporary tunnel hostname changes.

## Demo

The demo merge request adds an `average(values)` function whose docstring
requires `ValueError` for empty input, while the implementation raises
`ZeroDivisionError`.

An end-to-end run detected this mismatch and posted a review in approximately
11.64 seconds. This is one observed run, not a performance benchmark.

Updating the description again with the same source commit produced
`Skipped MR !1: already reviewed`.

## Limitations

- Background tasks and duplicate tracking are not persisted.
- Restarting the service clears duplicate tracking.
- Duplicate tracking is scoped to one process and keyed by project, MR, and
  source commit SHA.
- Reviews run sequentially within one process.
- The diff client supports one page of up to 100 files.
- Diffs exceeding 40,000 characters are rejected.
- GitLab-side diff truncation requires additional handling.
- There is no durable queue or automatic retry mechanism.
- The commit check reduces stale reviews but is not an atomic posting guarantee.
- Structured output validation does not guarantee that findings are correct.
- LLM feedback requires human verification.
- CI runs tests; deployment remains manual.

## Possible improvements

- Durable job queue and persistent review state.
- Recovery from ambiguous posting failures.
- Evaluation examples for buggy, corrected, and adversarial diffs.
- Pagination and handling of oversized or truncated diffs.
- Container packaging and deployment automation.