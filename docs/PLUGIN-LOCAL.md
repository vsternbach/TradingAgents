# TradingAgents Desk — local Agent Plugin

Minimal Agent Plugins 1.0.0 wrap around `mcp_server/trading_mcp.py`
(`TradeDeskSurface`). Does **not** publish; keep uncommitted until you choose
to commit.

## Layout (repo root)

```text
plugin.json
mcp.json
bin/run-trading-mcp
skills/tradingagents-desk/SKILL.md
docs/PLUGIN-LOCAL.md
docs/PLUGIN-VERIFY.md
docs/MCP-stdio.md          # Engineer stdio attach + E2E harness
```

## Why a wrapper (not `${TRADINGAGENTS_*}` in mcp.json)

Agent Plugins 1.0.0 only expands `${PLUGIN_ROOT}` / `${PLUGIN_DATA}` in
`args` / `env` / `cwd`. `cwd` must be `./…`, `${PLUGIN_ROOT}`, or
`${PLUGIN_DATA}`. `command` is a bare name or `./…` with **no** placeholder
expansion. There is no portable `variables` field on root `plugin.json`
(that exists on Cursor Plugins under `.cursor-plugin/plugin.json`).

So `mcp.json` launches `./bin/run-trading-mcp` with `cwd: ${PLUGIN_ROOT}`.
The script resolves the real repo via ambient env (or Vlad defaults).

## Defaults (Vlad Mac)

| Variable | Default |
|---|---|
| `TRADINGAGENTS_ROOT` | `/Users/vlad/Projects/TradingAgents` |
| `TRADINGAGENTS_PYTHON` | `$TRADINGAGENTS_ROOT/.venv/bin/python` |

Export before starting Cursor if your layout differs:

```bash
export TRADINGAGENTS_ROOT=/Users/vlad/Projects/TradingAgents
export TRADINGAGENTS_PYTHON=/Users/vlad/Projects/TradingAgents/.venv/bin/python
```

When `PLUGIN_ROOT` itself is the repo (dev), the wrapper detects `mcp_server/`
and prefers that path automatically.

## Install into Cursor (real directory copy)

Symlinks that escape `~/.cursor/plugins/local` are rejected. Copy the thin
plugin files:

```bash
mkdir -p ~/.cursor/plugins/local/tradingagents-desk
cp plugin.json mcp.json ~/.cursor/plugins/local/tradingagents-desk/
cp -R skills bin ~/.cursor/plugins/local/tradingagents-desk/
chmod +x ~/.cursor/plugins/local/tradingagents-desk/bin/run-trading-mcp
```

Then restart Cursor or **Developer: Reload Window**. Set
`TRADINGAGENTS_ROOT` + `TRADINGAGENTS_PYTHON` in the environment Cursor
inherits (or rely on Vlad defaults above).

Grok Bot cannot load local plugins; Cursor IDE can.

## Prove

1. Schema-validate `plugin.json` + `mcp.json` (see `docs/PLUGIN-VERIFY.md`).
2. MCP stdio E2E (Engineer harness — preferred):

   ```bash
   # from repo root, venv active
   python scripts/e2e_mcp_stdio.py --json
   pytest tests/test_e2e_mcp_stdio.py -m integration
   ```

   Details: `docs/MCP-stdio.md`.
3. Confirm local install dir exists as a real copy (not an outside symlink).
4. In Cursor: Customize → Plugins / MCP — confirm `tradingagents-desk` and
   the five frozen tool names.

## Alternative: native Cursor MCP (no plugin)

Same server without the plugin package — fragment in `docs/MCP-stdio.md`.
