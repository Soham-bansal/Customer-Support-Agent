import os
import asyncio
import sys
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agent import build_graph
from utils import message_text

load_dotenv()

params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])

TOOL_PREVIEW = 300   # how many characters of each tool result to show
DB_FILE = "checkpoints.db"


def make_callbacks():
    """Langfuse tracing, switched on only if the keys are in .env."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        from langfuse.langchain import CallbackHandler
        print("Langfuse tracing: ON")
        return [CallbackHandler()]
    print("Langfuse tracing: OFF (keys not found in .env)")
    return []


def flush_traces():
    """Send any traces still waiting to be uploaded."""
    if os.getenv("LANGFUSE_PUBLIC_KEY"):
        from langfuse import get_client
        get_client().flush()


async def ask_human(info: dict) -> dict:
    print("\n" + "=" * 44)
    print(" HUMAN APPROVAL REQUIRED")
    print("=" * 44)
    print(f"Order:         {info['order_id']} ({info['customer']})")
    print(f"Amount:        ₹{info['amount']}")
    print(f"Refund reason: {info['refund_reason']}")
    print(f"Eligibility:   {info['eligibility']} - {info['eligibility_reason']}")
    print(f"Why approval:  {info['why_approval']}")

    while True:
        choice = (
            await asyncio.to_thread(input, "Approve or Reject? [a/r]: ")
        ).strip().lower()
        if choice in ("a", "approve"):
            return {"decision": "approve", "note": ""}
        if choice in ("r", "reject"):
            note = await asyncio.to_thread(input, "Reason for rejecting: ")
            return {"decision": "reject", "note": note.strip()}
        print("Please type a or r.")


def show_update(update):
    """Print what one graph step produced."""
    if not update:
        return

    if update.get("summary"):
        print("\n[SUMMARY NOW]", update["summary"], "\n")

    for m in update.get("messages", []):
        kind = type(m).__name__
        if kind == "RemoveMessage":
            continue
        if kind == "AIMessage" and getattr(m, "tool_calls", None):
            print("AIMessage -> tool call:", [(c["name"], c["args"]) for c in m.tool_calls])
        elif kind == "ToolMessage":
            print("ToolMessage :", message_text(m)[:TOOL_PREVIEW].replace("\n", " "), "...")
        else:
            print("\nAIMessage :", message_text(m))


async def chat():
    # Same thread name = same conversation, even after a restart.
    thread = sys.argv[1] if len(sys.argv) > 1 else "support-chat-1"

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            print("Discovered tools:", [t.name for t in listed.tools])

            async with AsyncSqliteSaver.from_conn_string(DB_FILE) as saver:
                graph = build_graph(session, listed.tools, saver)
                config = {
                    "configurable": {"thread_id": thread},
                    "callbacks": make_callbacks(),
                    "metadata": {"langfuse_session_id": thread},
                }
                print(f"Refund copilot ready (conversation '{thread}'). Type 'exit' to quit.")

                while True:
                    question = (await asyncio.to_thread(input, "\nYou: ")).strip()
                    if question.lower() in ("exit", "quit"):
                        break
                    if not question:
                        continue

                    payload = {"messages": [HumanMessage(content=question)]}

                    # Stream each step live. If the graph pauses, ask, then resume.
                    while True:
                        pending = None
                        async for chunk in graph.astream(payload, config, stream_mode="updates"):
                            for node, update in chunk.items():
                                if node == "__interrupt__":
                                    pending = update
                                else:
                                    show_update(update)

                        if not pending:
                            break
                        answer = await ask_human(pending[0].value)
                        payload = Command(resume=answer)

                    flush_traces()


if __name__ == "__main__":
    try:
        asyncio.run(chat())
    finally:
        flush_traces()