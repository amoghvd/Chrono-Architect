from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpError(RuntimeError):
    pass


class AwsGateway(ABC):
    @abstractmethod
    async def call_cli(self, cli_command: str) -> dict[str, Any]: ...


class StdioAwsMcpGateway(AwsGateway):
    """Real MCP client for awslabs.aws-api-mcp-server's `call_aws` tool."""
    def __init__(self, command: str, args: list[str], region: str,
                 read_only: bool = True, tool_name: str = "call_aws", aws_profile: str | None = None):
        self.command, self.args, self.region = command, args, region
        self.read_only, self.tool_name, self.aws_profile = read_only, tool_name, aws_profile

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        env = dict(os.environ)
        env.update({
            "AWS_REGION": self.region,
            "AWS_API_MCP_TRANSPORT": "stdio",
            "READ_OPERATIONS_ONLY": "true" if self.read_only else "false",
            "AWS_API_MCP_FILE_ACCESS_MODE": "no-access",
        })
        if self.aws_profile:
            env["AWS_PROFILE"] = self.aws_profile
        params = StdioServerParameters(command=self.command, args=self.args, env=env)
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            yield session

    async def call_cli(self, cli_command: str) -> dict[str, Any]:
        if not cli_command.startswith("aws ") or any(x in cli_command for x in ["|", ">", "<", ";", "&&"]):
            raise McpError("Only a single validated AWS CLI command is allowed")
        async with self._session() as session:
            result = await session.call_tool(self.tool_name, {"cli_command": cli_command})
        if result.isError:
            raise McpError(str(result.content))
        texts = [getattr(item, "text", "") for item in result.content]
        joined = "\n".join(t for t in texts if t)
        try:
            envelope = json.loads(joined)
        except json.JSONDecodeError as exc:
            raise McpError(f"MCP returned non-JSON content: {joined[:300]}") from exc
        if isinstance(envelope, list):
            if not envelope:
                raise McpError("MCP returned empty list response")
            envelope = envelope[0]
        if envelope.get("error"):
            raise McpError(envelope["error"])
        response = envelope.get("response", envelope)
        # The server response may contain a serialized CLI JSON payload.
        for key in ("as_json", "json", "output", "stdout"):
            candidate = response.get(key) if isinstance(response, dict) else None
            if isinstance(candidate, str):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            if isinstance(candidate, dict):
                return candidate
        return response


class RecordingGateway(AwsGateway):
    """Test adapter; never used as a production fallback."""
    def __init__(self, responses: dict[str, dict[str, Any]]):
        self.responses = responses
        self.commands: list[str] = []

    async def call_cli(self, cli_command: str) -> dict[str, Any]:
        self.commands.append(cli_command)
        if cli_command not in self.responses:
            raise McpError(f"No recorded response for {cli_command}")
        return self.responses[cli_command]
