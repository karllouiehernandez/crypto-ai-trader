"""FastMCP server — registers all tools and exposes stdio and SSE transports."""
from mcp.server.fastmcp import FastMCP
from mcp_server import tools

mcp = FastMCP(
    name="crypto-trader",
    instructions=(
        "Query a live crypto paper-trading system. "
        "Read tools return live data from SQLite. "
        "Write tools (run_backtest, save_backtest_preset) require MCP_ALLOW_WRITES=true in .env."
    ),
)

# read tools
mcp.tool()(tools.get_system_status)
mcp.tool()(tools.get_trade_history)
mcp.tool()(tools.get_portfolio_equity)
mcp.tool()(tools.get_backtest_runs)
mcp.tool()(tools.get_backtest_run_detail)
mcp.tool()(tools.get_strategy_catalog)
mcp.tool()(tools.get_market_focus)
mcp.tool()(tools.get_promotions)
mcp.tool()(tools.list_kb_files)
mcp.tool()(tools.read_kb_file)

# write tools (gated)
mcp.tool()(tools.run_backtest)
mcp.tool()(tools.save_backtest_preset)
