import asyncio
import json
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.memory import InMemorySaver
from agent import build_graph
from run_agent import make_callbacks, flush_traces
from scenarios import SCENARIOS
from utils import message_text

load_dotenv()

PROJECT = Path(__file__).parent
DATA = PROJECT / "data"
TRACES = PROJECT / "eval_traces"
TRACES.mkdir(exist_ok=True)

params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])


def reset_data():
    shutil.copy(DATA / "orders.original.json", DATA / "orders.json")
    (DATA / "flagged_cases.json").unlink(missing_ok=True)
    (PROJECT / "audit_log.json").unlink(missing_ok=True)


def to_lines(update):
    """Turn one graph step into readable transcript lines."""
    lines = []
    if not update:          # steps with nothing to change report None
        return lines
    for m in update.get("messages", []):
        kind = type(m).__name__
        if kind == "RemoveMessage":
            continue
        if kind == "AIMessage" and getattr(m, "tool_calls", None):
            calls = ", ".join(f"{c['name']}({c['args']})" for c in m.tool_calls)
            lines.append(f"AGENT REQUESTED TOOL: {calls}")
        elif kind == "ToolMessage":
            lines.append(f"TOOL RESULT: {message_text(m)[:500]}")
        else:
            lines.append(f"AGENT: {message_text(m)}")
    return lines


async def run_one(session, tools, sc):
    reset_data()
    graph = build_graph(session, tools, InMemorySaver())
    config = {
        "configurable": {"thread_id": f"eval-{sc['id']}"},
        "callbacks": make_callbacks(),
        "metadata": {"langfuse_session_id": f"eval-{sc['id']}"},
    }

    transcript = [f"USER: {sc['question']}"]
    payload = {"messages": [HumanMessage(content=sc["question"])]}
    pauses = 0

    while True:
        pending = None
        async for chunk in graph.astream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    pending = update
                else:
                    transcript += to_lines(update)

        if not pending:
            break

        pauses += 1
        info = pending[0].value
        answer = sc["approval"] or {"decision": "reject", "note": "no approval configured"}
        transcript.append(
            f"HUMAN APPROVAL REQUESTED: refund of Rs {info['amount']} on {info['order_id']} "
            f"({info['why_approval']}). HUMAN ANSWERED: {answer['decision']} {answer['note']}"
        )
        payload = Command(resume=answer)

    return {
        "id": sc["id"],
        "name": sc["name"],
        "question": sc["question"],
        "approval_pauses": pauses,
        "transcript": transcript,
    }


async def main():
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()

            for sc in SCENARIOS:
                out = TRACES / f"scenario_{sc['id']:02d}.json"
                if out.exists():
                    print(f"Scenario {sc['id']}: already saved, skipping")
                    continue
                print(f"Scenario {sc['id']}: {sc['name']} ...")
                try:
                    result = await run_one(session, listed.tools, sc)
                    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"   saved ({len(result['transcript'])} lines, {result['approval_pauses']} pause(s))")
                except Exception as e:
                    print(f"   FAILED: {type(e).__name__}: {e}")
                await asyncio.sleep(2)

    reset_data()
    flush_traces()
    print("\nDone. Transcripts are in the eval_traces folder.")


if __name__ == "__main__":
    asyncio.run(main())