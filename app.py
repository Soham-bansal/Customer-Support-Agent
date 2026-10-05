import os
import sys
import json
import uuid
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agent import build_graph
from run_agent import make_callbacks, flush_traces
from utils import message_text

load_dotenv()

DB_FILE = "checkpoints.db"
PAGE = Path(__file__).parent / "static" / "index.html"
params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])

shared = {}   # holds the graph and a lock, created once at startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the MCP tool server and the saver once, and keep them open while the API runs.
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            async with AsyncSqliteSaver.from_conn_string(DB_FILE) as saver:
                shared["graph"] = build_graph(session, listed.tools, saver)
                shared["lock"] = asyncio.Lock()
                yield
    flush_traces()


app = FastAPI(title="Refund Support Copilot", lifespan=lifespan)


def make_config(thread_id: str):
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": make_callbacks(),
        "metadata": {"langfuse_session_id": thread_id},
    }


def steps_from(update):
    """Turn one graph step into entries the chat page can show."""
    steps = []
    if not update:
        return steps
    for m in update.get("messages", []):
        kind = type(m).__name__
        if kind == "RemoveMessage":
            continue
        if kind == "AIMessage" and getattr(m, "tool_calls", None):
            for c in m.tool_calls:
                args = json.dumps(c["args"], ensure_ascii=False)
                steps.append({"type": "tool_call", "text": f"{c['name']}({args})"})
        elif kind == "ToolMessage":
            steps.append({"type": "tool_result", "text": message_text(m)[:400]})
        elif kind == "AIMessage":
            steps.append({"type": "agent", "text": message_text(m)})
    if update.get("summary"):
        steps.append({"type": "note", "text": "Older messages were summarized to save space."})
    return steps


async def run(payload, thread_id: str):
    config = make_config(thread_id)
    steps = []
    pending = None
    try:
        async with shared["lock"]:   # one run at a time keeps the shared tool connection safe
            async for chunk in shared["graph"].astream(payload, config, stream_mode="updates"):
                for node, update in chunk.items():
                    if node == "__interrupt__":
                        pending = update
                    else:
                        steps += steps_from(update)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    finally:
        flush_traces()

    if pending:
        return {
            "status": "waiting_for_approval",
            "thread_id": thread_id,
            "approval_request": pending[0].value,
            "steps": steps,
        }

    replies = [s["text"] for s in steps if s["type"] == "agent"]
    return {
        "status": "done",
        "thread_id": thread_id,
        "reply": replies[-1] if replies else "",
        "steps": steps,
    }


class WebhookRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ApproveRequest(BaseModel):
    thread_id: str
    decision: str          # "approve" or "reject"
    note: str = ""


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(PAGE)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(req: WebhookRequest):
    thread_id = req.thread_id or str(uuid.uuid4())

    snapshot = await shared["graph"].aget_state(make_config(thread_id))
    if snapshot.next:
        raise HTTPException(
            status_code=409,
            detail="This conversation is waiting for approval. Call /approve first.",
        )

    return await run({"messages": [HumanMessage(content=req.message)]}, thread_id)


@app.post("/approve")
async def approve(req: ApproveRequest):
    if req.decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    snapshot = await shared["graph"].aget_state(make_config(req.thread_id))
    if not snapshot.next:
        raise HTTPException(status_code=409, detail="No approval is pending for this thread_id.")

    answer = {"decision": req.decision, "note": req.note}
    return await run(Command(resume=answer), req.thread_id)