"""Tests for FastMCP TradingAgents server (AC-03 / frozen v1 tools)."""

from __future__ import annotations

import asyncio
import json
import unittest

import pytest

from mcp_server.trading_mcp import V1_TOOL_NAMES, create_mcp_server


class _FakeDesk:
    def get_market_snapshot(self, ticker, trade_date=None):
        return {
            "ok": True,
            "ticker": ticker,
            "trade_date": trade_date or "2026-01-15",
            "data": {
                "current_price": 190.5,
                "volume": 1000,
                "change_pct": 1.2,
            },
        }

    def get_technical_indicators(self, ticker, indicators=None, trade_date=None):
        return {
            "ok": True,
            "ticker": ticker,
            "trade_date": trade_date,
            "indicators": {"rsi": {"ok": True, "data": "55.0"}},
        }

    def get_macro_indicators(self, trade_date=None, indicators=None):
        return {
            "ok": True,
            "trade_date": trade_date,
            "series": {"fed_funds_rate": {"ok": True, "data": "5.25"}},
        }

    async def analyze_ticker_parallel(
        self, ticker, analysts=None, trade_date=None, *, asset_type="stock"
    ):
        keys = analysts or ["market", "social"]
        # Normalize sentiment alias the way the real service does
        from tradingagents.service.desk_service import normalize_analyst_keys

        keys = normalize_analyst_keys(keys)
        return {
            "ok": True,
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": "parallel",
            "aspects": keys,
            "analysts": {
                k: {"ok": True, "aspect": k, "report": f"r-{k}"} for k in keys
            },
        }

    def run_full_trade_desk(self, ticker, trade_date=None, asset_type="stock", **kw):
        return {
            "ok": True,
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": "full",
            "signal": "Hold",
            "thesis": "thesis",
            "analysts": {"social": {"ok": True, "report": "s"}},
        }


def _tool_names(server) -> list[str]:
    tools = asyncio.run(server.list_tools())
    return [t.name for t in tools]


def _call_tool_payload(server, name: str, arguments: dict):
    result = asyncio.run(server.call_tool(name, arguments))
    # FastMCP 1.x returns (content_blocks, structured_dict) for dict tools.
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        return result[1]
    if isinstance(result, dict):
        return result
    blocks = result[0] if isinstance(result, tuple) else result
    texts = []
    for block in blocks:
        text = getattr(block, "text", None)
        if text is not None:
            texts.append(text)
        elif isinstance(block, dict) and "text" in block:
            texts.append(block["text"])
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError:
            return {"raw": texts[0]}
    return {"blocks": texts}


@pytest.mark.unit
class TradingMcpTests(unittest.TestCase):
    def setUp(self):
        self.server = create_mcp_server(_FakeDesk())

    def test_tools_list_matches_frozen_v1_names(self):
        names = _tool_names(self.server)
        self.assertEqual(sorted(names), sorted(V1_TOOL_NAMES))
        self.assertEqual(
            set(names),
            {
                "get_market_snapshot",
                "get_technical_indicators",
                "get_macro_indicators",
                "analyze_ticker_parallel",
                "run_full_trade_desk",
            },
        )

    def test_get_market_snapshot_returns_structured_json(self):
        payload = _call_tool_payload(
            self.server,
            "get_market_snapshot",
            {"ticker": "AAPL", "trade_date": "2026-01-15"},
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticker"], "AAPL")
        self.assertIsInstance(payload["data"], dict)
        self.assertIn("current_price", payload["data"])

    def test_analyze_ticker_parallel_sentiment_alias(self):
        payload = _call_tool_payload(
            self.server,
            "analyze_ticker_parallel",
            {
                "ticker": "TSLA",
                "analysts": ["sentiment", "market"],
                "trade_date": "2026-01-15",
            },
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["aspects"], ["social", "market"])
        self.assertIn("social", payload["analysts"])
        self.assertTrue(payload["analysts"]["social"]["ok"])

    def test_run_full_trade_desk_typed(self):
        payload = _call_tool_payload(
            self.server,
            "run_full_trade_desk",
            {"ticker": "NVDA", "trade_date": "2026-01-15"},
        )
        self.assertEqual(payload["signal"], "Hold")
        self.assertEqual(payload["mode"], "full")


if __name__ == "__main__":
    unittest.main()
