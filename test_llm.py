from langchain_core.messages import HumanMessage
from agent_local import  graph
questions = [
    "What is the capital of France?",
    "Where is my order O-1006?",
    "Is O-1002 still refundable?",
    "Refund O-1002, it arrived damaged.",
]

for question in questions:

    result = graph.invoke({
        "messages": [HumanMessage(content=question)]
    })

    print("\n" + "=" * 80)
    print("Q:", question)
    print("=" * 80)

    for msg in result["messages"]:

        print("\nMESSAGE TYPE:", type(msg).__name__)
        print("CONTENT:", msg.content)

        if hasattr(msg, "tool_calls"):
            print("TOOL CALLS:", msg.tool_calls)