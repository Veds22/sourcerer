"""
LangGraph orchestration loop for sourcerer (web UI).

Graph structure:
    START → chat_node → tools_condition → tools → chat_node (loop)
                                        ↘ END (no tool calls)

Talks to the MCP server (src/mcp_server.py) as a client over Streamable
HTTP — it never imports src/mcp.py directly, so this process and the MCP
server can be deployed and scaled independently.

Used by src/api.py, which exposes stream_reply() over Server-Sent Events.
"""

import logging
import os
from typing import Annotated, AsyncIterator, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src import db

load_dotenv()

logger = logging.getLogger("sourcerer.llm")

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
MESSAGE_HISTORY_LIMIT = int(os.getenv("MESSAGE_HISTORY_LIMIT", "20"))

SYSTEM_PROMPT = """You have access to tools for tracking job applications, reading items, links, and todos.
When you choose to call a tool, do not narrate status updates — just call it.
After tools run, return a clear, well-formatted final answer using markdown where it helps (lists, bold)."""

_mcp_connection = {
    "transport": "streamable_http",
    "url": MCP_SERVER_URL,
}


## --- Graph State --- ##


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


## --- Internal Helpers --- ##


def _history_to_lc_messages(history: list[dict]) -> list[BaseMessage]:
    """Convert db message rows to LangChain message objects."""
    lc_messages = []
    for row in history:
        direction = row["direction"]
        content = row["content"]

        if direction == "inbound":
            lc_messages.append(HumanMessage(content=content))
        elif direction == "outbound":
            lc_messages.append(AIMessage(content=content))
        elif direction == "summary":
            lc_messages.append(
                SystemMessage(content=f"[Conversation summary: {content}]")
            )
    return lc_messages


def _build_messages(user_text: str) -> list[BaseMessage]:
    """Assemble system prompt + recent history + the new user message."""
    history = db.get_recent_messages(limit=MESSAGE_HISTORY_LIMIT)
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    messages += _history_to_lc_messages(history)

    if not messages or not (
        isinstance(messages[-1], HumanMessage) and messages[-1].content == user_text
    ):
        messages.append(HumanMessage(content=user_text))

    return messages


async def _build_graph(mcp_client: MultiServerMCPClient) -> StateGraph:
    """Build and compile the LangGraph StateGraph for one request.

    As of langchain-mcp-adapters 0.1.0, MultiServerMCPClient opens a
    short-lived session per tool call internally — there's no persistent
    session to manage here, so mcp_client can just be a plain instance.
    """
    tools = await mcp_client.get_tools()
    llm = ChatGroq(api_key=GROQ_API_KEY, model=GROQ_MODEL)
    llm_with_tools = llm.bind_tools(tools)

    async def chat_node(state: ChatState):
        gathered = None
        async for chunk in llm_with_tools.astream(state["messages"]):
            gathered = chunk if gathered is None else gathered + chunk
        return {"messages": [gathered]}

    tool_node = ToolNode(tools)

    graph = StateGraph(ChatState)
    graph.add_node("chat_node", chat_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "chat_node")
    graph.add_conditional_edges("chat_node", tools_condition)
    graph.add_edge("tools", "chat_node")

    return graph.compile()


## --- Public Interface --- ##


async def handle_message(user_text: str) -> str:
    """Run the LangGraph loop for one inbound message and return the full reply.

    Non-streaming — kept for scripts/tests. src/api.py uses stream_reply()
    instead so the browser sees tokens as they're generated.
    """
    db.log_message("inbound", user_text)
    messages = _build_messages(user_text)

    mcp_client = MultiServerMCPClient({"sourcerer": _mcp_connection})
    graph = await _build_graph(mcp_client)
    result = await graph.ainvoke({"messages": messages})

    reply = ""
    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage) and message.content:
            reply = message.content
            break

    if not reply:
        reply = "I wasn't able to generate a response. Please try again."

    db.log_message("outbound", reply)
    return reply


async def stream_reply(user_text: str) -> AsyncIterator[dict]:
    """Run the agent loop for one inbound message, yielding SSE-ready events.

    Yields dicts of the form:
      {"type": "token", "content": str}   — a chunk of the model's reply
      {"type": "tool_call", "name": str}  — a tool the agent just invoked
      {"type": "done"}                    — stream finished
    """
    db.log_message("inbound", user_text)
    messages = _build_messages(user_text)

    full_reply = ""

    mcp_client = MultiServerMCPClient({"sourcerer": _mcp_connection})
    graph = await _build_graph(mcp_client)

    async for event in graph.astream_events({"messages": messages}, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            token = chunk.content or ""
            if token:
                full_reply += token
                yield {"type": "token", "content": token}

        elif kind == "on_chat_model_end" and not full_reply:
            # Safety net: if no token-level events fired for some reason
            # (provider/version quirk), fall back to the full message here
            # instead of silently showing nothing.
            output = event["data"].get("output")
            content = getattr(output, "content", "") or ""
            if content:
                full_reply += content
                yield {"type": "token", "content": content}

        elif kind == "on_tool_start":
            yield {"type": "tool_call", "name": event.get("name", "tool")}

    if not full_reply:
        full_reply = "I wasn't able to generate a response. Please try again."
        yield {"type": "token", "content": full_reply}

    db.log_message("outbound", full_reply)
    yield {"type": "done"}


async def summarizer_fn(messages: list[dict]) -> str:
    """Summarize a list of message dicts into a compact string.

    Injected into db.summarize_and_trim(). Kept here so llm.py is the
    only file that ever touches the LLM client directly.
    """
    formatted = "\n".join(f"[{m['direction']}] {m['content']}" for m in messages)
    prompt = (
        "Summarize the following conversation history concisely, "
        "preserving key facts about job applications, reading items, "
        "links, todos, and any decisions made. Be brief.\n\n"
        f"{formatted}"
    )
    model = ChatGroq(api_key=GROQ_API_KEY, model=GROQ_MODEL)
    response = await model.ainvoke([HumanMessage(content=prompt)])
    return response.content or ""