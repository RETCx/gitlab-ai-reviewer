import os
from urllib.parse import quote

import httpx


project_path = "RETCx/gitlab-ai-reviewer"
mr_iid = 1

token = os.environ.get("GITLAB_TOKEN")
if not token:
    raise SystemExit("Please set GITLAB_TOKEN first.")

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

print(f"HTTP status: {response.status_code}")
response.raise_for_status()

for changed_file in response.json():
    print(f"\nFile: {changed_file['new_path']}")
    print(changed_file["diff"])