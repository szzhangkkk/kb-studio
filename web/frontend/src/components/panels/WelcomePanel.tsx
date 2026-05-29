"use client";

interface WelcomePanelProps {
  onNavigate: (panel: string) => void;
}

export default function WelcomePanel({ onNavigate }: WelcomePanelProps) {
  return (
    <div className="h-full flex flex-col items-center justify-center relative overflow-hidden">
      {/* Grid background */}
      <div className="absolute inset-0 cyber-grid-bg" />

      {/* Radial glow */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 45%, var(--color-tiffany-glow), transparent 70%), radial-gradient(ellipse 50% 40% at 25% 65%, var(--color-lavender-glow), transparent 60%), radial-gradient(ellipse 30% 30% at 75% 30%, var(--color-tiffany-glow), transparent 50%)",
        }}
      />

      <div className="relative z-10 flex flex-col items-center text-center px-8 max-w-2xl" style={{ animation: "fade-in 0.6s ease-out" }}>
        {/* Logo */}
        <div
          className="mb-8 w-20 h-20 flex items-center justify-center border-2 border-tiffany rounded-lg"
          style={{
            animation: "float-y 3s ease-in-out infinite, glow-breathe 3s ease-in-out infinite",
            clipPath: "polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 12px 100%, 0 calc(100% - 12px))",
          }}
        >
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tiffany">
            <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
            <path d="M8 7h8M8 11h5" />
          </svg>
        </div>

        {/* Title */}
        <h1
          className="text-3xl font-bold mb-2 text-glow-tiffany"
          style={{ fontFamily: "var(--font-display)", color: "var(--color-tiffany)" }}
        >
          KB-STUDIO
        </h1>
        <p className="text-sm text-cyber-text-dim tracking-[3px] uppercase mb-2">
          Knowledge Base Q&A Platform
        </p>
        <p className="text-xs text-cyber-text-muted mb-10 tracking-wide">
          上传文档 → 配置 Prompt → 智能问答
        </p>

        {/* Cards */}
        <div className="grid grid-cols-3 gap-4 w-full mb-10">
          {[
            { id: "kb", label: "知识库", desc: "创建和管理", icon: DatabaseIcon, color: "tiffany" },
            { id: "config", label: "配置", desc: "设置 LLM", icon: SettingsIcon, color: "lavender" },
            { id: "chat", label: "对话", desc: "开始问答", icon: ChatIcon, color: "tiffany" },
          ].map(({ id, label, desc, icon: Icon, color }) => (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              className={`cyber-card group cursor-pointer text-left p-5 hover:border-${color}-dim`}
            >
              <div className={`mb-3 text-${color}`} style={{ animation: "float-y 4s ease-in-out infinite" }}>
                <Icon />
              </div>
              <div className="text-sm font-semibold text-cyber-text mb-1">{label}</div>
              <div className="text-[11px] text-cyber-text-muted">{desc}</div>
              <div className="mt-3 text-[10px] text-cyber-text-muted group-hover:text-tiffany transition-colors">
                ENTER →
              </div>
            </button>
          ))}
        </div>

        {/* Shortcuts */}
        <div className="flex items-center gap-8 text-[11px] text-cyber-text-muted">
          <div className="flex items-center gap-2">
            <kbd className="px-2 py-1 bg-cyber-surface border border-cyber-border rounded text-[10px] text-tiffany">Ctrl</kbd>
            <span>+</span>
            <kbd className="px-2 py-1 bg-cyber-surface border border-cyber-border rounded text-[10px] text-tiffany">Enter</kbd>
            <span className="text-cyber-text-dim">发送消息</span>
          </div>
          <div className="flex items-center gap-2">
            <kbd className="px-2 py-1 bg-cyber-surface border border-cyber-border rounded text-[10px] text-lavender">Ctrl</kbd>
            <span>+</span>
            <kbd className="px-2 py-1 bg-cyber-surface border border-cyber-border rounded text-[10px] text-lavender">Shift</kbd>
            <span>+</span>
            <kbd className="px-2 py-1 bg-cyber-surface border border-cyber-border rounded text-[10px] text-lavender">P</kbd>
            <span className="text-cyber-text-dim">切换面板</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function DatabaseIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.73 12.73l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}
