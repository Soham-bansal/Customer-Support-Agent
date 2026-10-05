from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from utils import message_text

COMPACT_AT = 10        # compact when there are more than this many messages
SUMMARIZE_FIRST = 8   # how many of the oldest messages to fold into the summary

SUMMARY_PROMPT = """You are compressing the history of a refund support conversation so the work can continue.
Write one short paragraph. Keep: order IDs, customer IDs, amounts in rupees, eligibility decisions, refunds issued or rejected (with the reviewer's note), orders flagged, emails sent, and anything the user still expects.
Drop greetings and raw data fields that no longer matter.
Do not invent anything. Only state facts that appear in the messages. Do not mention missing information or what the user might need next."""


def choose_cut(messages, summarize_first=SUMMARIZE_FIRST):
    """Index where the kept part starts, or None if it is not safe to compact."""
    cut = summarize_first
    while cut < len(messages) and isinstance(messages[cut], ToolMessage):
        cut += 1
    if cut >= len(messages):
        return None
    return cut


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