# TradingAgents MCP — stdio attach (v1)

Frozen FastMCP tool surface from Step 3 (`mcp_server/trading_mcp.py`):

| Tool | Tier |
|---|---|
| `get_market_snapshot` | data |
| `get_technical_indicators` | data |
| `get_macro_indicators` | data |
| `analyze_ticker_parallel` | parallel analysts |
| `run_full_trade_desk` | full desk |

Wire keys for analysts: `market | social | news | fundamentals` (`sentiment` → `social`).

## Run the server (stdio)

From the repo root (venv with `tradingagents[mcp]` / `mcp[cli]>=1.9,<2`):

```bash
python -m mcp_server.trading_mcp
```

## Attach from Cursor / Claude / Codex-style clients

Point an MCP stdio client at the same command. Example Cursor MCP config fragment:

```json
{
  "mcpServers": {
    "tradingagents": {
      "command": "/ABS/PATH/TO/TradingAgents/.venv/bin/python",
      "args": ["-m", "mcp_server.trading_mcp"],
      "cwd": "/ABS/PATH/TO/TradingAgents"
    }
  }
}
```

Grok / Codex / other agent hosts: same pattern — spawn the command over stdio, then `tools/list` / `tools/call`.

## E2E harness

```bash
python scripts/e2e_mcp_stdio.py --json
pytest tests/test_e2e_mcp_stdio.py -m integration
```

The harness asserts `tools/list` matches the five frozen names and calls
`get_market_snapshot` + `get_macro_indicators` (fail-open structured JSON is OK
without FRED keys). Live `analyze_ticker_parallel` / `run_full_trade_desk` need
LLM provider API keys; those paths are covered by unit fakes in
`tests/test_trading_mcp.py` and `tests/test_desk_service.py`.
