"""Real MCP smoke test: spawn the stdio server and drive it with the SDK client.

This does not mock anything — it launches ``python -m sqlite_rag_mcp`` as a
subprocess and talks MCP over stdio, exactly like Claude Code / Claude
Desktop would. If Ollama is not running on the host, the server must still
index and answer searches (lexical fallback).
"""
from __future__ import annotations

import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .conftest import FIXTURES_DIR

EXPECTED_TOOLS = {"index_documents", "search", "get_chunk", "stats"}


def _payload(result) -> dict:
    """Extract the tool's JSON payload from a CallToolResult."""
    if result.structuredContent:
        sc = result.structuredContent
        return sc.get("result", sc)
    return json.loads(result.content[0].text)


async def test_stdio_server_end_to_end(tmp_path):
    env = dict(os.environ)
    env["SQLITE_RAG_DB"] = str(tmp_path / "smoke.db")
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "sqlite_rag_mcp"], env=env
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == EXPECTED_TOOLS

            # index the fixture corpus through the MCP tool
            res = await session.call_tool(
                "index_documents", {"path": str(FIXTURES_DIR)}
            )
            assert not res.isError
            stats = _payload(res)
            assert stats["files_indexed"] == 7

            # search (works with or without Ollama on the host)
            res = await session.call_tool(
                "search", {"query": "kubernetes readiness probe", "k": 3}
            )
            assert not res.isError
            out = _payload(res)
            assert out["results"]
            assert out["results"][0]["source"].endswith("deployment.md")

            # fetch the full chunk
            res = await session.call_tool(
                "get_chunk", {"chunk_id": out["results"][0]["chunk_id"]}
            )
            assert not res.isError
            assert _payload(res)["found"] is True

            # stats
            res = await session.call_tool("stats", {})
            assert not res.isError
            assert _payload(res)["documents"] == 7
