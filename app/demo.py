"""Offline rehearsal entry point; never invokes a model or changes a verdict."""

from __future__ import annotations

import argparse
import json

from app.poc import CASES, handle_request


def run_demo(case: str) -> dict:
    """Project verified output into clearly separated presentation sections."""
    result = handle_request({"case": case, "narrate": False})
    if not result["ok"]:
        return result
    certificate = result["certificate"]
    card = certificate["verdict_card"]
    return {
        "mode": "verification_only",
        "live_model_tested": False,
        "data_origin": result["data_origin"],
        "case": case,
        "verification": {
            "verdict": card["verdict"],
            "rule": card["fired_rule"],
            "headline": card["headline"],
            "integrity_valid": result["certificate_integrity_valid"],
            "integrity_note": result["integrity_note"],
            "certificate": certificate,
        },
        "ai_advisory": result["advisory"],
        "human_attention": {
            "escalation": card["escalation"],
            "decision_recording_supported": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASES, "all"], default="maya")
    args = parser.parse_args(argv)
    cases = list(CASES) if args.case == "all" else [args.case]
    results = [run_demo(case) for case in cases]
    print(json.dumps(results, indent=2, ensure_ascii=True))
    return 0 if all(item.get("verification", {}).get("integrity_valid") for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
