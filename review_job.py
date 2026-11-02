import logging
import os
from threading import Lock
from time import perf_counter
from urllib.parse import quote

import httpx

from fetch_diff import fetch_mr_diff
from post_review import post_review
from review_diff import review_diff

logger = logging.getLogger(__name__)
review_lock = Lock()
completed_reviews = set()


def fetch_mr(project_path: str, mr_iid: int) -> dict:
    project = quote(project_path, safe="")
    response = httpx.get(
        f"https://gitlab.com/api/v4/projects/{project}"
        f"/merge_requests/{mr_iid}",
        headers={"PRIVATE-TOKEN": os.environ["GITLAB_TOKEN"]},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def run_review(project_path: str, mr_iid: int):
    # Process one review at a time in this POC.
    with review_lock:
        started = perf_counter()

        try:
            mr = fetch_mr(project_path, mr_iid)

            if mr["state"] != "opened":
                logger.info("Skipped MR !%s: not open", mr_iid)
                return

            sha = mr["sha"]
            if not sha:
                raise ValueError("Merge request has no commit SHA")

            key = (project_path, mr_iid, sha)

            if key in completed_reviews:
                logger.info("Skipped MR !%s: already reviewed", mr_iid)
                return

            logger.info("Review started: MR !%s, SHA %s", mr_iid, sha)

            diff = fetch_mr_diff(project_path, mr_iid)
            if len(diff) > 40_000:
                raise ValueError("Diff exceeds the POC size limit")

            review = review_diff(
                diff,
                os.environ["OPENROUTER_API_KEY"],
                os.environ.get("OPENROUTER_MODEL", "openai/gpt-5-mini"),
            )

            latest = fetch_mr(project_path, mr_iid)
            if latest["state"] != "opened" or latest["sha"] != sha:
                logger.info("Skipped posting: MR changed during review")
                return

            note_id = post_review(project_path, mr_iid, review)
            completed_reviews.add(key)

            logger.info(
                "Review posted: MR !%s, note %s, duration %.2fs",
                mr_iid,
                note_id,
                perf_counter() - started,
            )

        except Exception:
            logger.exception("Review failed: MR !%s", mr_iid)