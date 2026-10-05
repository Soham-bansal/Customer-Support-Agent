from mcp.server.mcpserver import MCPServer
import tools

mcp = MCPServer("refund-tools")
mcp.tool()(tools.get_order)
mcp.tool()(tools.get_customer_orders)
mcp.tool()(tools.get_tracking)
mcp.tool()(tools.get_pending_refund_requests)
mcp.tool()(tools.check_refund_eligibility)
mcp.tool()(tools.issue_refund)
mcp.tool()(tools.flag_for_review)
mcp.tool()(tools.send_email)

if __name__ == "__main__":
    mcp.run(transport="stdio")