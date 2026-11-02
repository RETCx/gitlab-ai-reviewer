import getpass
import logging
import os

import uvicorn


if __name__ == "__main__":
    for name in (
        "GITLAB_WEBHOOK_SIGNING_SECRET",
        "GITLAB_TOKEN",
        "OPENROUTER_API_KEY",
    ):
        if not os.environ.get(name):
            value = getpass.getpass(f"{name}: ").strip()
            if not value:
                raise SystemExit(f"{name} is required")
            os.environ[name] = value

    os.environ.setdefault("OPENROUTER_MODEL", "openai/gpt-5-mini")
    os.environ["AUTO_REVIEW_ENABLED"] = "1"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    uvicorn.run("app:app", host="127.0.0.1", port=8000)