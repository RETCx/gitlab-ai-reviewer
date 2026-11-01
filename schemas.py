from typing import Literal

from pydantic import BaseModel, ConfigDict


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    file: str
    severity: Literal["low", "medium", "high"]
    explanation: str
    suggestion: str


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str
    findings: list[Finding]
    suggested_tests: list[str]