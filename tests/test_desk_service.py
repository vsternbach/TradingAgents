"""Unit tests for TradingDeskService (Step 1 / AC-02, AC-04 shapes)."""

from __future__ import annotations

import asyncio
import time
import unittest

import pytest

from tradingagents.service.desk_service import (
    TradingDeskService,
    normalize_analyst_key,
    normalize_analyst_keys,
    report_field_for,
)


@pytest.mark.unit
class NormalizeAnalystKeyTests(unittest.TestCase):
    def test_sentiment_alias_maps_to_social(self):
        self.assertEqual(normalize_analyst_key("sentiment"), "social")
        self.assertEqual(normalize_analyst_key("Sentiment"), "social")

    def test_wire_keys_passthrough(self):
        for key in ("market", "social", "news", "fundamentals"):
            self.assertEqual(normalize_analyst_key(key), key)

    def test_normalize_list_dedupes_and_aliases(self):
        self.assertEqual(
            normalize_analyst_keys(["market", "sentiment", "market"]),
            ["market", "social"],
        )

    def test_rejects_unknown(self):
        with self.assertRaises(ValueError):
            normalize_analyst_keys(["market", "macro"])

    def test_social_report_field(self):
        self.assertEqual(report_field_for("social"), "sentiment_report")
        self.assertEqual(report_field_for("market"), "market_report")


class _FakeGraph:
    """Minimal stand-in for TradingAgentsGraph.propagate."""

    def __init__(self, selected_analysts=None, config=None, **_kwargs):
        self.selected_analysts = tuple(selected_analysts or ())
        self.config = config or {}
        self.delay = float(self.config.get("_fake_delay", 0.05))
        self.fail_aspects = set(self.config.get("_fail_aspects") or [])

    def propagate(self, company_name, trade_date, asset_type: str = "stock"):
        time.sleep(self.delay)
        if self.selected_analysts and self.selected_analysts[0] in self.fail_aspects:
            raise RuntimeError(f"boom:{self.selected_analysts[0]}")
        if not self.selected_analysts:
            # Full desk path
            return (
                {
                    "market_report": "m",
                    "sentiment_report": "s",
                    "news_report": "n",
                    "fundamentals_report": "f",
                    "final_trade_decision": "Hold — thesis",
                    "trader_investment_plan": "plan",
                },
                "Hold",
            )
        wire = self.selected_analysts[0]
        field = {
            "market": "market_report",
            "social": "sentiment_report",
            "news": "news_report",
            "fundamentals": "fundamentals_report",
        }[wire]
        return ({field: f"report-for-{wire}-{company_name}"}, "Hold")


@pytest.mark.unit
class TradingDeskServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = TradingDeskService(
            config_overrides={"_fake_delay": 0.08, "_fail_aspects": []},
            graph_factory=_FakeGraph,
            market_snapshot_tool=lambda **kw: f"snap:{kw['symbol']}",
            indicators_tool=lambda **kw: f"ind:{kw['indicator']}",
            macro_tool=lambda **kw: f"macro:{kw['indicator']}",
        )

    def tearDown(self):
        self.service.shutdown()

    def test_run_analyst_uses_sentiment_report_for_social(self):
        result = self.service.run_analyst("AAPL", "sentiment", "2026-01-15")
        self.assertTrue(result["ok"])
        self.assertEqual(result["aspect"], "social")
        self.assertIn("report-for-social", result["report"])

    def test_analyze_ticker_parallel_is_concurrent(self):
        keys = ["market", "social", "news"]
        started = time.monotonic()
        payload = asyncio.run(
            self.service.analyze_ticker_parallel(
                "NVDA",
                analysts=keys,
                trade_date="2026-01-15",
            )
        )
        elapsed = time.monotonic() - started
        # 3 × 0.08s sequential would be ~0.24s; parallel should be closer to one delay.
        self.assertLess(elapsed, 0.20)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["aspects"], keys)
        self.assertEqual(payload["mode"], "parallel")
        for key in keys:
            self.assertTrue(payload["analysts"][key]["ok"])
            self.assertIn(f"report-for-{key}", payload["analysts"][key]["report"])

    def test_parallel_partial_failure_keeps_other_reports(self):
        self.service.config["_fail_aspects"] = ["news"]
        payload = asyncio.run(
            self.service.analyze_ticker_parallel(
                "TSLA",
                analysts=["market", "news"],
                trade_date="2026-01-15",
            )
        )
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["analysts"]["market"]["ok"])
        self.assertFalse(payload["analysts"]["news"]["ok"])
        self.assertIn("boom:news", payload["analysts"]["news"]["error"])

    def test_get_market_snapshot_fail_open(self):
        def boom(**_kw):
            raise ConnectionError("vendor down")

        svc = TradingDeskService(
            graph_factory=_FakeGraph,
            market_snapshot_tool=boom,
        )
        out = svc.get_market_snapshot("AAPL", "2026-01-15")
        self.assertFalse(out["ok"])
        self.assertIn("vendor down", out["error"])
        svc.shutdown()

    def test_get_macro_indicators_per_series_fail_open(self):
        def flaky(**kw):
            if kw["indicator"] == "cpi":
                raise TimeoutError("fred timeout")
            return f"ok:{kw['indicator']}"

        svc = TradingDeskService(graph_factory=_FakeGraph, macro_tool=flaky)
        out = svc.get_macro_indicators(
            "2026-01-15",
            indicators=["fed_funds_rate", "cpi"],
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["series"]["fed_funds_rate"]["ok"])
        self.assertFalse(out["series"]["cpi"]["ok"])
        svc.shutdown()

    def test_run_full_trade_desk_typed_payload(self):
        out = self.service.run_full_trade_desk("BTC-USD", "2026-01-15", asset_type="crypto")
        self.assertTrue(out["ok"])
        self.assertEqual(out["signal"], "Hold")
        self.assertIn("thesis", out["thesis"].lower() + out.get("thesis", ""))
        self.assertEqual(out["mode"], "full")
        self.assertTrue(out["analysts"]["social"]["ok"])

    def test_run_analysts_concurrent_alias(self):
        payload = asyncio.run(
            self.service.run_analysts_concurrent(
                "AAPL",
                ["market"],
                "2026-01-15",
            )
        )
        self.assertTrue(payload["analysts"]["market"]["ok"])


if __name__ == "__main__":
    unittest.main()
