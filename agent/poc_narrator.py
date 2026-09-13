"""Bounded Strands narration for one server-selected synthetic package."""

from __future__ import annotations

import os
import time
from pathlib import Path

from agent.investigation import Investigation
from agent.limits import (
    MAX_ELAPSED_SECONDS,
    MAX_MODEL_CALLS,
    MAX_OUTPUT_TOKENS,
    MAX_TOOL_ATTEMPTS,
    configured_limits,
)
from agent.prompts import BOUND_SYSTEM_PROMPT
from agent.researchops_agent import VerificationRun
from evidence.run_metadata import build_run_metadata
from policy.investigation import InvestigationState


class InvocationBudget:
    """Stop before a ninth model request or after the elapsed-time allowance."""

    def __init__(self, investigation: Investigation | None = None):
        self.calls = 0
        self.started = time.monotonic()
        self.exceeded = False
        self.investigation = investigation

    def register_hooks(self, registry, **kwargs):
        from strands.hooks import BeforeModelCallEvent

        registry.add_callback(BeforeModelCallEvent, self.before_model)

    def before_model(self, event):
        if self.investigation and self.investigation.snapshot()["state"] in {
            InvestigationState.INVALIDATED,
            InvestigationState.FAILED,
            InvestigationState.BUDGET_EXCEEDED,
        }:
            event.cancel = "Investigation stopped. Use the independent verification result."
            return
        if self.calls >= MAX_MODEL_CALLS or time.monotonic() - self.started >= MAX_ELAPSED_SECONDS:
            self.exceeded = True
            event.cancel = "POC invocation budget reached. Use the deterministic certificate."
            return
        self.calls += 1


def build_bound_tools(
    root: Path, run: VerificationRun, calls: list[str], investigation: Investigation | None = None
):
    """Create five no-argument tools, each closing over its authorized package."""
    from strands import tool

    from agent.investigation import TOOL_NAMES

    session = investigation if investigation is not None else Investigation(root, run)

    def wrap(name):
        def invoke() -> dict:
            result = session.invoke(name)
            # Includes rejected attempts. See agent_trace for authoritative outcomes.
            if len(calls) <= MAX_TOOL_ATTEMPTS:
                calls.append(name)
            return result

        invoke.__name__ = name
        invoke.__doc__ = f"Return {name} for the server-selected experiment package."
        return tool(name=name)(invoke)

    return [wrap(name) for name in TOOL_NAMES]


def narrate_case(
    root: Path, run: VerificationRun, *, model_id: str | None = None, region_name: str | None = None
) -> dict:
    """Run real tool calling, reporting failures without replacing the certificate."""
    model_id = model_id if model_id is not None else os.environ.get("EVIDENCEPILOT_MODEL_ID", "")
    investigation = Investigation(root, run)
    region = region_name or os.environ.get("AWS_REGION", "ap-southeast-2")
    metadata = build_run_metadata(
        run.certificate,
        model_id=model_id,
        region=region,
        prompt=BOUND_SYSTEM_PROMPT,
        limits=configured_limits(),
    )
    if not model_id:
        return {
            "status": "not_configured",
            "authority": "advisory",
            "text": None,
            "investigation": investigation.report(),
            "run_metadata": metadata,
        }

    calls: list[str] = []
    budget = InvocationBudget(investigation)
    base = {
        "authority": "advisory",
        "model_id": metadata["model"]["id"],
        "tool_calls": calls,
        "run_metadata": metadata,
    }
    try:
        from botocore.config import Config
        from strands import Agent
        from strands.models import BedrockModel

        model = BedrockModel(
            model_id=model_id,
            region_name=region,
            temperature=0.0,
            max_tokens=MAX_OUTPUT_TOKENS,
            streaming=False,
            boto_client_config=Config(
                connect_timeout=5, read_timeout=30, retries={"total_max_attempts": 1}
            ),
        )
        agent = Agent(
            model=model,
            tools=build_bound_tools(root, run, calls, investigation),
            hooks=[budget],
            callback_handler=None,
            retry_strategy=None,
            system_prompt=BOUND_SYSTEM_PROMPT,
        )
        result = agent("Verify the selected package using the tools and explain its certificate.")
        text = "".join(b.get("text", "") for b in result.message.get("content", []))
        complete = investigation.complete and bool(text.strip())
        return {
            **base,
            "status": "complete" if complete and not budget.exceeded else "incomplete",
            "text": text[:12000],
            "model_calls": budget.calls,
            "budget_exceeded": budget.exceeded,
            "stop_reason": result.stop_reason,
            "usage": dict(result.metrics.accumulated_usage),
            "investigation": investigation.report(),
            "prose_checked": False,
        }
    except Exception as exc:
        # Service exception messages can contain account identifiers or endpoints.
        # Report only the documented error code or exception type, never credentials.
        response = getattr(exc, "response", None) or {}
        code = response.get("Error", {}).get("Code", type(exc).__name__)
        return {
            **base,
            "status": "error",
            "error_code": code,
            "text": None,
            "model_calls": budget.calls,
            "investigation": investigation.report(),
        }
