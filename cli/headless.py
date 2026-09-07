"""Non-interactive headless CLI for TradingAgents (PRD Step 2 / AC-01).

Examples:
  python -m cli.headless --ticker AAPL --mode technical --json
  python -m cli.headless --ticker BTC-USD --analysts market,social --json
  python -m cli.headless --ticker NVDA --mode full --json
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import typer

from cli.utils import detect_asset_type, normalize_ticker_symbol
from tradingagents.service.desk_service import (
    TradingDeskService,
    normalize_analyst_keys,
)

app = typer.Typer(
    name="tradingagents-headless",
    help="Non-interactive TradingAgents runner (JSON-friendly).",
    add_completion=False,
    no_args_is_help=True,
    invoke_without_command=True,
)

# Specialist --mode values map to wire keys (sentiment → social via normalize).
_MODE_ASPECTS: dict[str, list[str]] = {
    "technical": ["market"],
    "market": ["market"],
    "sentiment": ["social"],
    "social": ["social"],
    "news": ["news"],
    "fundamentals": ["fundamentals"],
    "parallel": ["market", "social", "news", "fundamentals"],
}

_SPECIAL_MODES = frozenset({"full", "data", "macro"})
_VALID_MODES = _SPECIAL_MODES | frozenset(_MODE_ASPECTS)


def parse_date(value: str | None) -> str:
    if not value:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise typer.BadParameter("date must be YYYY-MM-DD") from exc
    return value


def parse_analysts(raw: str | None) -> list[str] | None:
    if raw is None or not str(raw).strip():
        return None
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        return None
    try:
        return normalize_analyst_keys(parts)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def resolve_asset_type(symbol: str, asset_type: str | None) -> str:
    if asset_type:
        at = asset_type.strip().lower()
        if at not in ("stock", "crypto"):
            raise typer.BadParameter("asset-type must be stock or crypto")
        return at
    detected = detect_asset_type(symbol)
    return getattr(detected, "value", None) or str(detected).split(".")[-1].lower()


def emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    typer.echo(
        f"ok={payload.get('ok')} ticker={payload.get('ticker', '')} "
        f"mode={payload.get('mode') or payload.get('aspects')}"
    )
    if payload.get("signal"):
        typer.echo(f"signal={payload['signal']}")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}", err=True)


def build_payload(
    *,
    service: TradingDeskService,
    ticker: str,
    trade_date: str,
    mode: str,
    analysts: list[str] | None,
    asset_type: str,
) -> dict[str, Any]:
    """Map CLI flags onto TradingDeskService. Pure dispatch for unit tests."""
    mode_key = (mode or "full").strip().lower()
    if mode_key not in _VALID_MODES:
        return {
            "ok": False,
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": mode_key,
            "error": f"unknown mode: {mode}",
        }

    # Explicit --analysts always wins over --mode specialist mapping.
    if analysts is not None:
        if len(analysts) == 1:
            result = service.run_analyst(
                ticker, analysts[0], trade_date, asset_type=asset_type
            )
            return {
                "ok": bool(result.get("ok")),
                "ticker": ticker,
                "trade_date": trade_date,
                "mode": analysts[0],
                "aspects": analysts,
                "analysts": {analysts[0]: result},
            }
        return asyncio.run(
            service.analyze_ticker_parallel(
                ticker,
                analysts=analysts,
                trade_date=trade_date,
                asset_type=asset_type,
            )
        )

    if mode_key == "data":
        snap = service.get_market_snapshot(ticker, trade_date)
        tech = service.get_technical_indicators(ticker, trade_date=trade_date)
        return {
            "ok": bool(snap.get("ok") or tech.get("ok")),
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": "data",
            "market_snapshot": snap,
            "technical_indicators": tech,
        }

    if mode_key == "macro":
        macro = service.get_macro_indicators(trade_date)
        return {
            "ok": bool(macro.get("ok")),
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": "macro",
            "macro": macro,
        }

    if mode_key == "full":
        return service.run_full_trade_desk(
            ticker, trade_date, asset_type=asset_type
        )

    aspects = _MODE_ASPECTS[mode_key]
    if len(aspects) == 1:
        result = service.run_analyst(
            ticker, aspects[0], trade_date, asset_type=asset_type
        )
        return {
            "ok": bool(result.get("ok")),
            "ticker": ticker,
            "trade_date": trade_date,
            "mode": mode_key,
            "aspects": aspects,
            "analysts": {aspects[0]: result},
        }
    return asyncio.run(
        service.analyze_ticker_parallel(
            ticker,
            analysts=aspects,
            trade_date=trade_date,
            asset_type=asset_type,
        )
    )


@app.callback()
def main(
    ticker: str = typer.Option(..., "--ticker", help="Instrument symbol (AAPL, BTC-USD, 0700.HK)."),
    date: str | None = typer.Option(
        None, "--date", help="Trade date YYYY-MM-DD (default: today)."
    ),
    mode: str = typer.Option(
        "full",
        "--mode",
        help="full | data | macro | technical | sentiment | news | fundamentals | parallel",
    ),
    analysts: str | None = typer.Option(
        None,
        "--analysts",
        help="Comma-separated wire keys (market,social,news,fundamentals).",
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Emit structured JSON on stdout (AC-01)."
    ),
    asset_type: str | None = typer.Option(
        None,
        "--asset-type",
        help="stock | crypto (default: auto-detect from ticker).",
    ),
    save_dir: str | None = typer.Option(
        None,
        "--save-dir",
        help="Override results_dir for this run.",
    ),
) -> None:
    """Run TradingDeskService without interactive prompts."""
    trade_date = parse_date(date)
    parsed_analysts = parse_analysts(analysts)
    symbol = normalize_ticker_symbol(ticker)
    at = resolve_asset_type(symbol, asset_type)

    overrides: dict[str, Any] = {}
    if save_dir:
        overrides["results_dir"] = save_dir

    service = TradingDeskService(config_overrides=overrides or None)
    try:
        payload = build_payload(
            service=service,
            ticker=symbol,
            trade_date=trade_date,
            mode=mode,
            analysts=parsed_analysts,
            asset_type=at,
        )
        emit(payload, as_json=json_out)
        raise typer.Exit(code=0 if payload.get("ok") else 2)
    finally:
        service.shutdown()


def run(argv: list[str] | None = None) -> None:
    """Entrypoint for ``python -m cli.headless`` and CliRunner tests."""
    app(args=argv, prog_name="python -m cli.headless")


if __name__ == "__main__":
    run()
