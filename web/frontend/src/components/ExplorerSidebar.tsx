"use client";

import { useState, useEffect } from "react";
import { KnowledgeBase, DocumentInfo, ToolDefinition } from "@/hooks/useKBStudio";

interface ExplorerSidebarProps {
  activePanel: string;
  kbList: KnowledgeBase[];
  currentKB: string | null;
  onSelectKB: (name: string) => void;
  selectedKBForDocs: string | null;
  onLoadDocuments?: (kbName: string) => Promise<DocumentInfo[]>;
  toolList?: ToolDefinition[];
  selectedTool?: string | null;
  onSelectTool?: (name: string) => void;
}

const quickStart = [
  { step: "01", text: "配置 LLM 提供商" },
  { step: "02", text: "创建知识库" },
  { step: "03", text: "上传文档" },
  { step: "04", text: "开始对话" },
];

export default function ExplorerSidebar({
  activePanel,
  kbList,
  currentKB,
  onSelectKB,
  selectedKBForDocs,
  onLoadDocuments,
  toolList,
  selectedTool,
  onSelectTool,
}: ExplorerSidebarProps) {
  const sectionTitle = {
    welcome: "QUICK_START",
    kb: selectedKBForDocs ? "DOCUMENTS" : "KNOWLEDGE_BASES",
    chat: "EXPLORER",
    tools: "TOOLS",
    config: "SYSTEM_CONFIG",
  }[activePanel] || "EXPLORER";

  return (
    <div className="w-60 bg-cyber-surface flex flex-col shrink-0 overflow-hidden" style={{ borderRight: "2px solid var(--color-cyber-border)" }}>
      {/* Header */}
      <div className="h-9 flex items-center px-3 text-[10px] tracking-[2px] text-cyber-text-muted uppercase" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
        {sectionTitle}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2">
        {activePanel === "welcome" && <WelcomeSidebar />}
        {activePanel === "kb" && (selectedKBForDocs && onLoadDocuments
          ? <DocumentSidebar kbName={selectedKBForDocs} onLoadDocuments={onLoadDocuments} />
          : <KBSidebar kbList={kbList} onSelectKB={onSelectKB} />
        )}
        {activePanel === "chat" && (
          <ChatSidebar kbList={kbList} currentKB={currentKB} onSelectKB={onSelectKB} />
        )}
        {activePanel === "config" && <ConfigSidebar />}
        {activePanel === "tools" && toolList && onSelectTool && (
          <ToolsSidebar toolList={toolList} selectedTool={selectedTool} onSelectTool={onSelectTool} />
        )}
      </div>
    </div>
  );
}

function WelcomeSidebar() {
  return (
    <div className="space-y-1">
      {quickStart.map(({ step, text }) => (
        <div key={step} className="flex items-center gap-2 px-2 py-1.5 text-[12px] text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow rounded transition-colors cursor-default">
          <span className="text-tiffany font-bold text-[10px] w-5">{step}</span>
          <span>{text}</span>
        </div>
      ))}
      <div className="mt-4 px-2">
        <div className="text-[10px] text-cyber-text-muted tracking-wider mb-2">SHORTCUTS</div>
        <div className="space-y-1 text-[11px] text-cyber-text-dim">
          <div className="flex justify-between"><span>发送消息</span><kbd className="px-1.5 py-0.5 bg-cyber-bg border border-cyber-border rounded text-[9px] text-tiffany">Ctrl+Enter</kbd></div>
          <div className="flex justify-between"><span>切换面板</span><kbd className="px-1.5 py-0.5 bg-cyber-bg border border-cyber-border rounded text-[9px] text-tiffany">Ctrl+Shift+P</kbd></div>
        </div>
      </div>
    </div>
  );
}

function KBSidebar({ kbList, onSelectKB }: { kbList: KnowledgeBase[]; onSelectKB: (name: string) => void }) {
  return (
    <div className="space-y-0.5">
      <div className="px-2 py-1 text-[10px] text-cyber-text-muted tracking-wider">ALL_BASES ({kbList.length})</div>
      {kbList.map((kb) => (
        <button key={kb.name} onClick={() => onSelectKB(kb.name)} className="w-full flex items-center gap-2 px-2 py-1.5 text-[12px] text-cyber-text-dim hover:text-tiffany hover:bg-tiffany-glow rounded transition-colors text-left">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="shrink-0 text-lavender">
            <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          <span className="truncate">{kb.name}</span>
          <span className="ml-auto text-[9px] text-cyber-text-muted">{kb.doc_count}</span>
        </button>
      ))}
      {kbList.length === 0 && <div className="px-2 py-4 text-[11px] text-cyber-text-muted text-center">暂无知识库</div>}
    </div>
  );
}

function DocumentSidebar({ kbName, onLoadDocuments }: { kbName: string; onLoadDocuments: (kbName: string) => Promise<DocumentInfo[]> }) {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);

  useEffect(() => {
    onLoadDocuments(kbName).then(setDocs);
  }, [kbName, onLoadDocuments]);

  return (
    <div className="space-y-0.5">
      <div className="px-2 py-1 text-[10px] text-cyber-text-muted tracking-wider">{kbName}</div>
      {docs.map((doc) => (
        <div key={doc.filename} className="flex items-center gap-2 px-2 py-1.5 text-[11px] text-cyber-text-dim cursor-default">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="shrink-0 text-tiffany">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" />
          </svg>
          <span className="truncate flex-1">{doc.filename}</span>
          <span className="text-[9px] text-cyber-text-muted">{doc.chunk_count}</span>
        </div>
      ))}
      {docs.length === 0 && <div className="px-2 py-4 text-[11px] text-cyber-text-muted text-center">暂无文档</div>}
    </div>
  );
}

function ChatSidebar({ kbList, currentKB, onSelectKB }: { kbList: KnowledgeBase[]; currentKB: string | null; onSelectKB: (name: string) => void }) {
  return (
    <div className="space-y-0.5">
      <div className="px-2 py-1 text-[10px] text-cyber-text-muted tracking-wider">KNOWLEDGE_BASES</div>
      {kbList.map((kb) => (
        <button key={kb.name} onClick={() => onSelectKB(kb.name)} className={`w-full flex items-center gap-2 px-2 py-1.5 text-[12px] rounded transition-colors text-left ${currentKB === kb.name ? "text-tiffany bg-tiffany-glow" : "text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow"}`}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="shrink-0">
            <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
          <span className="truncate">{kb.name}</span>
        </button>
      ))}
      {kbList.length === 0 && <div className="px-2 py-4 text-[11px] text-cyber-text-muted text-center">暂无知识库</div>}
    </div>
  );
}

function ConfigSidebar() {
  const items = [
    { icon: "🔌", label: "连接测试", desc: "LLM & Embedding" },
    { icon: "🤖", label: "LLM 提供商", desc: "7 种提供商" },
    { icon: "⚙️", label: "LLM 配置", desc: "模型 & API Key" },
    { icon: "📐", label: "Embedding", desc: "向量模型配置" },
  ];
  return (
    <div className="space-y-0.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2 px-2 py-1.5 text-[12px] text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow rounded transition-colors cursor-default">
          <span className="text-sm">{item.icon}</span>
          <div><div>{item.label}</div><div className="text-[10px] text-cyber-text-muted">{item.desc}</div></div>
        </div>
      ))}
    </div>
  );
}

function ToolsSidebar({ toolList, selectedTool, onSelectTool }: { toolList: ToolDefinition[]; selectedTool?: string | null; onSelectTool: (name: string) => void }) {
  const builtin = toolList.filter(t => t.source === "builtin");
  const custom = toolList.filter(t => t.source !== "builtin");

  return (
    <div className="space-y-1">
      <div className="px-2 py-1 text-[10px] text-cyber-text-muted tracking-wider">BUILTIN ({builtin.length})</div>
      {builtin.map((t) => (
        <button key={t.name} onClick={() => onSelectTool(t.name)}
          className={`w-full flex items-center gap-2 px-2 py-1.5 text-[11px] rounded transition-colors text-left ${selectedTool === t.name ? "text-tiffany bg-tiffany-glow" : "text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow"}`}>
          <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.enabled ? "bg-cyber-green" : "bg-cyber-text-muted"}`} />
          <span className="truncate font-mono">{t.name}</span>
        </button>
      ))}
      {custom.length > 0 && (
        <>
          <div className="px-2 py-1 text-[10px] text-cyber-text-muted tracking-wider mt-2">CUSTOM ({custom.length})</div>
          {custom.map((t) => (
            <button key={t.name} onClick={() => onSelectTool(t.name)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 text-[11px] rounded transition-colors text-left ${selectedTool === t.name ? "text-tiffany bg-tiffany-glow" : "text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow"}`}>
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${t.enabled ? "bg-cyber-green" : "bg-cyber-text-muted"}`} />
              <span className="truncate font-mono">{t.name}</span>
              <span className="ml-auto px-1 py-0.5 rounded text-[8px] bg-lavender/20 text-lavender">{t.source}</span>
            </button>
          ))}
        </>
      )}
      {toolList.length === 0 && <div className="px-2 py-4 text-[11px] text-cyber-text-muted text-center">暂无工具</div>}
    </div>
  );
}
