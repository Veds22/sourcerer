import { ScrollText } from "lucide-react";

/** Renders one invoked tool as a quiet "ledger" line, not a generic spinner. */
export default function ToolLedgerEntry({ name }) {
  return (
    <div className="flex items-center gap-2 border-l-2 border-gold-600/50 pl-2.5 py-0.5">
      <ScrollText size={12} className="shrink-0 text-gold-500" />
      <span className="font-mono text-[11px] text-parchment-500">
        invoked <span className="text-gold-400">{name}</span>
      </span>
    </div>
  );
}
