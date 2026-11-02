import base64
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from standardwebhooks.webhooks import Webhook

from app import app


@pytest.mark.parametrize(
    "case, expected_status",
    [
        ("valid", 200),
        ("tampered", 401),
        ("missing_signature", 401),
    ],
)
def test_webhook_signature(monkeypatch, case, expected_status):
    secret = "whsec_" + base64.b64encode(b"local-test-secret").decode()
    monkeypatch.setenv("GITLAB_WEBHOOK_SIGNING_SECRET", secret)

    body = json.dumps({
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "RETCx/gitlab-ai-reviewer"},
        "object_attributes": {"iid": 1, "action": "open"},
    })

    now = datetime.now(timezone.utc)
    headers = {
        "Content-Type": "application/json",
        "webhook-id": "local-test",
        "webhook-timestamp": str(int(now.timestamp())),
        "webhook-signature": Webhook(secret).sign(
            "local-test", now, body
        ),
    }

    if case == "tampered":
        body = body.replace('"iid": 1', '"iid": 2')
    elif case == "missing_signature":
        headers.pop("webhook-signature")

    with TestClient(app) as client:
        response = client.post(
            "/webhooks/gitlab",
            content=body,
            headers=headers,
        )

    assert response.status_code == expected_status