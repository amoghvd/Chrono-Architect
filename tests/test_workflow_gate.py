from datetime import UTC, datetime, timedelta

import pytest
from test_policy import make_proposal

from chrono_architect.config import Settings
from chrono_architect.mcp_gateway import RecordingGateway
from chrono_architect.models import Approval
from chrono_architect.policy import PolicyViolation
from chrono_architect.workflow import ChronoArchitect


@pytest.mark.asyncio
async def test_no_read_recheck_or_mutation_before_valid_approval(tmp_path):
    read = RecordingGateway({})
    write = RecordingGateway({})
    agent = ChronoArchitect(read, write, Settings(audit_dir=tmp_path))
    proposal = make_proposal()
    agent.store.save(proposal)
    now = datetime.now(UTC)
    wrong = Approval(
        decision="approve",
        proposal_hash="0" * 64,
        approver="mallory",
        approved_at=now,
        expires_at=min(now + timedelta(minutes=1), proposal.expires_at),
    )
    with pytest.raises(PolicyViolation):
        await agent.execute(proposal.run_id, wrong)
    assert read.commands == []
    assert write.commands == []
