"""TradingAgents Model Context Protocol (MCP) server package.

Keep this module import-light so ``python -m mcp_server.trading_mcp`` does not
double-load the FastMCP entrypoint via package ``__init__``.
"""

V1_TOOL_NAMES: tuple[str, ...] = (
    "get_market_snapshot",
    "get_technical_indicators",
    "get_macro_indicators",
    "analyze_ticker_parallel",
    "run_full_trade_desk",
)

__all__ = ["V1_TOOL_NAMES", "create_mcp_server", "mcp"]


def __getattr__(name: str):
    if name in {"create_mcp_server", "mcp"}:
        from .trading_mcp import create_mcp_server, mcp

        return {"create_mcp_server": create_mcp_server, "mcp": mcp}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
