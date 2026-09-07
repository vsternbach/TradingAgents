#!/usr/bin/env python3
"""Stdio MCP E2E harness for TradingAgents FastMCP (PRD Step 4).

Starts ``python -m mcp_server.trading_mcp`` over stdio, asserts the frozen
``tools/list`` surface, and calls deterministic data tools.

Usage (from repo root, with venv activated or PYTHONPATH set):

  python scripts/e2e_mcp_stdio.py
  python scripts/e2e_mcp_stdio.py --ticker AAPL --date 2026-01-15 --json

Exit codes: 0 success, 1 assertion/runtime failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Frozen v1 surface (Product Design errata / Step 3).
V1_TOOL_NAMES = (
    "get_market_snapshot",
    "get_technical_indicators",
    "get_macro_indicators",
    "analyze_ticker_parallel",
    "run_full_trade_desk",
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _python_executable() -> str:
    # Prefer the active interpreter (venv) so the child has mcp + tradingagents.
    return sys.executable


def _server_params() -> StdioServerParameters:
    env = os.environ.copy()
    # Ensure repo root is importable even if not installed editable.
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(REPO_ROOT) if not existing else f"{REPO_ROOT}{os.pathsep}{existing}"
    )
    return StdioServerParameters(
        command=_python_executable(),
        args=["-m", "mcp_server.trading_mcp"],
        cwd=str(REPO_ROOT),
        env=env,
    )


def _payload_from_call_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    texts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)
    if len(texts) == 1:
        try:
            parsed = json.loads(texts[0])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"raw": texts[0]}
    return {"blocks": texts}


async def run_e2e(
    *,
    ticker: str = "AAPL",
    trade_date: str = "2026-01-15",
) -> dict[str, Any]:
    """Drive the FastMCP server over stdio and return a result summary."""
    report: dict[str, Any] = {
        "ok": False,
        "server": "python -m mcp_server.trading_mcp",
        "tools_list": [],
        "calls": {},
        "notes": [
            "LLM tools (analyze_ticker_parallel / run_full_trade_desk) are covered "
            "by unit tests with fakes; live desk calls need provider API keys.",
        ],
    }

    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        listed = await session.list_tools()
        names = [t.name for t in listed.tools]
        report["tools_list"] = names
        if sorted(names) != sorted(V1_TOOL_NAMES):
            report["error"] = (
                f"tools/list mismatch: got {names}, expected {list(V1_TOOL_NAMES)}"
            )
            return report

        snap = await session.call_tool(
            "get_market_snapshot",
            {"ticker": ticker, "trade_date": trade_date},
        )
        if snap.isError:
            report["error"] = "get_market_snapshot returned isError"
            report["calls"]["get_market_snapshot"] = _payload_from_call_result(snap)
            return report
        snap_payload = _payload_from_call_result(snap)
        report["calls"]["get_market_snapshot"] = {
            "ok": bool(snap_payload.get("ok")),
            "ticker": snap_payload.get("ticker"),
            "trade_date": snap_payload.get("trade_date"),
            "has_data": "data" in snap_payload or "error" in snap_payload,
            # Keep a short preview for humans; full markdown can be huge.
            "data_preview": str(snap_payload.get("data", snap_payload.get("error", "")))[
                :240
            ],
        }
        if "ok" not in snap_payload or "ticker" not in snap_payload:
            report["error"] = "get_market_snapshot missing structured ok/ticker fields"
            return report

        macro = await session.call_tool(
            "get_macro_indicators",
            {"trade_date": trade_date},
        )
        macro_payload = _payload_from_call_result(macro)
        report["calls"]["get_macro_indicators"] = {
            "ok": bool(macro_payload.get("ok")),
            "trade_date": macro_payload.get("trade_date"),
            "series_keys": list((macro_payload.get("series") or {}).keys()),
            "isError": bool(macro.isError),
        }
        # Fail-open: tool may return ok=False without API keys; still must be structured.
        if not isinstance(macro_payload, dict) or "ok" not in macro_payload:
            report["error"] = "get_macro_indicators missing structured ok field"
            return report

        report["ok"] = True
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--date", default="2026-01-15", help="YYYY-MM-DD")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args(argv)

    try:
        report = asyncio.run(run_e2e(ticker=args.ticker, trade_date=args.date))
    except Exception as exc:  # noqa: BLE001 — harness surfaces any spawn/protocol failure
        print(f"E2E failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        status = "PASS" if report.get("ok") else "FAIL"
        print(f"[{status}] tools/list={report.get('tools_list')}")
        for name, detail in (report.get("calls") or {}).items():
            print(f"  {name}: {detail}")
        if report.get("error"):
            print(f"error: {report['error']}", file=sys.stderr)
        for note in report.get("notes") or []:
            print(f"note: {note}")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
