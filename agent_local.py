from dotenv import load_dotenv
import os
import json
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from state import AgentState
from langchain_core.tools import tool
from tools import (
    get_order,
    get_customer_orders,
    get_tracking,
    get_pending_refund_requests,
    check_refund_eligibility,
    issue_refund,
    flag_for_review,
    send_email,
)

load_dotenv()
llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)
provider = os.getenv("LLM_PROVIDER", "gemini")
if provider == "gemini":
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
else:
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

TOOLS = [
    tool(f)
    for f in [
        get_order,
        get_customer_orders,
        get_tracking,
        get_pending_refund_requests,
        check_refund_eligibility,
        issue_refund,
        flag_for_review,
        send_email,
    ]
]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


llm_with_tools = llm.bind_tools(TOOLS)



SYSTEM_PROMPT = """You are a refund triage copilot for an online shop. You help the shop owner or support staff.

Scope:
- You only help with orders, delivery status, and refunds.
- If the request is about anything else, politely refuse and offer to help with orders or refunds.

Lookups:
- Never guess order data. Always get it from tools.
- Look up an order with get_order before answering about it, unless you already have its full details from get_customer_orders.

Multi-order reviews:
- When asked to review several orders, first call get_customer_orders.
- Identify every order returned by get_customer_orders.
- Call check_refund_eligibility for EVERY order.
- Process orders one at a time.
- Do not finish the task until every order has been checked.
- Do not return an empty response.
- Only provide the final summary after all required orders have been checked.

Refund decisions:
- Before any refund decision, call check_refund_eligibility and follow its decision.
- eligible: the refund is allowed.
- borderline: the order is slightly past the return window. Say so and recommend a human decision.
- flag: the customer has too many recent refunds. Recommend flagging it for review.
- not_eligible: explain the reason clearly.
- Never call issue_refund when the decision is not_eligible or flag.

Answering:
- Keep answers short and clear.
- All amounts are in Indian rupees (₹).
- Finish every task with a plain-text summary of what you found or did.
"""



def reasoning_node(state: AgentState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def tool_node(state: AgentState):
    last = state["messages"][-1]
    results = []
    for call in last.tool_calls:
        t = TOOLS_BY_NAME[call["name"]]
        output = t.invoke(call["args"])
        results.append(
            ToolMessage(content=json.dumps(output, default=str), tool_call_id=call["id"])
        )
    return {"messages": results}

def should_continue(state: AgentState):
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return END

builder = StateGraph(AgentState)
builder.add_node("reasoning", reasoning_node)
builder.add_node("tools", tool_node)
builder.add_edge(START, "reasoning")
builder.add_conditional_edges("reasoning", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "reasoning")
graph = builder.compile()