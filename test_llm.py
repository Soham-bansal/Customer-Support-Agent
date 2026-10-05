from langchain_core.messages import HumanMessage
from agent import graph

questions = [
    "What is the capital of France?",
    "Where is my order O-1006?",
    "Is O-1002 still refundable?",
    "Refund O-1002, it arrived damaged.",
]

for question in questions:
    result = graph.invoke({"messages": [HumanMessage(content=question)]})
    last = result["messages"][-1]
    print("Q:", question)
    print("Text:", last.content)
    print("Tool calls:", last.tool_calls)
    print()