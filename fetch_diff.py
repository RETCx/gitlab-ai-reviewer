import os
from urllib.parse import quote

import httpx


def fetch_mr_diff(project_path: str, mr_iid: int) -> str:
    token = os.environ.get("GITLAB_TOKEN")
    if not token:
        raise ValueError("Please set GITLAB_TOKEN first.")

    encoded_project = quote(project_path, safe="")
    url = (
        f"https://gitlab.com/api/v4/projects/{encoded_project}"
        f"/merge_requests/{mr_iid}/diffs"
    )

    response = httpx.get(
        url,
        headers={"PRIVATE-TOKEN": token},
        params={"per_page": 100},
        timeout=20,
    )
    response.raise_for_status()

    if response.headers.get("X-Next-Page"):
        raise ValueError("Multiple diff pages are not supported yet.")

    sections = []
    for changed_file in response.json():
        sections.append(
            f"File: {changed_file['new_path']}\n"
            f"{changed_file['diff']}"
        )

    if not sections:
        raise ValueError("No diff found.")

    return "\n\n".join(sections)


if __name__ == "__main__":
    print(fetch_mr_diff("RETCx/gitlab-ai-reviewer", 1))