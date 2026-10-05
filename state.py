from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    tickets: list[dict]
    processed: dict[str, str]
    current_ticket: dict | None
    pending_action: dict | None
    approval_status: str
    approvals: dict
    rejection_reason: str | None
    retry_count: int
    summary: str