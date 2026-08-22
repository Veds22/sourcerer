import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble.jsx";

export default function ChatWindow({ messages }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
        <p className="font-display text-lg text-parchment-300">
          The ledger is empty.
        </p>
        <p className="max-w-sm font-mono text-xs text-parchment-500">
          Try: "add a todo to follow up with Acme on Friday" or "what's the
          status of my applications?"
        </p>
      </div>
    );
  }

  return (
    <div className="chat-scroll flex-1 space-y-4 overflow-y-auto px-6 py-6">
      {messages.map((m) => (
        <MessageBubble
          key={m.id}
          role={m.role}
          content={m.content}
          toolCalls={m.toolCalls}
          isStreaming={m.isStreaming}
        />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
