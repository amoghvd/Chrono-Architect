import pytest

from chrono_architect.mcp_gateway import McpError, RecordingGateway


@pytest.mark.asyncio
async def test_recording_gateway_never_falls_back_to_fake_data():
    gateway = RecordingGateway({})
    with pytest.raises(McpError):
        await gateway.call_cli("aws ec2 describe-instances")
