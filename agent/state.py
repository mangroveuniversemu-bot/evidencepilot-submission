"""The working state a single verification run accumulates.

Every field is filled by deterministic tooling. The agent narrates this object;
it never edits it.
"""

from __future__ import annotations

from pydantic import BaseModel

from agent.schemas import (
    ExperimentPackage,
    ProvenanceReport,
    ReplayReport,
    RootCauseReport,
)


class Assessment(BaseModel):
    """Everything known about one claim, before policy is applied."""

    package: ExperimentPackage
    provenance: ProvenanceReport
    replay: ReplayReport | None = None
    root_cause: RootCauseReport | None = None
    replay_error: str | None = None

    @property
    def claim_id(self) -> str:
        return self.package.claim.claim_id

    @property
    def package_id(self) -> str:
        return self.package.manifest.package_id
