---
name: tradingagents-desk
description: >-
  Use when the user wants market data, technicals, macro series, parallel
  analyst research, or a full multi-agent trade-desk run via TradingAgents
  MCP. Call only the five frozen tools listed below; never invent tickers,
  prices, sample payloads, or extra APIs.
---

# TradingAgents Desk (MCP)

Domain surface: **TradeDeskSurface** — ticker-scoped tools returning typed
dicts. Data tools fail-open. Parallel analysts use wire keys
`market | social | news | fundamentals` (`sentiment` → `social` alias) with
per-analyst `{ok, report?, error?}`.

## When to call which tool

| Tool | When |
|---|---|
| `get_market_snapshot` | OHLCV / range snapshot for a ticker (deterministic data). |
| `get_technical_indicators` | Exact indicators (RSI, MACD, SMAs, …); per-indicator fail-open. |
| `get_macro_indicators` | US macro series (FRED); fail-open per series. |
| `analyze_ticker_parallel` | Concurrent analyst reports for selected wire keys. |
| `run_full_trade_desk` | Full 11-agent desk → typed signal + thesis (needs LLM keys). |

## Frozen v1 tool names (exact)

1. `get_market_snapshot`
2. `get_technical_indicators`
3. `get_macro_indicators`
4. `analyze_ticker_parallel`
5. `run_full_trade_desk`

Do not invent tool names, arguments, or sample market data. Prefer live
`tools/list` / `tools/call` over guessing schemas. See `docs/MCP-stdio.md`
for stdio attach and E2E prove commands.
