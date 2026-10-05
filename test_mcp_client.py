import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])


async def main():
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            for t in listed.tools:
                print(t.name, "|", t.description[:60])
                print("   schema:", t.input_schema)

            result = await session.call_tool("get_order", {"order_id": "O-1006"})
            print("\nCall result:", result.content)


asyncio.run(main())