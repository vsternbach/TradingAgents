"""Pytest wrapper for the stdio MCP E2E harness (PRD Step 4 / AC-03)."""

from __future__ import annotations

import asyncio

import pytest

from mcp_server.trading_mcp import V1_TOOL_NAMES
from scripts.e2e_mcp_stdio import run_e2e


@pytest.mark.integration
def test_stdio_mcp_tools_list_and_data_tools():
    report = asyncio.run(run_e2e(ticker="AAPL", trade_date="2026-01-15"))
    assert report["ok"] is True, report.get("error") or report
    assert sorted(report["tools_list"]) == sorted(V1_TOOL_NAMES)
    snap = report["calls"]["get_market_snapshot"]
    assert snap["ok"] is True
    assert snap["ticker"] == "AAPL"
    assert snap["has_data"] is True
    macro = report["calls"]["get_macro_indicators"]
    assert "ok" in macro
    assert isinstance(macro.get("series_keys"), list)
