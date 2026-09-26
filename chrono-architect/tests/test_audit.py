from chrono_architect.audit import AuditLog
from chrono_architect.models import RunState


def test_hash_chained_audit_detects_tampering(tmp_path):
    log = AuditLog(tmp_path)
    log.append("r1", "start", state=RunState.INVESTIGATING)
    log.append("r1", "proposal", {"x": 1}, RunState.AWAITING_APPROVAL)
    assert log.verify("r1")
    path = tmp_path / "r1.jsonl"
    path.write_text(path.read_text().replace('"x":1', '"x":2'))
    assert not log.verify("r1")
