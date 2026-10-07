import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


params = StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
)


async def main():

    async with stdio_client(params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            result = await session.list_tools()

            print("\n")
            print("=" * 80)
            print("                 MCP SERVER — AVAILABLE TOOLS")
            print("=" * 80)

            for i, tool in enumerate(result.tools, 1):

                print(f"\n{i}. {tool.name}")

                print(f"   Purpose: {tool.description}")

                # Get arguments from MCP schema
                properties = tool.input_schema.get("properties", {})

                if properties:
                    arguments = ", ".join(properties.keys())
                    print(f"   Arguments: {arguments}")
                else:
                    print("   Arguments: None")

            print("\n")
            print("=" * 80)
            print(f"Total Tools: {len(result.tools)}")
            print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())