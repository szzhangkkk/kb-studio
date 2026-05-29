"use client";

interface StatusBarProps {
  statusKB: string;
  statusLLM: string;
  statusEmb: string;
}

export default function StatusBar({ statusKB, statusLLM, statusEmb }: StatusBarProps) {
  return (
    <div className="h-6 bg-cyber-surface flex items-center justify-between px-3 text-[11px] shrink-0 select-none" style={{ borderTop: "2px solid var(--color-cyber-border)" }}>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-tiffany">
          <span className="w-1.5 h-1.5 rounded-full bg-cyber-green" style={{ boxShadow: "0 0 4px var(--color-cyber-glow-green-strong)" }} />
          KB-Studio v0.1.0
        </span>
        <span className="text-cyber-text-muted">|</span>
        <span className="text-cyber-text-muted">CYBER//MODE</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-cyber-text-dim">{statusKB}</span>
        <span className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${statusLLM.includes("✓") ? "bg-cyber-green" : "bg-cyber-red"}`}
                style={{ boxShadow: statusLLM.includes("✓") ? "0 0 4px var(--color-cyber-glow-green-strong)" : "0 0 4px var(--color-cyber-glow-red)" }} />
          <span className="text-cyber-text-dim">{statusLLM}</span>
        </span>
        <span className="flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${statusEmb.includes("✗") ? "bg-cyber-red" : "bg-tiffany"}`}
                style={{ boxShadow: statusEmb.includes("✗") ? "0 0 4px var(--color-cyber-glow-red)" : "0 0 4px var(--color-cyber-glow-green-strong)" }} />
          <span className="text-cyber-text-dim">{statusEmb}</span>
        </span>
      </div>
    </div>
  );
}
