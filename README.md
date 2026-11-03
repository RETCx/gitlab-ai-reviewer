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

## How the code works

### Webhook and API requests

`run_server.py` asks for missing credentials and starts Uvicorn with `app:app`:
the `app` variable in `app.py`. It enables automatic reviews in this local
launcher. GitLab already stores and displays a merge request when it sends a
webhook; the webhook tells this service that an event occurred. It does not
supply the complete code diff to this service.

| Step | Direction | Code | Purpose |
| --- | --- | --- | --- |
| 1 | GitLab POST -> service | `app.py`: `POST /webhooks/gitlab` | Notify the service of a merge request event. |
| 2 | Service GET -> GitLab API | `review_job.py`: `fetch_mr()` | Read the current MR state and source commit SHA. |
| 3 | Service GET -> GitLab API | `fetch_diff.py`: `fetch_mr_diff()` | Read the changed files and diff text. |
| 4 | Service POST -> OpenRouter | `review_diff.py`: `review_diff()` | Ask the LLM for a structured review. |
| 5 | Service GET -> GitLab API | `review_job.py`: `fetch_mr()` | Check the MR state and SHA again before posting. |
| 6 | Service POST -> GitLab API | `post_review.py`: `post_review()` | Add a Markdown note to the MR. |

In step 1, FastAPI parses the webhook JSON into `MergeRequestEvent`. The
payload includes more fields than this model uses; the code extracts only the
project path, MR IID (for example, `!1`), and action. `app.py` verifies the
signature using the original request body and headers, accepts only the
configured project and `open`, `reopen`, or `update` actions, and schedules
`run_review()` when `AUTO_REVIEW_ENABLED=1`. The response status `accepted`
means the work was scheduled, not that a review was posted.

The three credentials have distinct roles: `GITLAB_WEBHOOK_SIGNING_SECRET`
verifies incoming GitLab webhooks; `GITLAB_TOKEN` authenticates outgoing
GitLab API requests to read MRs/diffs and post notes; `OPENROUTER_API_KEY`
authenticates the LLM request.

### Reviewing a commit

`review_job.py` first skips MRs that are no longer open. It stores the source
commit SHA in a key `(project_path, mr_iid, sha)` and skips a key already in
`completed_reviews`. `fetch_mr_diff()` asks GitLab for each changed file's
`new_path` and `diff`. This is patch text: `+` marks added lines, `-` removed
lines, and `@@` a changed section. No local Git checkout is needed.

After the LLM responds, the second `fetch_mr()` checks whether the MR is still
open and has the same source SHA. If a new commit was pushed during review,
the service discards the stale result. This check reduces stale comments but
cannot make posting atomic with GitLab changes.

### Structured review output

`schemas.py` defines a `Review` with a `summary`, a list of `Finding` objects,
and a list of `suggested_tests`. One `Finding` contains:

| Field | Meaning |
| --- | --- |
| `file` | Path reported by the LLM, such as `examples/demo_app.py`. |
| `severity` | One of `low`, `medium`, or `high`. |
| `explanation` | The reported defect and its triggering case. |
| `suggestion` | A proposed fix. |

`Review.model_json_schema()` in `review_diff.py` produces a JSON Schema for
the full review, including the nested `Finding` fields, and sends it to
OpenRouter. `Review.model_validate_json(content)` then validates the returned
JSON recursively. Pydantic requires the declared fields and types, rejects
extra fields, and restricts `severity` to the listed values. It does not
check whether a named file exists or whether a finding is factually correct;
the field names and system prompt guide the LLM's wording.

`post_review.py` formats the validated review as Markdown and creates a
top-level MR note. Only after the post succeeds does `review_job.py` add the
key to `completed_reviews`. That set lives in process memory, so restarting
the service clears it. A failure in `run_review()` is logged; the earlier
webhook HTTP response cannot report that later failure.

The command-line demo under `if __name__ == "__main__":` in `review_diff.py`
runs only when that file is executed directly. Importing and calling
`review_diff()` from `review_job.py` does not run the demo block.

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