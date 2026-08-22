import ToolLedgerEntry from "./ToolLedgerEntry.jsx";

export default function MessageBubble({ role, content, toolCalls, isStreaming }) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1.5`}>
        {!isUser && toolCalls?.length > 0 && (
          <div className="mb-1 flex flex-col gap-0.5">
            {toolCalls.map((name, i) => (
              <ToolLedgerEntry key={`${name}-${i}`} name={name} />
            ))}
          </div>
        )}

        <div
          className={
            isUser
              ? "rounded-2xl rounded-tr-sm bg-gold-500 px-4 py-2.5 text-ink-950"
              : "rounded-2xl rounded-tl-sm border border-ink-700 bg-ink-800 px-4 py-2.5 text-parchment-100"
          }
        >
          <p className="whitespace-pre-wrap font-mono text-[13.5px] leading-relaxed">
            {content}
            {isStreaming && (
              <span className="ml-0.5 inline-block h-3.5 w-1.5 translate-y-0.5 animate-pulse_glow bg-arcane-400 align-middle" />
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
