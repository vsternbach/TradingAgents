"""Unit tests for trading_mcp CLI flags."""

from __future__ import annotations

import unittest

import pytest

from mcp_server.trading_mcp import parse_args


@pytest.mark.unit
class McpCliTests(unittest.TestCase):
    def test_defaults_stdio(self):
        args = parse_args([])
        self.assertEqual(args.transport, "stdio")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 8000)

    def test_sse_flags(self):
        args = parse_args(
            ["--transport", "sse", "--host", "127.0.0.1", "--port", "9001"]
        )
        self.assertEqual(args.transport, "sse")
        self.assertEqual(args.port, 9001)
