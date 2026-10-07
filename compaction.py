from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from utils import message_text

COMPACT_AT = 6        # compact when there are more than this many messages
SUMMARIZE_FIRST = 4    # how many of the oldest messages to fold into the summary


SUMMARY_PROMPT = """You are writing background notes about an earlier part of a customer support conversation, so the work can continue.
Write one short paragraph of facts. Keep: order IDs, customer IDs, amounts in rupees, eligibility decisions, refunds issued (with the reason given), refunds rejected by a person (with the reviewer's note), orders flagged, and emails sent.
Only state facts that appear in the messages. Do not write questions, instructions or a reply to the user.
Do not invent anything."""


def choose_cut(messages, summarize_first=SUMMARIZE_FIRST):
    """Index where the kept part starts, or None if it is not safe to compact."""
    cut = summarize_first
    while cut < len(messages) and isinstance(messages[cut], ToolMessage):
        cut += 1
    if cut >= len(messages):
        return None
    return cut


def messages_to_fold(messages):
    """The messages to summarize and remove.
    The user's latest request is never included, so the model always sees what it must answer."""
    cut = choose_cut(messages)
    if cut is None:
        return []
    latest = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=None)
    return [m for i, m in enumerate(messages[:cut]) if i != latest]


def render(messages):
    """Turn messages into plain text for the summarizer."""
    lines = []
    for m in messages:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {message_text(m)}")
        elif isinstance(m, AIMessage):
            if m.tool_calls:
                calls = ", ".join(f"{c['name']}({c['args']})" for c in m.tool_calls)
                lines.append(f"Agent requested: {calls}")
            else:
                lines.append(f"Agent: {message_text(m)}")
        elif isinstance(m, ToolMessage):
            lines.append(f"Tool result: {message_text(m)[:600]}")
    return "\n".join(lines)