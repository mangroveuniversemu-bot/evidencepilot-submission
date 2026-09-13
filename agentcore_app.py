"""AgentCore HTTP entrypoint; the AWS service authenticates callers with IAM."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from app.poc import handle_request

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """Verify an allowlisted synthetic case and optionally narrate with Bedrock."""
    return handle_request(payload)


if __name__ == "__main__":
    app.run()
