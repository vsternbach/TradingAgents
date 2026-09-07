"""SSE smoke: FastMCP starts and tools/list matches frozen v1 names."""

from __future__ import annotations

import asyncio
import socket
import threading
import time

import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client

from mcp_server.trading_mcp import V1_TOOL_NAMES, create_mcp_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _FakeDesk:
    """Minimal desk so server construction does not touch vendors."""

    def get_market_snapshot(self, *a, **k):
        return {"ok": True}

    def get_technical_indicators(self, *a, **k):
        return {"ok": True}

    def get_macro_indicators(self, *a, **k):
        return {"ok": True}

    async def analyze_ticker_parallel(self, *a, **k):
        return {"ok": True}

    def run_full_trade_desk(self, *a, **k):
        return {"ok": True}


@pytest.mark.integration
def test_sse_tools_list_matches_frozen_v1_names():
    port = _free_port()
    server = create_mcp_server(_FakeDesk(), host="127.0.0.1", port=port)

    thread = threading.Thread(
        target=lambda: server.run(transport="sse"),
        daemon=True,
    )
    thread.start()

    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        pytest.fail(f"SSE server did not listen on 127.0.0.1:{port}")

    async def _list() -> list[str]:
        url = f"http://127.0.0.1:{port}/sse"
        async with (
            sse_client(url) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            return [t.name for t in listed.tools]

    names = asyncio.run(_list())
    assert sorted(names) == sorted(V1_TOOL_NAMES)
