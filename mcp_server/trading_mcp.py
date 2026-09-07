"""FastMCP server exposing TradingDeskService (PRD Step 3 / AC-03).

Frozen v1 tool names (Product Design errata — not the aspirational catalog):
  get_market_snapshot
  get_technical_indicators
  get_macro_indicators
  analyze_ticker_parallel
  run_full_trade_desk

Wire keys for analysts: market | social | news | fundamentals
(``sentiment`` accepted as alias → ``social``).

Transports (Step 5):
  stdio (default) — local Cursor / Claude Desktop
  sse — HTTP+SSE for remote MCP clients (Grok Bot via Tailscale/SSH)
  streamable-http — FastMCP streamable HTTP endpoint

Env (DNS-rebinding allowlist for Funnel/Serve Host headers):
  MCP_ALLOWED_HOSTS — comma-separated hosts/patterns merged with localhost defaults
    e.g. MCP_ALLOWED_HOSTS=mac.tailbe8cfe.ts.net,mac.tailbe8cfe.ts.net:*
  MCP_ALLOWED_ORIGINS — optional comma-separated Origin patterns (https://host, https://host:*)
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from tradingagents.service.desk_service import TradingDeskService

V1_TOOL_NAMES: tuple[str, ...] = (
    "get_market_snapshot",
    "get_technical_indicators",
    "get_macro_indicators",
    "analyze_ticker_parallel",
    "run_full_trade_desk",
)

TransportName = Literal["stdio", "sse", "streamable-http"]

_DEFAULT_ALLOWED_HOSTS: list[str] = [
    "127.0.0.1:*",
    "localhost:*",
    "[::1]:*",
]
_DEFAULT_ALLOWED_ORIGINS: list[str] = [
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
]


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_transport_security(
    extra_hosts: list[str] | None = None,
    extra_origins: list[str] | None = None,
) -> TransportSecuritySettings:
    """Keep DNS-rebinding on; merge localhost defaults with env/extra hosts."""
    hosts = list(_DEFAULT_ALLOWED_HOSTS)
    for host in _split_csv(os.environ.get("MCP_ALLOWED_HOSTS")) + list(extra_hosts or []):
        if host not in hosts:
            hosts.append(host)

    origins = list(_DEFAULT_ALLOWED_ORIGINS)
    for origin in _split_csv(os.environ.get("MCP_ALLOWED_ORIGINS")) + list(
        extra_origins or []
    ):
        if origin not in origins:
            origins.append(origin)

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_mcp_server(
    service: TradingDeskService | None = None,
    *,
    name: str = "TradingAgents-Desk",
    host: str = "127.0.0.1",
    port: int = 8000,
    transport_security: TransportSecuritySettings | None = None,
) -> FastMCP:
    """Build a FastMCP app bound to a TradingDeskService instance.

    ``host`` defaults to loopback. Prefer Tailscale Serve / Funnel / SSH tunnel
    for remote clients rather than binding ``0.0.0.0`` without a network gate.
    """
    desk = service or TradingDeskService()
    security = transport_security or build_transport_security()
    server = FastMCP(
        name,
        host=host,
        port=port,
        transport_security=security,
    )

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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TradingAgents FastMCP server (stdio / sse / streamable-http)."
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport (default: stdio).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for sse/streamable-http (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port for sse/streamable-http (default: 8000).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    transport: TransportName = args.transport
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    server = create_mcp_server(host=args.host, port=args.port)
    if transport == "sse":
        print(
            f"TradingAgents MCP SSE listening on http://{args.host}:{args.port}/sse",
            flush=True,
        )
    else:
        print(
            f"TradingAgents MCP streamable-http listening on "
            f"http://{args.host}:{args.port}/mcp",
            flush=True,
        )
    server.run(transport=transport)


if __name__ == "__main__":
    main()
