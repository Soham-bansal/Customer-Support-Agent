from dotenv import load_dotenv
import os
import json
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from state import AgentState
from hooks import pre_hook, post_hook, approval_decision
from utils import message_text
from langgraph.types import interrupt
from langchain_core.messages import RemoveMessage
from compaction import COMPACT_AT, SUMMARY_PROMPT, choose_cut, render,messages_to_fold
from audit import log_event

MAX_RETRIES = 3

load_dotenv()
provider = os.getenv("LLM_PROVIDER", "gemini")
if provider == "gemini":
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
else:
    from langchain_groq import ChatGroq
    llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)






SYSTEM_PROMPT = """You are a customer support copilot for an online shop. You help the shop owner or support staff.

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

Tool errors:
- If a tool returns status 400, read the error message, correct your input, and try again. Never repeat the same input.
- Only when a result says post_check_failed (never for rejected_by_human): do NOT call issue_refund again for that order. Call flag_for_review with the order ID 
and a short note that the refund could not be confirmed, then tell the user the refund status is unconfirmed 
and has been flagged for a person to check.


Human decisions:
- If a result says rejected_by_human, the refund was NOT issued and its status is known. This is not an error and not an unconfirmed result.
- Do not call issue_refund again for that order, and do not call flag_for_review unless the user asks.
- Tell the user clearly that no refund was issued, and repeat the reviewer's note.
- Then offer these options and wait for the user to choose: a smaller partial refund (suggest an amount only if the note supports it), a polite decline email to the customer, or flagging the order for review.
- Do not take any of these actions without the user's choice.:

Emails:
-Only send an email when the user asks.
-An email may only mention orders that belong to the recipient.

Answering:
- Keep answers short and clear.
- All amounts are in Indian rupees (₹).
- Answer only the user's latest request, and end with a short plain-text summary of what you found or did for that request.
- Never repeat or summarize the background notes about earlier messages.
"""


# mcp server tool exactly as in mcp , function repackages it into format model expects 
def to_llm_tool(t):
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.input_schema,
        },
    }

# helper function to decide if we should go to approval or end after reasoning
def should_continue(state: AgentState):
    last = state["messages"][-1]
    if last.tool_calls:
        return "approval"
    return END



def build_graph(session, mcp_tools,checkpointer):
    llm_with_tools = llm.bind_tools([to_llm_tool(t) for t in mcp_tools])

# helper function that call mcp server and get text of blocks and turn it into dict
    async def call_json(name, args):
        result = await session.call_tool(name, args)
        text = "\n".join(b.text for b in result.content if b.type == "text")
        return json.loads(text)

    async def fetch_order(order_id):
        return await call_json("get_order", {"order_id": order_id})

    async def fetch_eligibility(order_id):
        return await call_json("check_refund_eligibility", {"order_id": order_id})


    async def reasoning_node(state: AgentState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] 
        # labelling summary as notes
        if state.get("summary"):
            messages.append(HumanMessage(
                content="Background notes about earlier messages that were removed to save space. "
                        "These notes are NOT a question or a request, so do not reply to them, "
                        "repeat them or summarize them. Use them only as context, and answer the "
                        "user's latest request below.\n\n" + state["summary"]
            ))
        messages += state["messages"]
        response = await llm_with_tools.ainvoke(messages)

        # Guard: if the LLM returned nothing at all, ask once more
        if not response.tool_calls and not message_text(response).strip():
            nudge = HumanMessage(content="Please give your final answer in plain text.")
            response = await llm_with_tools.ainvoke(messages + [nudge])

        return {"messages": [response]}

    async def approval_node(state: AgentState):
        last = state["messages"][-1]
        approvals = {}

        for call in last.tool_calls:
            if call["name"] != "issue_refund":
                continue

            error, context = await pre_hook(call["name"], call["args"], fetch_order)
            if error:
                continue  # the tools node runs the pre-hook again and returns the 400

            order = context["order"]
            eligibility = await fetch_eligibility(order["order_id"])
            verdict = approval_decision(call["args"], eligibility)

            if verdict["action"] == "approve":
                answer = interrupt({
                    "order_id": order["order_id"],
                    "customer": order["customer_name"],
                    "amount": call["args"]["amount"],
                    "refund_reason": call["args"]["reason"],
                    "eligibility": eligibility.get("decision"),
                    "eligibility_reason": eligibility.get("reason"),
                    "why_approval": verdict["reason"],
                })
                verdict = {
                    **verdict,
                    "decision": answer["decision"],
                    "note": answer.get("note", ""),
                }

            approvals[call["id"]] = verdict

        return {"approvals": approvals}

    async def tool_node(state: AgentState):
        last = state["messages"][-1]
        approvals = state.get("approvals") or {}
        results = []
        failed = False

        for call in last.tool_calls:
            name, args = call["name"], call["args"]
            text = None
            verdict = None

            # PRE-HOOK: validate before anything runs
            error, context = await pre_hook(name, args, fetch_order)
            if error:
                failed = True
                print(f"[PRE-HOOK BLOCKED] {name} {args} -> {error['error']}")
                text = json.dumps(error, ensure_ascii=False)

            elif name == "issue_refund":
                verdict = approvals.get(call["id"])

                if verdict is None or verdict["action"] == "block":
                    reason = verdict["reason"] if verdict else "no approval record"
                    failed = True
                    print(f"[APPROVAL BLOCKED] {args} -> {reason}")
                    log_event("refund_blocked", args.get("order_id"), args.get("amount"),
                              args.get("reason"), "system", reason)
                    text = json.dumps(
                        {"status": 400, "error": f"Refund blocked: {reason}"},
                        ensure_ascii=False,
                    )

                elif verdict["action"] == "approve" and verdict["decision"] != "approve":
                    print(f"[REJECTED BY HUMAN] {args}")
                    log_event("refund_rejected", args.get("order_id"), args.get("amount"),
                              args.get("reason"), "human", verdict.get("note", ""))
                    text = json.dumps(
                        {
                            "status": "rejected_by_human",
                            "refund_issued": False,
                            "note": verdict.get("note") or "No reason given",
                            "message": (
                                "The human reviewer rejected this refund. No money was "
                                "moved. The refund status is known: NOT refunded. "
                                "Do not retry it and do not flag it."
                            ),
                        },
                        ensure_ascii=False,
                    )

            # Nothing stopped the call: run the tool through MCP (tools/call)
            if text is None:
                result = await session.call_tool(name, args)
                text = "\n".join(b.text for b in result.content if b.type == "text")

                # POST-HOOK: verify the outcome
                text = await post_hook(name, args, text, context, fetch_order)
                if "post_check_failed" in text:
                    failed = True

                if name == "issue_refund":
                    if "post_check_failed" in text:
                        log_event("refund_unconfirmed", args["order_id"], args["amount"],
                                  args["reason"], "system", "post-check mismatch")
                    else:
                        by = "human" if verdict and verdict["action"] == "approve" else "auto"
                        log_event("refund_issued", args["order_id"], args["amount"],
                                  args["reason"], by, (verdict or {}).get("note", ""))

            results.append(ToolMessage(content=text, tool_call_id=call["id"]))

        retries = state.get("retry_count", 0) + 1 if failed else 0
        return {"messages": results, "retry_count": retries}

    async def compact_node(state: AgentState):
        messages = state["messages"]
        if len(messages) <= COMPACT_AT:
            return {}

        old = messages_to_fold(messages)
        if not old:
            return {}

        previous = state.get("summary") or "(none)"
        prompt = f"Previous notes:\n{previous}\n\nMessages to fold in:\n{render(old)}"
        reply = await llm.ainvoke(
            [SystemMessage(content=SUMMARY_PROMPT), HumanMessage(content=prompt)]
        )

        print(f"[COMPACTED] {len(old)} messages folded into the summary")
        return {
            "summary": message_text(reply).strip(),
            "messages": [RemoveMessage(id=m.id) for m in old],
        }

    
    def give_up_node(state: AgentState):
        return {
            "messages": [
                AIMessage(
                    content=f"I stopped after {MAX_RETRIES} failed attempts. "
                    "Please check the request and try again."
                )
            ]
        }

    def after_tools(state: AgentState):
        if state.get("retry_count", 0) >= MAX_RETRIES:
            return "give_up"
        return "compact"

    builder = StateGraph(AgentState)
    builder.add_node("compact", compact_node)
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("approval", approval_node)
    builder.add_node("tools", tool_node)
    builder.add_node("give_up", give_up_node)
    builder.add_edge(START, "compact")
    builder.add_edge("compact", "reasoning")
    builder.add_conditional_edges("reasoning", should_continue, {"approval": "approval", END: END})
    builder.add_edge("approval", "tools")
    builder.add_conditional_edges(
        "tools", after_tools, {"compact": "compact", "give_up": "give_up"}
    )
    builder.add_edge("give_up", END)
    return builder.compile(checkpointer=checkpointer)