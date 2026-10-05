import json
from datetime import datetime
from pathlib import Path

AUDIT_FILE = Path(__file__).parent / "audit_log.json"


def log_event(event, order_id, amount, reason, decided_by, note=""):
    entries = []
    if AUDIT_FILE.exists():
        entries = json.loads(AUDIT_FILE.read_text(encoding="utf-8"))
    entries.append(
        {
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "decided_by": decided_by,
            "note": note,
        }
    )
    AUDIT_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )