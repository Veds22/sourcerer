"""
FastAPI backend for the Sourcerer web UI (Process 2).

Run with:
    uv run uvicorn src.api:app --reload --port 8000

Requires the MCP server (src/mcp_server.py) to be running separately
on port 8001 — this process is only an MCP *client*.
"""
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src import db
from src.llm import stream_reply

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sourcerer.api")

app = FastAPI(title="Sourcerer API")

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse

MCP_INTERNAL_URL = "http://127.0.0.1:8001/mcp"


@app.api_route(
    "/mcp",
    methods=["GET", "POST", "DELETE"],
)
async def mcp_proxy(request: Request):
    body = await request.body()

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length"}
    }

    client = httpx.AsyncClient(timeout=None)

    upstream_request = client.build_request(
        request.method,
        MCP_INTERNAL_URL,
        content=body,
        headers=headers,
        params=request.query_params,
    )

    try:
        response = await client.send(upstream_request, stream=True)
    except Exception:
        await client.aclose()
        raise

    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower()
        not in {"content-length", "transfer-encoding", "connection"}
    }

    async def stream():
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        status_code=response.status_code,
        headers=response_headers,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/history")
def history(limit: int = 50):
    """Recent chat history, for the UI to render when it first loads."""
    return db.get_recent_messages(limit=limit)


@app.post("/chat")
async def chat(req: ChatRequest):
    """Stream the assistant's reply back as Server-Sent Events.

    Each event's `data` is JSON:
      {"type": "token", "content": "..."}   — a text chunk to append
      {"type": "tool_call", "name": "..."}  — a tool the agent invoked
      {"type": "done"}                      — stream finished
      {"type": "error", "message": "..."}   — something went wrong
    """

    async def event_generator():
        try:
            async for event in stream_reply(req.message):
                yield {"event": "message", "data": json.dumps(event)}
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            logger.exception("stream_reply failed")
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(exc)}),
            }

    return EventSourceResponse(event_generator())
