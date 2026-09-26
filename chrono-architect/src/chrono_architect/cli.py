import asyncio
import json
from pathlib import Path

import typer

from .api import agent
from .models import Approval

app = typer.Typer(help="Chrono-Architect safe AWS FinOps agent")

@app.command()
def investigate(instance_id: str, target_type: str, health_check_url: str | None = None):
    proposal = asyncio.run(agent.investigate(instance_id, target_type, health_check_url))
    typer.echo(proposal.model_dump_json(indent=2))

@app.command()
def execute(run_id: str, approval_file: Path):
    approval = Approval.model_validate_json(approval_file.read_text())
    typer.echo(json.dumps(asyncio.run(agent.execute(run_id, approval)), indent=2, default=str))

@app.command()
def audit(run_id: str):
    typer.echo(json.dumps({"valid": agent.audit.verify(run_id),
                           "events": [e.model_dump(mode="json") for e in agent.audit.read(run_id)]}, indent=2))
