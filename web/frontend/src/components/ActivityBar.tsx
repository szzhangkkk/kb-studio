"use client";

import { useTheme } from "@/hooks/useTheme";

interface ActivityBarProps {
  activePanel: string;
  onPanelChange: (panel: string) => void;
  kbCount: number;
  unreadNotifications?: number;
}

const navItems = [
  { id: "welcome", label: "欢迎", icon: HomeIcon },
  { id: "kb", label: "知识库", icon: DatabaseIcon },
  { id: "chat", label: "对话", icon: ChatIcon },
  { id: "tools", label: "工具", icon: ToolsIcon },
  { id: "butler", label: "管家", icon: ButlerIcon },
  { id: "config", label: "配置", icon: SettingsIcon },
  { id: "__theme__", label: "主题", icon: ThemeIcon },
];

export default function ActivityBar({
  activePanel,
  onPanelChange,
  kbCount,
  unreadNotifications = 0,
}: ActivityBarProps) {
  const { theme, toggle } = useTheme();
  return (
    <div className="w-12 flex flex-col items-center py-3 shrink-0" style={{ background: "linear-gradient(180deg, var(--color-cyber-activity-bg-start), var(--color-cyber-activity-bg-end))", borderRight: "2px solid var(--color-cyber-activity-border)" }}>
      {/* Logo */}
      <div className="mb-4 w-8 h-8 flex items-center justify-center border border-tiffany rounded"
           style={{ boxShadow: "0 0 8px var(--color-cyber-glow-tiffany-activity)" }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" className="text-tiffany">
          <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
        </svg>
      </div>

      <div className="w-8 h-px mb-4" style={{ background: "var(--color-cyber-activity-divider)" }} />

      {/* Nav Items */}
      <div className="flex flex-col items-center gap-1 flex-1">
        {navItems.map(({ id, label, icon: Icon }) => {
          if (id === "__theme__") {
            return (
              <div key={id} className="mt-auto">
                <div className="w-8 h-px mb-1" style={{ background: "var(--color-cyber-activity-divider)" }} />
                <button onClick={toggle}
                  className="relative w-10 h-10 flex items-center justify-center rounded transition-all duration-200 text-cyber-text-muted hover:text-tiffany hover:bg-tiffany-glow group"
                  title={theme === "dark" ? "切换到浅色" : "切换到深色"}>
                  {theme === "dark" ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="12" cy="12" r="5" /><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.73 12.73l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
                    </svg>
                  )}
                  <div className="absolute left-full ml-2 px-2 py-1 bg-cyber-card border border-cyber-border text-xs text-cyber-text whitespace-nowrap rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50"
                       style={{ boxShadow: "0 0 8px var(--color-tiffany-glow)" }}>
                    {theme === "dark" ? "浅色模式" : "深色模式"}
                  </div>
                </button>
              </div>
            );
          }
          return (
            <button
              key={id}
              onClick={() => onPanelChange(id)}
              className={`relative w-10 h-10 flex items-center justify-center rounded transition-all duration-200 group
                ${
                  activePanel === id
                    ? "text-tiffany bg-tiffany-glow"
                    : "text-cyber-text-muted hover:text-lavender hover:bg-lavender-glow"
                }`}
              title={label}
            >
              {activePanel === id && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5 bg-tiffany rounded-r"
                     style={{ boxShadow: "0 0 6px var(--color-cyber-glow-tiffany-activity)" }} />
              )}
              <Icon />
              {id === "kb" && kbCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center text-[9px] font-bold bg-tiffany text-cyber-bg rounded-full">
                  {kbCount}
                </span>
              )}
              {id === "butler" && unreadNotifications > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center text-[9px] font-bold bg-cyber-red text-white rounded-full">
                  {unreadNotifications > 9 ? "9+" : unreadNotifications}
                </span>
              )}
              {/* Tooltip */}
              <div className="absolute left-full ml-2 px-2 py-1 bg-cyber-card border border-cyber-border text-xs text-cyber-text whitespace-nowrap rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50"
                   style={{ boxShadow: "0 0 8px var(--color-tiffany-glow)" }}>
                {label}
              </div>
            </button>
          );
        })}
      </div>

      {/* Status dot */}
      <div className="flex flex-col items-center gap-2 pt-2">
        <div className="w-2 h-2 rounded-full bg-cyber-green" style={{ boxShadow: "0 0 6px var(--color-cyber-glow-green)" }} />
      </div>
    </div>
  );
}

// SVG Icons
function HomeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1h-2z" />
    </svg>
  );
}

function DatabaseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function SettingsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.73 12.73l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}

function ToolsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function ButlerIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

function ThemeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="5" />
      <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.73 12.73l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
    </svg>
  );
}
