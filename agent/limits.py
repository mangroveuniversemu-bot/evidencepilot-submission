"""Host-owned limits; none can be increased by a model or hosted API caller."""

MAX_MODEL_CALLS = 8
MAX_OUTPUT_TOKENS = 1024
MAX_ELAPSED_SECONDS = 120
MAX_TOOL_ATTEMPTS = 16
MAX_OBSERVATION_BYTES = 16 * 1024
MAX_TOTAL_OBSERVATION_BYTES = 64 * 1024


def configured_limits() -> dict[str, int]:
    return {
        "model_calls": MAX_MODEL_CALLS,
        "output_tokens_per_call": MAX_OUTPUT_TOKENS,
        "elapsed_seconds_checked_before_call": MAX_ELAPSED_SECONDS,
        "tool_attempts": MAX_TOOL_ATTEMPTS,
        "observation_bytes_per_tool": MAX_OBSERVATION_BYTES,
        "accepted_observation_bytes_total": MAX_TOTAL_OBSERVATION_BYTES,
    }
