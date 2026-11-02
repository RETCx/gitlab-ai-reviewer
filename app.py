import os

from fastapi import HTTPException, Request
from standardwebhooks.webhooks import Webhook, WebhookVerificationError

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from fastapi import BackgroundTasks

from review_job import run_review

app = FastAPI()


class Project(BaseModel):
    path_with_namespace: str


class MergeRequestAttributes(BaseModel):
    iid: int = Field(gt=0)
    action: str


class MergeRequestEvent(BaseModel):
    object_kind: Literal["merge_request"]
    project: Project
    object_attributes: MergeRequestAttributes


@app.post("/webhooks/gitlab")
async def receive_webhook(
    event: MergeRequestEvent,
    request: Request,
    background_tasks: BackgroundTasks,
):
    secret = os.environ.get("GITLAB_WEBHOOK_SIGNING_SECRET")
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Webhook signing secret is not configured",
        )

    raw_body = await request.body()

    try:
        Webhook(secret).verify(raw_body, dict(request.headers))
    except (WebhookVerificationError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    project = event.project.path_with_namespace
    mr_iid = event.object_attributes.iid
    action = event.object_attributes.action

    if project != "RETCx/gitlab-ai-reviewer":
        return {"status": "ignored", "reason": "Project not allowed"}

    if action not in {"open", "reopen", "update"}:
        return {"status": "ignored", "reason": "Action not supported"}

    enabled = os.environ.get("AUTO_REVIEW_ENABLED") == "1"

    if enabled:
        background_tasks.add_task(run_review, project, mr_iid)

    return {
        "status": "accepted" if enabled else "received",
        "project": project,
        "mr_iid": mr_iid,
        "action": action,
    }