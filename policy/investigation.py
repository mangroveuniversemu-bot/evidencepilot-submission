"""Legal investigation actions; this policy never computes physical quantities."""

from enum import StrEnum

from agent.schemas import ProvenanceReport, ReplayReport


class InvestigationState(StrEnum):
    NEW = "new"
    PACKAGE_READ = "package_read"
    REPLAY_REQUIRED = "replay_required"
    ROOT_CAUSE_REQUIRED = "root_cause_required"
    READY_TO_ISSUE = "ready_to_issue"
    COMPLETE = "complete"
    INVALIDATED = "invalidated"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"


_ACTIONS = {
    InvestigationState.NEW: ("read_experiment_package",),
    InvestigationState.PACKAGE_READ: ("check_provenance",),
    InvestigationState.REPLAY_REQUIRED: ("replay_chsh",),
    InvestigationState.ROOT_CAUSE_REQUIRED: ("search_root_cause",),
    InvestigationState.READY_TO_ISSUE: ("issue_verdict",),
}


def allowed_actions(state: InvestigationState) -> tuple[str, ...]:
    return _ACTIONS.get(state, ())


def after_provenance(report: ProvenanceReport) -> InvestigationState:
    if report.critical:
        return InvestigationState.READY_TO_ISSUE
    return InvestigationState.REPLAY_REQUIRED


def after_replay(report: ReplayReport | None) -> InvestigationState:
    # A domain replay failure must be adjudicated, not silently called a pass.
    if report is not None and not report.agrees:
        return InvestigationState.ROOT_CAUSE_REQUIRED
    return InvestigationState.READY_TO_ISSUE
