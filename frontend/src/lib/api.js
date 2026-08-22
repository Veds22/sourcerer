const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

/**
 * POST a message to /chat and stream the SSE response.
 *
 * The backend (sse-starlette) sends blocks like:
 *   event: message
 *   data: {"type": "token", "content": "..."}
 *
 * fetch + ReadableStream is used instead of EventSource because
 * EventSource can't send a POST body — this parses the same wire
 * format by hand.
 */
export async function streamChat(message, { onToken, onToolCall, onDone, onError }) {
  let res;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  } catch (err) {
    onError?.(err);
    return;
  }

  if (!res.ok || !res.body) {
    onError?.(new Error(`Request failed: ${res.status}`));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const processBlock = (block) => {
    const dataLine = block.split(/\r?\n/).find((line) => line.startsWith("data:"));
    if (!dataLine) return;

    const jsonStr = dataLine.slice(5).trim();
    if (!jsonStr) return;

    let evt;
    try {
      evt = JSON.parse(jsonStr);
    } catch {
      return;
    }

    switch (evt.type) {
      case "token":
        onToken?.(evt.content);
        break;
      case "tool_call":
        onToolCall?.(evt.name);
        break;
      case "done":
        onDone?.();
        break;
      case "error":
        onError?.(new Error(evt.message));
        break;
      default:
        break;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // sse-starlette (and the SSE spec in general) may use \r\n or \n as the
    // line separator, so split on either — a plain "\n\n" check misses
    // "\r\n\r\n" entirely since it has no adjacent \n\n substring.
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? ""; // last chunk may be incomplete, keep for next read

    for (const block of blocks) {
      processBlock(block);
    }
  }

  // Process whatever's left in the buffer once the stream closes — the
  // final event may not be followed by a trailing blank line before EOF.
  if (buffer.trim()) {
    processBlock(buffer);
  }
}

export async function fetchHistory(limit = 50) {
  const res = await fetch(`${API_BASE}/history?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load history: ${res.status}`);
  return res.json();
}