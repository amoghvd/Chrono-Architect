from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .config import Settings
from .mcp_gateway import StdioAwsMcpGateway
from .models import Approval
from .policy import PolicyViolation
from .workflow import ChronoArchitect

settings = Settings()
read_gateway = StdioAwsMcpGateway(settings.mcp_command, settings.mcp_args, settings.aws_region, True, settings.mcp_tool, settings.analyzer_aws_profile)
write_gateway = StdioAwsMcpGateway(settings.mcp_command, settings.mcp_args, settings.aws_region, False, settings.mcp_tool, settings.executor_aws_profile)
agent = ChronoArchitect(read_gateway, write_gateway, settings)
app = FastAPI(title="Chrono-Architect", version="0.1.0")

class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_id: str = Field(pattern=r"^i-[0-9a-f]{8,17}$")
    target_instance_type: str = Field(pattern=r"^[a-z0-9]+[a-z0-9-]*\.[a-z0-9]+$")
    health_check_url: HttpUrl | None = None

@app.get("/healthz")
def healthz():
    return {"status": "ok", "mode": "real-mcp"}

@app.get("/v1/instances")
async def list_instances():
    return await agent.list_instances()


@app.post("/v1/investigations")
async def investigate(request: AnalyzeRequest):
    try:
        return await agent.investigate(request.instance_id, request.target_instance_type,
                                       str(request.health_check_url) if request.health_check_url else None)
    except (PolicyViolation, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@app.get("/v1/runs/{run_id}/proposal")
def proposal(run_id: str):
    try:
        return agent.store.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc

@app.get("/v1/runs/{run_id}/audit")
def audit(run_id: str):
    return {"events": agent.audit.read(run_id), "chain_valid": agent.audit.verify(run_id)}

@app.post("/v1/runs/{run_id}/execute")
async def execute(run_id: str, approval: Approval):
    try:
        return await agent.execute(run_id, approval)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    except PolicyViolation as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

# Serve the same-origin operator console from the API process.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="frontend")
