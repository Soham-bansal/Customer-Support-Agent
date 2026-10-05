import shutil
from pathlib import Path

PROJECT = Path(__file__).parent
DATA = PROJECT / "data"

# Restore the orders to their original state
shutil.copy(DATA / "orders.original.json", DATA / "orders.json")

# Remove files created by test runs
(DATA / "flagged_cases.json").unlink(missing_ok=True)
(PROJECT / "audit_log.json").unlink(missing_ok=True)

# Remove saved conversations (SQLite may also create -wal and -shm helper files)
for name in ("checkpoints.db", "checkpoints.db-wal", "checkpoints.db-shm"):
    (PROJECT / name).unlink(missing_ok=True)

print("Reset done: orders restored, flags, audit log and saved conversations cleared.")