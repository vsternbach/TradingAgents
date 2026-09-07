# TradingAgents MCP — SSE / HTTP (remote clients)

Frozen tool surface is unchanged from stdio (see `docs/MCP-stdio.md`):

`get_market_snapshot` · `get_technical_indicators` · `get_macro_indicators` ·
`analyze_ticker_parallel` · `run_full_trade_desk`

## Run locally (SSE)

From the repo root (venv with `mcp[cli]>=1.9,<2`):

```bash
python -m mcp_server.trading_mcp --transport sse --host 127.0.0.1 --port 8000
```

Endpoints (FastMCP defaults):

| Transport | URL |
|---|---|
| SSE | `http://127.0.0.1:8000/sse` |
| Messages (SSE POST) | `http://127.0.0.1:8000/messages/` |
| Streamable HTTP | `http://127.0.0.1:8000/mcp` |

Streamable HTTP alternative:

```bash
python -m mcp_server.trading_mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

**Default bind is loopback.** Do not expose `0.0.0.0` on the public internet
without your own gate (Tailscale / SSH). No auth layer ships in v1.

## Attach from Cursor / Grok Bot (`AddMcpServer`)

Remote MCP clients that take a URL (Cursor `AddMcpServer` `url` field, Grok Bot
connector):

- **Same machine:** `http://127.0.0.1:8000/sse`
- **Grok Bot on another host:** publish the SSE URL via Tailscale Serve or an
  SSH tunnel (preferred), then paste that HTTPS/HTTP URL into AddMcpServer.

Example AddMcpServer shape:

- `name`: `tradingagents`
- `url`: `http://127.0.0.1:8000/sse` (or your Tailscale Serve URL)

Stdio remains available for local plugin installs (`python -m mcp_server.trading_mcp`).

## Reach Grok Bot from your Mac (Tailscale / SSH)

Preferred patterns (keep FastMCP bound to `127.0.0.1`):

1. **SSH tunnel** from the Grok Bot machine to your Mac:
   `ssh -L 8000:127.0.0.1:8000 user@mac` then attach `http://127.0.0.1:8000/sse`.
2. **Tailscale Serve** on the Mac, serving local port 8000, then use the Serve
   URL as the AddMcpServer `url`.

DNS-rebinding protection in FastMCP allows `127.0.0.1` / `localhost` by default.
If you bind a Tailscale IP / MagicDNS hostname directly, you may need to widen
`transport_security` — prefer Serve/tunnel instead.

## Smoke test

```bash
pytest tests/test_mcp_sse.py -m integration
```

Asserts an SSE server starts and `tools/list` returns the five frozen names.
