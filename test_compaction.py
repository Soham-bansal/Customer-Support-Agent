from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from compaction import choose_cut

msgs = [HumanMessage(content="review C-02")]
msgs.append(AIMessage(content="", tool_calls=[
    {"name": "get_customer_orders", "args": {"customer_id": "C-02"}, "id": "c0"}]))
msgs.append(ToolMessage(content="orders...", tool_call_id="c0"))
msgs.append(AIMessage(content="", tool_calls=[
    {"name": "check_refund_eligibility", "args": {"order_id": f"O-100{i}"}, "id": f"c{i}"}
    for i in range(1, 6)]))
for i in range(1, 6):
    msgs.append(ToolMessage(content=f"decision {i}", tool_call_id=f"c{i}"))
msgs.append(AIMessage(content="Review summary..."))
msgs.append(HumanMessage(content="now refund O-1010"))
msgs.append(AIMessage(content="", tool_calls=[
    {"name": "issue_refund", "args": {"order_id": "O-1010"}, "id": "c9"}]))
msgs.append(ToolMessage(content="refunded", tool_call_id="c9"))

print("total messages:", len(msgs))
for n in (8, 5, 3):
    cut = choose_cut(msgs, n)
    kept = msgs[cut:]
    call_ids = {c["id"] for m in kept if isinstance(m, AIMessage) for c in m.tool_calls}
    orphans = [m for m in kept
               if isinstance(m, ToolMessage) and m.tool_call_id not in call_ids]
    print(f"summarize_first={n}: cut={cut}, first kept={type(msgs[cut]).__name__}, "
          f"orphan tool results={len(orphans)}")