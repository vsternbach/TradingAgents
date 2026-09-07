"""Unit tests for cli.headless (AC-01 — non-interactive JSON)."""

from __future__ import annotations

import json
import unittest
from unittest import mock

import pytest
from typer.testing import CliRunner

from cli import headless as h


class _FakeService:
    def __init__(self, *a, **k):
        pass

    def shutdown(self):
        pass

    def get_market_snapshot(self, ticker, trade_date=None):
        return {"ok": True, "ticker": ticker, "trade_date": trade_date, "data": "snap"}

    def get_technical_indicators(self, ticker, indicators=None, trade_date=None):
        return {
            "ok": True,
            "ticker": ticker,
            "trade_date": trade_date,
            "indicators": {"rsi": {"ok": True, "data": "55"}},
        }

    def get_macro_indicators(self, trade_date=None, indicators=None):
        return {"ok": True, "trade_date": trade_date, "series": {"cpi": {"ok": True}}}

    def run_analyst(self, ticker, analyst_key, trade_date=None, *, asset_type="stock"):
        return {
            "ok": True,
            "ticker": ticker,
            "trade_date": trade_date,
            "aspect": "social" if analyst_key in ("sentiment", "social") else analyst_key,
            "report": f"report-{analyst_key}",
        }

    async def analyze_ticker_parallel(
        self, ticker, analysts=None, trade_date=None, *, asset_type="stock"
    ):
        keys = analysts or ["market", "social"]
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
            "asset_type": asset_type,
            "signal": "Hold",
            "thesis": "thesis",
        }


@pytest.mark.unit
class HeadlessCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_technical_json_no_prompts(self):
        with mock.patch.object(h, "TradingDeskService", _FakeService):
            result = self.runner.invoke(
                h.app,
                ["--ticker", "AAPL", "--mode", "technical", "--json", "--date", "2026-01-15"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ticker"], "AAPL")
        self.assertIn("market", payload["analysts"])
        self.assertEqual(payload["analysts"]["market"]["report"], "report-market")

    def test_sentiment_mode_maps_to_social_wire(self):
        with mock.patch.object(h, "TradingDeskService", _FakeService):
            result = self.runner.invoke(
                h.app,
                ["--ticker", "TSLA", "--mode", "sentiment", "--json", "--date", "2026-01-15"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertIn("social", payload["analysts"])

    def test_analysts_parallel_json(self):
        with mock.patch.object(h, "TradingDeskService", _FakeService):
            result = self.runner.invoke(
                h.app,
                [
                    "--ticker",
                    "BTC-USD",
                    "--analysts",
                    "market,social",
                    "--json",
                    "--date",
                    "2026-01-15",
                ],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["mode"], "parallel")
        self.assertEqual(payload["aspects"], ["market", "social"])

    def test_data_mode_json(self):
        with mock.patch.object(h, "TradingDeskService", _FakeService):
            result = self.runner.invoke(
                h.app,
                ["--ticker", "AAPL", "--mode", "data", "--json", "--date", "2026-01-15"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["mode"], "data")
        self.assertTrue(payload["market_snapshot"]["ok"])

    def test_full_mode_json(self):
        with mock.patch.object(h, "TradingDeskService", _FakeService):
            result = self.runner.invoke(
                h.app,
                ["--ticker", "NVDA", "--mode", "full", "--json", "--date", "2026-01-15"],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["signal"], "Hold")
        self.assertEqual(payload["mode"], "full")

    def test_missing_ticker_exits_nonzero(self):
        result = self.runner.invoke(h.app, ["--mode", "data", "--json"])
        self.assertNotEqual(result.exit_code, 0)

    def test_sentiment_alias_in_analysts_flag(self):
        with mock.patch.object(h, "TradingDeskService", _FakeService):
            result = self.runner.invoke(
                h.app,
                [
                    "--ticker",
                    "AAPL",
                    "--analysts",
                    "sentiment",
                    "--json",
                    "--date",
                    "2026-01-15",
                ],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["aspects"], ["social"])


if __name__ == "__main__":
    unittest.main()
