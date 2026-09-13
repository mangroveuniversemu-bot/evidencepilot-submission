"""Render verdicts and certificates for the two audiences that read them.

The terminal rendering is for the person with fourteen minutes before a
meeting. The markdown rendering is for whoever opens the certificate in six
months and needs to know exactly what was and was not checked.
"""

from __future__ import annotations

from agent.schemas import (
    ClaimState,
    EvidenceCertificate,
    Severity,
    Verdict,
    VerdictCard,
)

WIDTH = 74


def _banner(card: VerdictCard) -> str:
    """The headline has to match the claim state, not just the verdict.

    A claim blocked for stale inputs was never replayed, so calling it "not
    reproduced" would overstate what was checked. A finite search that found no
    counterexample has not reproduced anything either.
    """
    if card.verdict is Verdict.ALLOW:
        return "CLAIM REPRODUCED"
    if card.verdict is Verdict.HUMAN_DECISION:
        return "CONCLUSION DEPENDS ON A JUDGEMENT CALL"
    if card.verdict is Verdict.BLOCK:
        if card.claim_state is ClaimState.UNVERIFIED:
            return "CLAIM NOT VERIFIABLE AS SUBMITTED"
        return "CLAIM NOT REPRODUCED"
    if card.claim_state is ClaimState.INCONCLUSIVE:
        return "CLAIM REMAINS OPEN"
    if card.claim_state is ClaimState.UNVERIFIED:
        return "CLAIM NOT VERIFIED"
    return "CLAIM REPRODUCED, NOT CERTIFIABLE"


_PAIR_LABEL = {"a_b": "E(a,b)  ", "a_bp": "E(a,b') ", "ap_b": "E(a',b) ", "ap_bp": "E(a',b')"}


def _rule(char: str = "=") -> str:
    return char * WIDTH


def render_verdict_text(card: VerdictCard) -> str:
    lines: list[str] = [_rule(), f"  VERDICT: {_banner(card)}", _rule()]
    lines.append(f"  Claim       {card.claim_id}")
    lines.append(f"  Decision    {card.verdict.value}   (rule {card.fired_rule})")
    lines.append(f"  Claim state {card.claim_state.value}")
    lines.append(f"  Evidence    {card.evidence_class.value}")
    lines.append(f"  Physics     {card.physical_interpretation.value}")
    lines.append("")
    lines.append(f"  {card.headline}")

    numbers = card.numbers
    if "replayed_S" in numbers:
        lines.append("")
        lines.append(f"  Submitted   S = {numbers['claimed_S']:.4f}")
        lines.append(
            f"  Replayed    S = {numbers['replayed_S']:.4f} +/- {numbers['sigma_S']:.4f}"
            " (plug-in SE)"
        )
        if "sigma_above_bound" in numbers:
            lines.append(
                f"  Screen      {numbers['sigma_above_bound']:+.1f} sigma vs classical bound "
                f"{numbers['classical_bound']:g}; not a certified Bell test"
            )
        scale = (
            f" = {abs(numbers['delta_in_sigma']):.1f} plug-in sigma"
            if "delta_in_sigma" in numbers
            else "; sigma ratio unavailable (zero plug-in SE)"
        )
        lines.append(f"  Difference  {numbers['delta_S']:+.4f}{scale}")
        if "replayed_S_excluding_flagged" in numbers:
            lines.append(
                f"  Alternative S = {numbers['replayed_S_excluding_flagged']:.4f} "
                "(flagged sub-runs excluded)"
            )
        lines.append("")
        for pair, label in _PAIR_LABEL.items():
            key = f"E({pair})"
            if key in numbers:
                lines.append(f"    {label} = {numbers[key]:+.4f}")

    if card.root_cause:
        lines.append("")
        lines.append("  ROOT CAUSE")
        lines.extend(_wrap(card.root_cause, "    "))

    blocking = [f for f in card.findings if f.severity is not Severity.INFO]
    if blocking:
        lines.append("")
        lines.append("  FINDINGS")
        for finding in blocking:
            lines.append(f"    [{finding.severity.value}] {finding.check_id}  {finding.summary}")

    if card.escalation is None:
        lines.append("")
        lines.append("  NO DECISION REQUIRED. Certificate issued.")
    else:
        escalation = card.escalation
        lines.append("")
        lines.append(_rule("-"))
        lines.append("  ONE DECISION REQUIRED")
        lines.append(_rule("-"))
        lines.extend(_wrap(escalation.question, "  "))
        lines.append("")
        lines.extend(_wrap(escalation.context, "  "))
        lines.append("")
        for option in escalation.options:
            marker = "*" if option.option_id == escalation.recommended_option_id else " "
            lines.append(f"  [{marker}] {option.option_id}")
            lines.extend(_wrap(option.label, "        "))
            lines.extend(_wrap(f"-> {option.consequence}", "        "))
        if escalation.recommended_option_id:
            lines.append("")
            lines.append(f"  Suggested: {escalation.recommended_option_id}  (* above)")
        else:
            lines.append("")
            lines.append("  No option is recommended. This one is yours to make.")
        if escalation.deadline_note:
            lines.append(f"  {escalation.deadline_note}")

    lines.append(_rule())
    return "\n".join(lines)


def _wrap(text: str, indent: str) -> list[str]:
    import textwrap

    return textwrap.wrap(
        text, width=WIDTH - len(indent), initial_indent=indent, subsequent_indent=indent
    ) or [indent.rstrip()]


def render_certificate_markdown(certificate: EvidenceCertificate) -> str:
    card = certificate.verdict_card
    out: list[str] = [
        f"# Evidence certificate {certificate.certificate_id}",
        "",
        f"- **Claim**: `{certificate.claim_id}`",
        f"- **Package**: `{certificate.package_id}`",
        f"- **Convention**: `{certificate.convention_id}`",
        f"- **Issued**: {certificate.issued_at}",
        f"- **Verdict**: `{card.verdict.value}` (rule `{card.fired_rule}`)",
        f"- **Claim state**: `{card.claim_state.value}`",
        f"- **Evidence class**: `{card.evidence_class.value}`",
        f"- **Physical interpretation**: `{card.physical_interpretation.value}`",
        f"- **Integrity checksum (not authenticated)**: `{certificate.signature}`",
        "",
        "## Headline",
        "",
        card.headline,
    ]

    if card.root_cause:
        out += ["", "## Root cause", "", card.root_cause]

    if card.numbers:
        out += ["", "## Numbers", "", "| quantity | value |", "| --- | ---: |"]
        out += [f"| `{key}` | {value:.6g} |" for key, value in card.numbers.items()]

    out += ["", "## Checks", "", "| check | severity | summary |", "| --- | --- | --- |"]
    out += [f"| `{f.check_id}` | {f.severity.value} | {f.summary} |" for f in card.findings]

    if certificate.input_hashes:
        out += ["", "## Inputs", "", "| file | sha256 |", "| --- | --- |"]
        out += [f"| `{name}` | `{h}` |" for name, h in sorted(certificate.input_hashes.items())]

    if card.escalation is not None:
        escalation = card.escalation
        out += ["", "## Decision required", "", escalation.question, "", escalation.context, ""]
        for option in escalation.options:
            recommended = option.option_id == escalation.recommended_option_id
            suffix = " *(suggested)*" if recommended else ""
            out += [f"- **{option.option_id}**{suffix} — {option.label} _{option.consequence}_"]
        if card.escalation.recommended_option_id is None:
            out += [
                "",
                "_No option is recommended; this decision is deliberately left to a human._",
            ]

    if certificate.trace is not None:
        out += [
            "",
            "## Execution trace",
            "",
            "| # | tool | outcome | args | result |",
            "| ---: | --- | --- | --- | --- |",
        ]
        out += [
            f"| {s.index} | `{s.tool}` | {s.outcome} | `{s.args_digest}` | `{s.result_digest}` |"
            for s in certificate.trace.steps
        ]

    out += ["", "## Limitations", ""]
    out += [f"- {line}" for line in certificate.limitations]
    return "\n".join(out) + "\n"


def render_queue_summary(cards: list[VerdictCard]) -> str:
    counts = {verdict: 0 for verdict in Verdict}
    for card in cards:
        counts[card.verdict] += 1
    needs_human = [c for c in cards if c.escalation is not None]
    lines = [
        _rule(),
        "  REVIEW QUEUE",
        _rule(),
        f"  {counts[Verdict.ALLOW]} verified"
        f"   |  {counts[Verdict.REVIEW]} review"
        f"   |  {counts[Verdict.BLOCK]} blocked"
        f"   |  {counts[Verdict.HUMAN_DECISION]} needs your judgement",
        "",
    ]
    for card in cards:
        flag = "  " if card.escalation is None else "->"
        lines.append(f"  {flag} {card.verdict.value:<15} {card.claim_id:<24} {card.fired_rule}")
    lines += [
        "",
        f"  {len(cards) - len(needs_human)} of {len(cards)} claims are settled and need nothing "
        "from you.",
        f"  {len(needs_human)} require a decision.",
        _rule(),
    ]
    return "\n".join(lines)
