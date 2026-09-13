"""Command line entry point.

python -m app.main verify examples/maya_case/inputs
python -m app.main queue examples/review_queue/queue.json
python -m app.main benchmark collatz --limit 1000000
python -m app.main agent examples/maya_case/inputs      # needs AWS credentials
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.prompts import DETERMINISTIC_NOTE
from agent.researchops_agent import verify_package
from evidence.certificate import finite_verification_card, issue_finite_certificate
from tools.benchmark_runner import verify_collatz
from tools.report_generator import (
    render_certificate_markdown,
    render_queue_summary,
    render_verdict_text,
)


def _write_outputs(out_dir: Path, stem: str, certificate) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / f"{stem}.md"
    js = out_dir / f"{stem}.json"
    md.write_text(render_certificate_markdown(certificate), encoding="utf-8")
    js.write_text(certificate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return [md, js]


def cmd_verify(args: argparse.Namespace) -> int:
    run = verify_package(args.package, deadline_note=args.deadline_note)
    if args.json:
        print(run.certificate.model_dump_json(indent=2))
    else:
        print(DETERMINISTIC_NOTE)
        print()
        print(render_verdict_text(run.card))
    if args.out:
        for path in _write_outputs(Path(args.out), run.certificate.certificate_id, run.certificate):
            print(f"wrote {path}", file=sys.stderr)
    return 0 if run.card.verdict.value in {"ALLOW", "REVIEW"} else 1


def cmd_queue(args: argparse.Namespace) -> int:
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    base = Path(args.queue).resolve().parents[2]
    cards = []
    runs = []
    for relative in queue["packages"]:
        candidate = Path(relative)
        if not candidate.is_dir():
            candidate = base / relative
        run = verify_package(candidate, deadline_note=args.deadline_note)
        runs.append(run)
        cards.append(run.card)

    print(DETERMINISTIC_NOTE)
    print()
    print(render_queue_summary(cards))
    for run in runs:
        if run.card.escalation is not None:
            print()
            print(render_verdict_text(run.card))
    if args.out:
        for run in runs:
            _write_outputs(Path(args.out), run.certificate.certificate_id, run.certificate)
        print(f"wrote {len(runs)} certificates to {args.out}", file=sys.stderr)
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    if args.name != "collatz":
        print(f"unknown benchmark: {args.name}", file=sys.stderr)
        return 2
    result = verify_collatz(args.limit)
    card = finite_verification_card(result, "the Collatz conjecture")
    certificate = issue_finite_certificate(card, result)
    print(DETERMINISTIC_NOTE)
    print()
    print(render_verdict_text(card))
    print()
    for limitation in certificate.limitations:
        print(f"  ! {limitation}")
    if args.out:
        _write_outputs(Path(args.out), certificate.certificate_id, certificate)
    return 0


def cmd_agent(args: argparse.Namespace) -> int:
    from agent.researchops_agent import run_model_report

    report = run_model_report(
        args.package,
        model_id=args.model_id,
        region_name=args.region,
        deadline_note=args.deadline_note,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["advisory"].get("text") or "No model explanation is available.")
        print(f"Investigation: {report['advisory']['status']}", file=sys.stderr)
    return 0 if report["advisory"]["status"] == "complete" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evidencepilot", description=__doc__)
    parser.add_argument(
        "--deadline-note", default="", help="context line shown with any escalation"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="verify one experiment package")
    verify.add_argument("package")
    verify.add_argument("--json", action="store_true", help="print the certificate as JSON")
    verify.add_argument("--out", help="directory to write the certificate into")
    verify.set_defaults(func=cmd_verify)

    queue = subparsers.add_parser("queue", help="verify a review queue of packages")
    queue.add_argument("queue")
    queue.add_argument("--out", help="directory to write certificates into")
    queue.set_defaults(func=cmd_queue)

    benchmark = subparsers.add_parser("benchmark", help="run a finite verification benchmark")
    benchmark.add_argument("name", choices=["collatz"])
    benchmark.add_argument("--limit", type=int, default=100_000)
    benchmark.add_argument("--out", help="directory to write the certificate into")
    benchmark.set_defaults(func=cmd_benchmark)

    agent = subparsers.add_parser("agent", help="run the Strands agent against Bedrock")
    agent.add_argument("package")
    agent.add_argument("--model-id", default=None, help="or set EVIDENCEPILOT_MODEL_ID")
    agent.add_argument("--region", default=None)
    agent.add_argument("--json", action="store_true", help="include certificate and both traces")
    agent.set_defaults(func=cmd_agent)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # --deadline-note is defined on the top-level parser; give subcommands a default.
    if not hasattr(args, "deadline_note"):
        args.deadline_note = ""
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
