"""Typed contracts for every artifact EvidencePilot reads, computes, or emits.

Everything that crosses a module boundary is a model in this file. Two rules
hold throughout:

1. The language model never produces a number in any of these structures.
   Numbers come from deterministic Python in ``tools/``; the model may only
   request authorized tools or write advisory prose, whose accuracy is not
   automatically checked against these structures.
2. ``EvidenceClass`` deliberately has no ``PROOF`` member. A finite replay is
   evidence, never a theorem. ``evidence/certificate.py`` enforces this.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SettingPair = str  # one of "a_b", "a_bp", "ap_b", "ap_bp"

PAIR_ORDER: tuple[str, ...] = ("a_b", "a_bp", "ap_b", "ap_bp")


class ClaimState(StrEnum):
    """Where a claim stands after replay. Never a statement about nature."""

    UNVERIFIED = "UNVERIFIED"  # replay not attempted or not attemptable
    REPRODUCED = "REPRODUCED"  # independent replay lands on the claim
    NOT_REPRODUCED = "NOT_REPRODUCED"  # independent replay contradicts the claim
    INCONCLUSIVE = "INCONCLUSIVE"  # replay ran, but does not settle the claim


class Verdict(StrEnum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"
    HUMAN_DECISION = "HUMAN_DECISION"


class EvidenceClass(StrEnum):
    """What kind of evidence backs a certificate.

    There is intentionally no ``PROOF`` member and there must never be one.
    """

    NONE = "NONE"
    DETERMINISTIC_RECOMPUTE = "DETERMINISTIC_RECOMPUTE"
    STATISTICAL_REPLAY = "STATISTICAL_REPLAY"
    FINITE_VERIFICATION = "FINITE_VERIFICATION"


class Severity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class PhysicalInterpretation(StrEnum):
    """Replay does not establish a physical model or close experimental loopholes."""

    NOT_ASSESSED = "NOT_ASSESSED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class Finding(BaseModel):
    """One deterministic observation, always traceable to a check id."""

    model_config = ConfigDict(frozen=True)

    check_id: str
    severity: Severity
    summary: str
    detail: str = ""
    evidence: dict[str, object] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Inputs: what a submitted experiment package contains
# --------------------------------------------------------------------------


class Manifest(BaseModel):
    package_id: str
    experiment_id: str
    created_at: str
    instrument: str = ""
    operator: str = ""
    files: dict[str, str] = Field(default_factory=dict)  # relative path -> sha256
    environment: dict[str, str] | None = None
    notes: str = ""


class CountRow(BaseModel):
    """Raw coincidence counts for one acquisition sub-run, as recorded.

    Counts are stored exactly as the detectors labelled them. Any documented
    channel inversion lives in the convention, not in the data.
    """

    model_config = ConfigDict(frozen=True)

    block_id: str
    subrun_id: str
    setting_a: str
    setting_b: str
    n_pp: int = Field(ge=0)
    n_pm: int = Field(ge=0)
    n_mp: int = Field(ge=0)
    n_mm: int = Field(ge=0)
    window_ns: float
    flags: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return self.n_pp + self.n_pm + self.n_mp + self.n_mm


class BlockConvention(BaseModel):
    model_config = ConfigDict(frozen=True)

    pair: SettingPair
    alice_channel_map: str = "standard"  # "standard" | "inverted"
    bob_channel_map: str = "standard"  # "standard" | "inverted"
    note: str = ""


class Convention(BaseModel):
    """The registered analysis convention. This is data, not code.

    The whole Maya case turns on the difference between the convention a
    notebook *declares* and the convention it *applies*.
    """

    convention_id: str
    registered_at: str | None = None
    registry: str | None = None
    outcome_map: dict[str, int] = Field(default_factory=lambda: {"ch1": 1, "ch2": -1})
    chsh_combination: dict[SettingPair, int]
    blocks: dict[str, BlockConvention]
    subrun_inclusion: str = "all"  # "all" | "unflagged_only"
    post_selection: dict[str, object] = Field(default_factory=dict)
    classical_bound: float = 2.0
    tsirelson_bound: float = 2.8284271247461903

    @property
    def is_registered(self) -> bool:
        return bool(self.registered_at) and bool(self.registry)


class ClaimedAnalysis(BaseModel):
    """The result a collaborator is asking the group to stand behind."""

    claim_id: str
    submitted_by: str
    submitted_at: str
    dataset_id: str
    dataset_sha256: str
    convention_id: str
    statistic: str
    value: float
    uncertainty: float
    per_pair_correlation: dict[SettingPair, float] = Field(default_factory=dict)
    conclusion: str = ""
    analysis_script: str | None = None
    analysis_script_sha256: str | None = None


class ExperimentPackage(BaseModel):
    """Everything the agent was handed, plus where it came from."""

    root: str
    manifest: Manifest
    counts: list[CountRow]
    convention: Convention
    claim: ClaimedAnalysis


# --------------------------------------------------------------------------
# Computation results
# --------------------------------------------------------------------------


class Correlation(BaseModel):
    model_config = ConfigDict(frozen=True)

    pair: SettingPair
    block_ids: tuple[str, ...]
    n_total: int
    e_value: float
    sigma: float


class CHSHResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    s_value: float
    sigma_s: float
    correlations: tuple[Correlation, ...]
    classical_bound: float
    tsirelson_bound: float
    convention_id: str
    included_subruns: tuple[str, ...]
    excluded_subruns: tuple[str, ...]

    @property
    def sigma_above_bound(self) -> float:
        if self.sigma_s == 0:
            return 0.0
        return (abs(self.s_value) - self.classical_bound) / self.sigma_s

    @property
    def violates_bound(self) -> bool:
        """Legacy name for a plug-in three-sigma screen, not a Bell-test conclusion."""
        return self.sigma_above_bound > 3.0

    def per_pair(self) -> dict[SettingPair, float]:
        return {c.pair: c.e_value for c in self.correlations}


class CHSHDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    convention_valid: bool
    convention_issues: tuple[str, ...]
    claim_in_algebraic_range: bool
    algebraic_bound: float
    empirical_above_tsirelson: bool
    degenerate_uncertainty: bool
    minimum_pair_count: int


class ReplayReport(BaseModel):
    """Independent replay set against the submitted claim."""

    registered: CHSHResult
    robustness_alternative: CHSHResult | None = None
    claimed_value: float
    delta_s: float
    delta_in_sigma: float | None
    agrees: bool
    tolerance: float
    diagnostics: CHSHDiagnostics | None = None


class Deviation(BaseModel):
    model_config = ConfigDict(frozen=True)

    deviation_id: str
    family: str
    target: str
    description: str


class RootCauseCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    deviation: Deviation
    s_value: float
    per_pair: dict[SettingPair, float]
    matches_value: bool
    matches_per_pair: bool

    @property
    def is_full_match(self) -> bool:
        return self.matches_value and self.matches_per_pair


class RootCauseReport(BaseModel):
    candidates: tuple[RootCauseCandidate, ...]
    value_matches: tuple[str, ...]
    full_matches: tuple[str, ...]
    conclusion: str

    @property
    def identified(self) -> Deviation | None:
        if len(self.full_matches) != 1:
            return None
        wanted = self.full_matches[0]
        for c in self.candidates:
            if c.deviation.deviation_id == wanted:
                return c.deviation
        return None


class ProvenanceReport(BaseModel):
    findings: tuple[Finding, ...]

    @property
    def critical(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.CRITICAL)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.WARN)

    @property
    def complete(self) -> bool:
        return not self.critical and not self.warnings


# --------------------------------------------------------------------------
# Outputs: what reaches a human
# --------------------------------------------------------------------------


class EscalationOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    option_id: str
    label: str
    consequence: str


class Escalation(BaseModel):
    """The single decision the agent is allowed to put in front of a person."""

    escalation_id: str
    question: str
    context: str
    options: tuple[EscalationOption, ...]
    recommended_option_id: str | None = None
    deadline_note: str = ""


class VerdictCard(BaseModel):
    verdict: Verdict
    claim_state: ClaimState
    evidence_class: EvidenceClass
    physical_interpretation: PhysicalInterpretation = PhysicalInterpretation.NOT_ASSESSED
    claim_id: str
    headline: str
    root_cause: str | None = None
    numbers: dict[str, float] = Field(default_factory=dict)
    findings: tuple[Finding, ...] = ()
    fired_rule: str = ""
    escalation: Escalation | None = None


class TraceStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    tool: str
    args_digest: str
    duration_ms: float
    outcome: str
    result_digest: str


class ExecutionTrace(BaseModel):
    trace_id: str
    started_at: str
    steps: tuple[TraceStep, ...] = ()

    @property
    def digest(self) -> str:
        return "|".join(f"{s.tool}:{s.result_digest}" for s in self.steps)


class EvidenceCertificate(BaseModel):
    """A signed, reproducible record of what was checked and what was not."""

    certificate_id: str
    issued_at: str
    package_id: str
    claim_id: str
    verdict_card: VerdictCard
    input_hashes: dict[str, str] = Field(default_factory=dict)
    convention_id: str = ""
    tool_versions: dict[str, str] = Field(default_factory=dict)
    trace: ExecutionTrace | None = None
    limitations: tuple[str, ...] = ()
    signature: str = ""


class HumanDecisionInput(BaseModel):
    """An operator's intent, bound to the exact certificate they reviewed."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    certificate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    option_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    actor_display_name: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("actor_display_name", "reason")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("a nonblank, printable explanation and display name are required")
        return value


class HumanDecisionReceipt(BaseModel):
    """A separate local record; never a replacement or authorization of a verdict."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    decision_id: str
    recorded_at: str
    certificate_id: str
    certificate_sha256: str
    escalation_id: str
    selected_option: EscalationOption
    actor_display_name: str
    reason: str
    original_verdict: Verdict
    original_claim_state: ClaimState
    authority: Literal["intent_only"] = "intent_only"
    identity_assurance: Literal["self_reported_not_authenticated"] = (
        "self_reported_not_authenticated"
    )
    action_executed: Literal[False] = False
    checksum: str = ""


class BenchmarkResult(BaseModel):
    """Result of a finite search. Never upgraded to a theorem."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    limit: int
    cases_tested: int
    counterexamples: tuple[int, ...]
    max_steps: int
    max_peak: int
    elapsed_s: float

    @property
    def passed(self) -> bool:
        return not self.counterexamples
