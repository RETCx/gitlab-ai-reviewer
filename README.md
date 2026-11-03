# GitLab AI Reviewer

A Python proof of concept that reviews GitLab merge requests using an LLM
and posts structured feedback as a merge request comment.

## One review, from start to finish

Imagine you open GitLab MR `!1` to merge `feat/add-demo-code` into `main`.
GitLab already stores this MR and shows it on the Merge requests page. Our
service listens for an event and writes a review comment on that existing MR.

1. **GitLab tells us about the MR.** GitLab sends an HTTP `POST` to
   `/webhooks/gitlab`. The JSON body includes the project path, MR number
   (`iid: 1`), and action (`open` or `update`), among other details. It does
   **not** contain the full code diff. `run_server.py` starts Uvicorn with
   `app:app`: the `app` object in `app.py` receives this request.
2. **`app.py` checks the request.** It verifies the webhook signature with
   `GITLAB_WEBHOOK_SIGNING_SECRET`, then checks the project and action. If
   automatic review is enabled, it schedules `run_review(project, 1)` as a
   background task. It immediately replies `accepted` to GitLab. This means
   the request was accepted; the review may still fail later.
3. **`review_job.py` gets the current MR.** `fetch_mr()` sends a `GET` to
   GitLab's API using `GITLAB_TOKEN`. The response includes the MR's current
   state and the SHA of the latest commit on its source branch. The job skips
   a closed MR or a `(project, MR number, SHA)` it already reviewed.
4. **It gets the code changes.** `fetch_mr_diff()` sends another `GET` to
   GitLab. GitLab returns changed file paths and patch text: `+` means an
   added line, `-` a removed line, and `@@` a changed section. Our service
   joins these patches and skips diffs longer than 40,000 characters. It
   does not clone either branch locally.
5. **The LLM reviews that diff.** `review_diff()` sends it to OpenRouter
   using `OPENROUTER_API_KEY`. `schemas.py` describes the answer:
   `Review` has a `summary`, `findings: list[Finding]`, and
   `suggested_tests`. Each `Finding` has a `file` path, `severity`
   (`low`/`medium`/`high`), `explanation`, and `suggestion`.

   For MR `!1`, a short example of the expected JSON is:

   ```json
   {
     "summary": "Empty input raises the wrong exception.",
     "findings": [{
       "file": "examples/demo_app.py",
       "severity": "high",
       "explanation": "average([]) raises ZeroDivisionError, not ValueError.",
       "suggestion": "Raise ValueError before dividing."
     }],
     "suggested_tests": ["Check average([]) raises ValueError."]
   }
   ```

   `Review.model_json_schema()` tells the LLM which JSON fields to return,
   including the fields nested inside `Finding`.
   `Review.model_validate_json(content)` checks the answer afterward.
   This checks the *shape* of the response; it does not open the reported
   file or prove that the finding is correct.

6. **It checks and posts.** `fetch_mr()` sends a second `GET` because the MR
   could have changed while the LLM was working. If the MR is still open and
   its SHA is unchanged, `post_review()` sends an outgoing `POST` to GitLab's
   `/notes` API to create a Markdown comment on the MR. Only then does the
   job add its `(project, MR number, SHA)` key to `completed_reviews`.

The `POST` in `@app.post("/webhooks/gitlab")` is **incoming** (GitLab calls
our service). The `POST` in `post_review()` is **outgoing** (our service calls
GitLab). `completed_reviews` lives only in this Python process, so it is
cleared when the service restarts. Failures after `accepted` are logged by
`run_review()`; they are not sent in the earlier HTTP response.

When `review_job.py` imports and calls `review_diff()`, Python runs that
function directly. The demo block under `if __name__ == "__main__":` in
`review_diff.py` runs only when you execute that file itself.

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