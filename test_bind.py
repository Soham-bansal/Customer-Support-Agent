from agent import TOOLS

for t in TOOLS:
    print(t.name, "|", t.description)
    print("   args:", t.args)