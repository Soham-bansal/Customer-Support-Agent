from langchain_core.messages import HumanMessage
from agent_local import graph

questions = ["What is the capital of France?", "Where is my order O-1006?"]

for question in questions:
    result = graph.invoke({"messages": [HumanMessage(content=question)]})
    print("Q:", question)
    print("A:", result["messages"][-1].content)
    print()