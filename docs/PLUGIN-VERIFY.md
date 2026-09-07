# PLUGIN-VERIFY — tradingagents-desk Agent Plugin

Date: 2026-09-07 (Asia/Jerusalem)
Repo: `/Users/vlad/Projects/TradingAgents` @ `feat/modular-orchestrator-mcp` / `6dcf3bf`
Format: Agent Plugins 1.0.0 (root `plugin.json`, not `.cursor-plugin/`)

## Results

| Gate | Result | Notes |
|---|---|---|
| Schema-validate `plugin.json` | **PASS** | vs agent-plugins.org 1.0.0 plugin.schema.json (jsonschema) |
| Schema-validate `mcp.json` | **PASS** | vs agent-plugins.org 1.0.0 mcp.schema.json |
| MCP stdio `tools/list` (five frozen names) | **PASS** | Engineer harness + thin-install wrapper |
| Local install real directory | **PASS** | `~/.cursor/plugins/local/tradingagents-desk` (copy, not outside symlink) |
| `@anysphere/cursor-plugins` `loadUserLocalPlugins` | **SKIP** | Not used in this prove; load via Cursor IDE Reload Window |
| Grok Bot loads local plugins | **N/A** | Cursor IDE only |

## Absolute paths (repo)

- `/Users/vlad/Projects/TradingAgents/plugin.json`
- `/Users/vlad/Projects/TradingAgents/mcp.json`
- `/Users/vlad/Projects/TradingAgents/bin/run-trading-mcp`
- `/Users/vlad/Projects/TradingAgents/skills/tradingagents-desk/SKILL.md`
- `/Users/vlad/Projects/TradingAgents/docs/PLUGIN-LOCAL.md`
- `/Users/vlad/Projects/TradingAgents/docs/PLUGIN-VERIFY.md`
- Engineer stdio guide: `/Users/vlad/Projects/TradingAgents/docs/MCP-stdio.md`

## Local install path

`/Users/vlad/.cursor/plugins/local/tradingagents-desk/` with real copies of `plugin.json`, `mcp.json`, `bin/run-trading-mcp`, `skills/tradingagents-desk/SKILL.md`.

## Exact tools/list names

```
get_market_snapshot
get_technical_indicators
get_macro_indicators
analyze_ticker_parallel
run_full_trade_desk
```

## Prove commands run

```bash
# Schema PASS
.venv/bin/python  # jsonschema validate plugin.json + mcp.json

# Engineer MCP stdio E2E PASS — see docs/MCP-stdio.md
.venv/bin/python scripts/e2e_mcp_stdio.py --json
# optional: pytest tests/test_e2e_mcp_stdio.py -m integration

# Thin-install wrapper initialize + tools/list PASS
```

E2E (`ok: true`): tools_list as above; `get_market_snapshot` / `get_macro_indicators` called (macro fail-open without FRED_API_KEY is OK). Live analyze/desk skipped (need LLM keys); unit fakes per docs/MCP-stdio.md.

## How Vlad installs / proves in Cursor IDE

1. Ambient env (or wrapper Vlad defaults):

```bash
export TRADINGAGENTS_ROOT=/Users/vlad/Projects/TradingAgents
export TRADINGAGENTS_PYTHON=/Users/vlad/Projects/TradingAgents/.venv/bin/python
```

2. Refresh local copy (no outside symlink):

```bash
mkdir -p ~/.cursor/plugins/local/tradingagents-desk
cp plugin.json mcp.json ~/.cursor/plugins/local/tradingagents-desk/
cp -R skills bin ~/.cursor/plugins/local/tradingagents-desk/
chmod +x ~/.cursor/plugins/local/tradingagents-desk/bin/run-trading-mcp
```

3. Cursor: Developer: Reload Window — verify Plugins/MCP `tradingagents-desk` and the five tools.

4. Re-prove: `python scripts/e2e_mcp_stdio.py --json` (docs/MCP-stdio.md).

## Gaps / design notes

1. **No portable `variables` on Agent Plugins 1.0.0** — root plugin.json schema is closed. Cursor dashboard variables need a Cursor Plugin (`.cursor-plugin/plugin.json`). This wrap stays AP-conformant and uses ambient `TRADINGAGENTS_ROOT` / `TRADINGAGENTS_PYTHON` (wrapper defaults for Vlad Mac).
2. **mcp.json cannot use `${TRADINGAGENTS_ROOT}` as cwd** — AP 1.0.0 only allows `./…`, `${PLUGIN_ROOT}`, `${PLUGIN_DATA}`. Launch is `./bin/run-trading-mcp` + `cwd: ${PLUGIN_ROOT}`.
3. Macro without FRED key — fail-open; not a plugin failure.
4. loadUserLocalPlugins — skipped; use IDE reload.
5. Files left **uncommitted** (do not publish).

## Related

- Install: `docs/PLUGIN-LOCAL.md`
- Stdio + E2E: `docs/MCP-stdio.md`
