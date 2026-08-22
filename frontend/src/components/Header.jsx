import { Sparkles } from "lucide-react";

export default function Header() {
  return (
    <header className="flex items-center justify-between border-b border-ink-700 px-6 py-4">
      <div className="flex items-baseline gap-2">
        <h1 className="font-display text-2xl font-medium tracking-tight text-parchment-100">
          Sourcerer
        </h1>
        <span className="font-mono text-xs text-parchment-500">
          job apps · reading · links · todos
        </span>
      </div>
      <div className="flex items-center gap-1.5 rounded-full border border-ink-600 px-3 py-1">
        <Sparkles size={13} className="text-gold-500" />
        <span className="font-mono text-[11px] text-parchment-500">
          agent online
        </span>
      </div>
    </header>
  );
}
