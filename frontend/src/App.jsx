import { useCallback, useState } from "react";
import ChatInput from "./components/ChatInput.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import Header from "./components/Header.jsx";
import { streamChat } from "./lib/api.js";

let idCounter = 0;
const nextId = () => `m-${++idCounter}-${Date.now()}`;

export default function App() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);

  const updateLastAssistant = (updater) => {
    setMessages((prev) => {
      const next = [...prev];
      const lastIdx = next.length - 1;
      next[lastIdx] = updater(next[lastIdx]);
      return next;
    });
  };

  const handleSend = useCallback(async (text) => {
    const userMsg = { id: nextId(), role: "user", content: text };
    const assistantMsg = {
      id: nextId(),
      role: "assistant",
      content: "",
      toolCalls: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    await streamChat(text, {
      onToken: (chunk) => {
        updateLastAssistant((m) => ({ ...m, content: m.content + chunk }));
      },
      onToolCall: (name) => {
        updateLastAssistant((m) => ({ ...m, toolCalls: [...m.toolCalls, name] }));
      },
      onDone: () => {
        updateLastAssistant((m) => ({ ...m, isStreaming: false }));
        setIsStreaming(false);
      },
      onError: (err) => {
        updateLastAssistant((m) => ({
          ...m,
          content: m.content || `Something went wrong: ${err.message}`,
          isStreaming: false,
        }));
        setIsStreaming(false);
      },
    });
  }, []);

  return (
    <div className="flex h-screen flex-col bg-ink-900">
      <Header />
      <ChatWindow messages={messages} />
      <ChatInput onSend={handleSend} disabled={isStreaming} />
    </div>
  );
}
