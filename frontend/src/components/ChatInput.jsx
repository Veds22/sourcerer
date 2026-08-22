import { ArrowUp } from "lucide-react";
import { useState } from "react";

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-ink-700 p-4">
      <div className="flex items-end gap-2 rounded-2xl border border-ink-600 bg-ink-800 px-3 py-2 focus-within:border-gold-500/60">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask about your applications, reading list, links, or todos…"
          className="max-h-32 flex-1 resize-none bg-transparent font-mono text-[13.5px] text-parchment-100 placeholder:text-parchment-500 focus:outline-none"
          disabled={disabled}
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gold-500 text-ink-950 transition-opacity disabled:opacity-30"
        >
          <ArrowUp size={16} />
        </button>
      </div>
    </div>
  );
}
