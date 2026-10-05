from langchain_core.messages import HumanMessage
from agent import graph
from utils import message_text

question = "Review all orders for customer C-02 and tell me which are refundable"

result = graph.invoke({
    "messages": [HumanMessage(content=question)]
})

# Print the complete conversation / agent execution
for m in result["messages"]:
    kind = type(m).__name__

    if kind == "AIMessage" and getattr(m, "tool_calls", None):
        print(
            kind,
            "-> tool call:",
            [(c["name"], c["args"]) for c in m.tool_calls]
        )
    elif kind == "ToolMessage":
        print(kind, ":", message_text(m)[:150], "...")
    else:
        print(kind, ":", message_text(m))

# Final answer, as clean text
last = result["messages"][-1]

print("\n--- Final Answer ---")
print(message_text(last))

print("\n--- Tool Calls (should be empty) ---")
print(getattr(last, "tool_calls", []))

print("\n--- Response Metadata ---")
print(getattr(last, "response_metadata", {}))