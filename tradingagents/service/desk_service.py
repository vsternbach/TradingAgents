"""TradingDeskService — decoupled graph + data access for CLI/MCP.

Step 1 of the Modular Orchestrator & MCP/API Gateway PRD. Errata applied:
- Analyst wire keys: ``market | social | news | fundamentals`` (alias
  ``sentiment`` → ``social``). Report field for social stays ``sentiment_report``.
- v1 surface names: ``get_market_snapshot``, ``get_technical_indicators``,
  ``get_macro_indicators``, ``analyze_ticker_parallel``, ``run_full_trade_desk``.
- Per-analyst results use ``{ok, report?, error?}`` so one failure does not
  nuke the payload (AC-04).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from tradingagents.agents.utils.agent_utils import (
    get_indicators,
    get_macro_indicators as get_macro_indicators_tool,
    get_verified_market_snapshot,
)
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.analyst_execution import ANALYST_NODE_SPECS
from tradingagents.graph.trading_graph import TradingAgentsGraph

WIRE_KEYS = frozenset(ANALYST_NODE_SPECS)
_ALIAS_TO_WIRE = {"sentiment": "social"}

# Default FRED-friendly aliases for get_macro_indicators (fail-open per series).
_DEFAULT_MACRO_INDICATORS = (
    "fed_funds_rate",
    "cpi",
    "real_gdp",
    "10y_treasury",
    "unemployment",
)

GraphFactory = Callable[..., TradingAgentsGraph]


def normalize_analyst_key(key: str) -> str:
    """Map user-facing aliases to canonical wire keys."""
    cleaned = (key or "").strip().lower()
    return _ALIAS_TO_WIRE.get(cleaned, cleaned)


def normalize_analyst_keys(keys: list[str] | tuple[str, ...] | None) -> list[str]:
    if not keys:
        raise ValueError("at least one analyst must be selected")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in keys:
        wire = normalize_analyst_key(raw)
        if wire not in WIRE_KEYS:
            raise ValueError(f"unknown analyst key: {raw}")
        if wire not in seen:
            seen.add(wire)
            normalized.append(wire)
    if not normalized:
        raise ValueError("at least one analyst must be selected")
    return normalized


def report_field_for(wire_key: str) -> str:
    return ANALYST_NODE_SPECS[wire_key].report_key


def _today_str() -> str:
    return date.today().isoformat()


def _tool_invoke(tool: Any, payload: dict[str, Any]) -> Any:
    """Invoke a LangChain ``@tool`` or a plain callable (tests)."""
    invoke = getattr(tool, "invoke", None)
    if callable(invoke):
        return invoke(payload)
    return tool(**payload)


class TradingDeskService:
    """Service core shared by headless CLI and FastMCP (Steps 2–3)."""

    def __init__(
        self,
        config_overrides: dict[str, Any] | None = None,
        *,
        max_workers: int = 8,
        graph_factory: GraphFactory | None = None,
        market_snapshot_tool: Any | None = None,
        indicators_tool: Any | None = None,
        macro_tool: Any | None = None,
    ):
        self.config = DEFAULT_CONFIG.copy()
        if config_overrides:
            self.config.update(config_overrides)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._graph_factory = graph_factory or TradingAgentsGraph
        self._market_snapshot_tool = market_snapshot_tool or get_verified_market_snapshot
        self._indicators_tool = indicators_tool or get_indicators
        self._macro_tool = macro_tool or get_macro_indicators_tool

    def today(self) -> str:
        return _today_str()

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    # --- Tier 1: deterministic data (v1 names) ---

    def get_market_snapshot(self, ticker: str, trade_date: str | None = None) -> dict[str, Any]:
        """Fail-open market snapshot (AC-04)."""
        day = trade_date or self.today()
        try:
            data = _tool_invoke(
                self._market_snapshot_tool,
                {"symbol": ticker, "curr_date": day},
            )
            return {
                "ok": True,
                "ticker": ticker,
                "trade_date": day,
                "data": data,
            }
        except Exception as exc:  # noqa: BLE001 — fail-open for optional vendors
            return {
                "ok": False,
                "ticker": ticker,
                "trade_date": day,
                "error": str(exc),
            }

    # PRD sample name — keep as thin alias for Steps 2–3.
    def get_market_data(self, ticker: str, trade_date: str | None = None) -> dict[str, Any]:
        return self.get_market_snapshot(ticker, trade_date)

    def get_technical_indicators(
        self,
        ticker: str,
        indicators: list[str] | None = None,
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        day = trade_date or self.today()
        names = indicators or ["rsi", "macd", "close_50_sma", "close_200_sma"]
        results: dict[str, Any] = {}
        any_ok = False
        for name in names:
            try:
                results[name] = {
                    "ok": True,
                    "data": _tool_invoke(
                        self._indicators_tool,
                        {
                            "symbol": ticker,
                            "indicator": name,
                            "curr_date": day,
                        },
                    ),
                }
                any_ok = True
            except Exception as exc:  # noqa: BLE001
                results[name] = {"ok": False, "error": str(exc)}
        return {
            "ok": any_ok,
            "ticker": ticker,
            "trade_date": day,
            "indicators": results,
        }

    def get_macro_indicators(
        self,
        trade_date: str | None = None,
        indicators: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch macro series; each series fails open independently (AC-04)."""
        day = trade_date or self.today()
        names = indicators or list(_DEFAULT_MACRO_INDICATORS)
        series: dict[str, Any] = {}
        any_ok = False
        for name in names:
            try:
                series[name] = {
                    "ok": True,
                    "data": _tool_invoke(
                        self._macro_tool,
                        {"indicator": name, "curr_date": day},
                    ),
                }
                any_ok = True
            except Exception as exc:  # noqa: BLE001
                series[name] = {"ok": False, "error": str(exc)}
        return {
            "ok": any_ok,
            "trade_date": day,
            "series": series,
        }

    # --- Tier 2 / 3: analysts ---

    def run_analyst(
        self,
        ticker: str,
        analyst_key: str,
        trade_date: str | None = None,
        *,
        asset_type: str = "stock",
    ) -> dict[str, Any]:
        """Run one analyst in isolation; returns typed ``ok``/``report``/``error``."""
        day = trade_date or self.today()
        wire = normalize_analyst_key(analyst_key)
        if wire not in WIRE_KEYS:
            return {
                "ok": False,
                "ticker": ticker,
                "trade_date": day,
                "aspect": wire,
                "error": f"unknown analyst key: {analyst_key}",
            }
        report_key = report_field_for(wire)
        try:
            graph = self._graph_factory(
                selected_analysts=[wire],
                config=self.config,
            )
            state, _signal = graph.propagate(
                company_name=ticker,
                trade_date=day,
                asset_type=asset_type,
            )
            report = ""
            if isinstance(state, dict):
                report = state.get(report_key) or ""
            return {
                "ok": True,
                "ticker": ticker,
                "trade_date": day,
                "aspect": wire,
                "report": report,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "ticker": ticker,
                "trade_date": day,
                "aspect": wire,
                "error": str(exc),
            }

    async def analyze_ticker_parallel(
        self,
        ticker: str,
        analysts: list[str] | None = None,
        trade_date: str | None = None,
        *,
        asset_type: str = "stock",
    ) -> dict[str, Any]:
        """Dispatch selected analysts concurrently (AC-02 / v1 parallel tool)."""
        day = trade_date or self.today()
        keys = normalize_analyst_keys(
            analysts or ["market", "social", "news", "fundamentals"]
        )
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(
                self._executor,
                lambda k=key: self.run_analyst(
                    ticker, k, day, asset_type=asset_type
                ),
            )
            for key in keys
        ]
        results = await asyncio.gather(*tasks)
        by_aspect = {item["aspect"]: item for item in results}
        return {
            "ok": any(item.get("ok") for item in results),
            "ticker": ticker,
            "trade_date": day,
            "mode": "parallel",
            "aspects": keys,
            "analysts": by_aspect,
        }

    async def run_analysts_concurrent(
        self,
        ticker: str,
        analyst_keys: list[str],
        trade_date: str | None = None,
        *,
        asset_type: str = "stock",
    ) -> dict[str, Any]:
        """PRD sample alias for ``analyze_ticker_parallel``."""
        return await self.analyze_ticker_parallel(
            ticker,
            analysts=analyst_keys,
            trade_date=trade_date,
            asset_type=asset_type,
        )

    # --- Tier 4: full desk ---

    def run_full_trade_desk(
        self,
        ticker: str,
        trade_date: str | None = None,
        asset_type: str = "stock",
        *,
        save_reports: bool = False,
    ) -> dict[str, Any]:
        """Run the full 11-agent desk; typed signal + thesis (v1 name)."""
        day = trade_date or self.today()
        try:
            graph = self._graph_factory(config=self.config)
            state, signal = graph.propagate(
                company_name=ticker,
                trade_date=day,
                asset_type=asset_type,
            )
            report_path = None
            if save_reports and hasattr(graph, "save_reports"):
                report_path = str(graph.save_reports(state, ticker))
            thesis = ""
            if isinstance(state, dict):
                thesis = (
                    state.get("final_trade_decision")
                    or state.get("trader_investment_plan")
                    or ""
                )
            analysts: dict[str, Any] = {}
            if isinstance(state, dict):
                for wire, spec in ANALYST_NODE_SPECS.items():
                    report = state.get(spec.report_key)
                    if report:
                        analysts[wire] = {"ok": True, "report": report}
            return {
                "ok": True,
                "ticker": ticker,
                "trade_date": day,
                "mode": "full",
                "asset_type": asset_type,
                "signal": signal,
                "thesis": thesis,
                "complete_report_path": report_path,
                "memory_log_path": self.config.get("memory_log_path"),
                "analysts": analysts,
                "trade_plan": (
                    state.get("trader_investment_plan") if isinstance(state, dict) else None
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "ticker": ticker,
                "trade_date": day,
                "mode": "full",
                "asset_type": asset_type,
                "error": str(exc),
            }

    def run_full_pipeline(
        self,
        ticker: str,
        trade_date: str | None = None,
        asset_type: str = "stock",
    ) -> dict[str, Any]:
        """PRD sample alias for ``run_full_trade_desk``."""
        return self.run_full_trade_desk(ticker, trade_date, asset_type=asset_type)


__all__ = [
    "TradingDeskService",
    "WIRE_KEYS",
    "normalize_analyst_key",
    "normalize_analyst_keys",
    "report_field_for",
]
