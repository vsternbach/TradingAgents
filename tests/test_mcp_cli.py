"""Unit tests for trading_mcp CLI flags and allowlist env."""

from __future__ import annotations

import os
import unittest

import pytest

from mcp_server.trading_mcp import build_transport_security, parse_args


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


@pytest.mark.unit
class TransportSecurityEnvTests(unittest.TestCase):
    def test_mcp_allowed_hosts_merged_with_localhost(self):
        prev = os.environ.get("MCP_ALLOWED_HOSTS")
        try:
            os.environ["MCP_ALLOWED_HOSTS"] = (
                "mac.tailbe8cfe.ts.net,mac.tailbe8cfe.ts.net:*"
            )
            settings = build_transport_security()
            self.assertTrue(settings.enable_dns_rebinding_protection)
            self.assertIn("127.0.0.1:*", settings.allowed_hosts)
            self.assertIn("localhost:*", settings.allowed_hosts)
            self.assertIn("mac.tailbe8cfe.ts.net", settings.allowed_hosts)
            self.assertIn("mac.tailbe8cfe.ts.net:*", settings.allowed_hosts)
        finally:
            if prev is None:
                os.environ.pop("MCP_ALLOWED_HOSTS", None)
            else:
                os.environ["MCP_ALLOWED_HOSTS"] = prev
