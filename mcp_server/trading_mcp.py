"""FastMCP server exposing TradingDeskService (PRD Step 3 / AC-03).

Frozen v1 tool names (Product Design errata — not the aspirational catalog):
  get_market_snapshot
  get_technical_indicators
  get_macro_indicators
  analyze_ticker_parallel
  run_full_trade_desk

Wire keys for analysts: market | social | news | fundamentals
(``sentiment`` accepted as alias → ``social``).
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from tradingagents.service.desk_service import TradingDeskService

V1_TOOL_NAMES: tuple[str, ...] = (
    "get_market_snapshot",
    "get_technical_indicators",
    "get_macro_indicators",
    "analyze_ticker_parallel",
    "run_full_trade_desk",
)


def create_mcp_server(
    service: TradingDeskService | None = None,
    *,
    name: str = "TradingAgents-Desk",
) -> FastMCP:
    """Build a FastMCP app bound to a TradingDeskService instance."""
    desk = service or TradingDeskService()
    server = FastMCP(name)

    @server.tool(name="get_market_snapshot")
    def get_market_snapshot(
        ticker: str,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch OHLCV / range snapshot for a ticker (deterministic data, fail-open)."""
        return desk.get_market_snapshot(ticker, trade_date)

    @server.tool(name="get_technical_indicators")
    def get_technical_indicators(
        ticker: str,
        indicators: list[str] | None = None,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        """Exact technical indicators (RSI, MACD, SMAs, …); per-indicator fail-open."""
        return desk.get_technical_indicators(
            ticker, indicators=indicators, trade_date=trade_date
        )

    @server.tool(name="get_macro_indicators")
    def get_macro_indicators(
        trade_date: str | None = None,
        indicators: list[str] | None = None,
    ) -> dict[str, Any]:
        """US macro series from FRED (fail-open per series)."""
        return desk.get_macro_indicators(trade_date, indicators=indicators)

    @server.tool(name="analyze_ticker_parallel")
    async def analyze_ticker_parallel(
        ticker: str,
        analysts: list[str] | None = None,
        trade_date: str | None = None,
        asset_type: str = "stock",
    ) -> dict[str, Any]:
        """Run selected analysts concurrently.

        ``analysts`` wire keys: market, social, news, fundamentals
        (alias ``sentiment`` → ``social``). Returns per-analyst
        ``{ok, report?, error?}``.
        """
        return await desk.analyze_ticker_parallel(
            ticker,
            analysts=analysts,
            trade_date=trade_date,
            asset_type=asset_type,
        )

    @server.tool(name="run_full_trade_desk")
    def run_full_trade_desk(
        ticker: str,
        trade_date: str | None = None,
        asset_type: str = "stock",
    ) -> dict[str, Any]:
        """Run the full 11-agent desk; typed signal + thesis."""
        return desk.run_full_trade_desk(
            ticker, trade_date, asset_type=asset_type
        )

    return server


# Default stdio entrypoint instance (``python -m mcp_server.trading_mcp``).
mcp = create_mcp_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
