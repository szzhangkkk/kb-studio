"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { KnowledgeBase, ChatResponse, RetrievalResult, SearchResult, Conversation, ConversationMessage, MemoryData, PipelineConfig, PipelineResult } from "@/hooks/useKBStudio";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  chunksUsed?: number;
  retrievalResults?: RetrievalResult[];
}

interface ChatPanelProps {
  kbList: KnowledgeBase[];
  currentKB: string | null;
  onSelectKB: (name: string) => void;
  onSendMessage: (question: string, conversationId?: string) => Promise<ChatResponse | null>;
  onUploadFile: (file: File) => Promise<{ success: boolean; error?: string; chunksAdded?: number }>;
  onUploadURL?: (url: string) => Promise<{ success: boolean; error?: string; chunksAdded?: number }>;
  onClearHistory: () => Promise<void>;
  onSearch?: (kbName: string, query: string, params: Record<string, unknown>) => Promise<SearchResult | null>;
  onLoadConversations?: (kbName: string) => Promise<{ conversations: Conversation[]; active_conversation_id: string | null }>;
  onCreateConversation?: (kbName: string, name: string) => Promise<Conversation>;
  onDeleteConversation?: (kbName: string, convId: string) => Promise<void>;
  onGetConversationHistory?: (kbName: string, convId: string) => Promise<ConversationMessage[]>;
  onRenameConversation?: (kbName: string, convId: string, name: string) => Promise<void>;
  onExportConversation?: (kbName: string, convId: string) => Promise<string>;
  onSetActiveConversation?: (kbName: string, convId: string) => Promise<void>;
  onLoadMemory?: (kbName: string) => Promise<MemoryData>;
  onAddMemory?: (kbName: string, content: string, category: string, importance: number) => Promise<void>;
  onDeleteMemory?: (kbName: string, entryId: string) => Promise<void>;
  onLoadPipeline?: (kbName: string) => Promise<PipelineConfig>;
  onUpdatePipeline?: (kbName: string, config: PipelineConfig) => Promise<void>;
  onPipelineChat?: (kbName: string, question: string, conversationId?: string) => Promise<PipelineResult | null>;
}

export default function ChatPanel({
  kbList, currentKB, onSelectKB, onSendMessage, onUploadFile, onUploadURL, onClearHistory, onSearch,
  onLoadConversations, onCreateConversation, onDeleteConversation,
  onGetConversationHistory, onRenameConversation, onExportConversation, onSetActiveConversation,
  onLoadMemory, onAddMemory, onDeleteMemory,
  onLoadPipeline, onUpdatePipeline, onPipelineChat,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedResult, setSelectedResult] = useState<RetrievalResult | null>(null);
  const [tab, setTab] = useState<"chat" | "search">("chat");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [urlInput, setUrlInput] = useState("");
  const [urlUploading, setUrlUploading] = useState(false);

  // Conversation state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [renamingConv, setRenamingConv] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // Memory state
  const [memory, setMemory] = useState<MemoryData>({ entries: [], summary: "" });
  const [sidebarTab, setSidebarTab] = useState<"conversations" | "memory">("conversations");
  const [newMemoryContent, setNewMemoryContent] = useState("");

  // Pipeline state
  const [pipelineEnabled, setPipelineEnabled] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState<{ name: string; status: string; output_preview: string; latency: number }[]>([]);
  const [showPipelineSteps, setShowPipelineSteps] = useState(false);

  // Search test state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchTopK, setSearchTopK] = useState(5);
  const [searchStrategy, setSearchStrategy] = useState("hybrid");
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  // Load conversations when KB changes
  useEffect(() => {
    if (currentKB && onLoadConversations) {
      onLoadConversations(currentKB).then((data) => {
        setConversations(data.conversations || []);
        setActiveConvId(data.active_conversation_id);
        if (data.active_conversation_id && onGetConversationHistory) {
          onGetConversationHistory(currentKB, data.active_conversation_id).then((msgs) => {
            if (msgs.length > 0) {
              setMessages(msgs.map((m) => ({ role: m.role, content: m.content, sources: m.sources })));
            } else {
              setMessages([{ role: "assistant", content: `已连接知识库: ${currentKB}，可以开始提问。` }]);
            }
          });
        } else if (data.conversations.length === 0 && onCreateConversation) {
          // Auto-create default conversation
          onCreateConversation(currentKB, "Default").then((conv) => {
            setConversations([conv]);
            setActiveConvId(conv.id);
            setMessages([{ role: "assistant", content: `已连接知识库: ${currentKB}，可以开始提问。` }]);
          });
        } else {
          setMessages([{ role: "assistant", content: `已连接知识库: ${currentKB}，可以开始提问。` }]);
        }
      });
    } else {
      setConversations([]);
      setActiveConvId(null);
      setMessages([{ role: "assistant", content: "请选择一个知识库开始对话。" }]);
    }
  }, [currentKB, onLoadConversations, onCreateConversation, onGetConversationHistory]);

  // Load memory and pipeline when KB changes
  useEffect(() => {
    if (currentKB) {
      if (onLoadMemory) onLoadMemory(currentKB).then(setMemory);
      if (onLoadPipeline) onLoadPipeline(currentKB).then((cfg) => setPipelineEnabled(cfg.enabled));
    }
  }, [currentKB, onLoadMemory, onLoadPipeline]);

  const handleSend = async () => {
    if (!input.trim() || !currentKB || loading) return;
    const question = input;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    setPipelineSteps([]);

    if (pipelineEnabled && onPipelineChat) {
      const result = await onPipelineChat(currentKB, question, activeConvId || undefined);
      setLoading(false);
      if (result) {
        setPipelineSteps(result.steps_log || []);
        let content = result.answer;
        if (result.review) content += `\n\n---\n审核：${result.review}`;
        setMessages((prev) => [...prev, {
          role: "assistant", content,
          sources: result.sources,
          chunksUsed: result.retrieval_results?.length || 0,
          retrievalResults: result.retrieval_results,
        }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "流水线执行失败。" }]);
      }
    } else {
      const data = await onSendMessage(question, activeConvId || undefined);
      setLoading(false);
      if (data) {
        setMessages((prev) => [...prev, {
          role: "assistant", content: data.answer,
          sources: data.sources, chunksUsed: data.chunks_used,
          retrievalResults: data.retrieval_results,
        }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "发送失败。" }]);
      }
    }

    // Refresh conversation list and memory
    if (activeConvId && onLoadConversations && currentKB) {
      onLoadConversations(currentKB).then((d) => setConversations(d.conversations || []));
    }
    if (onLoadMemory && currentKB) {
      onLoadMemory(currentKB).then(setMemory);
    }
  };

  const handleNewConversation = async () => {
    if (!currentKB || !onCreateConversation) return;
    const conv = await onCreateConversation(currentKB, "New Chat");
    setConversations((prev) => [...prev, conv]);
    setActiveConvId(conv.id);
    setMessages([{ role: "assistant", content: "新对话已创建。" }]);
  };

  const handleSwitchConversation = async (convId: string) => {
    if (!currentKB || !onGetConversationHistory || !onSetActiveConversation) return;
    setActiveConvId(convId);
    await onSetActiveConversation(currentKB, convId);
    const msgs = await onGetConversationHistory(currentKB, convId);
    if (msgs.length > 0) {
      setMessages(msgs.map((m) => ({ role: m.role, content: m.content, sources: m.sources })));
    } else {
      setMessages([{ role: "assistant", content: "空对话，开始提问吧。" }]);
    }
  };

  const handleDeleteConversation = async (convId: string) => {
    if (!currentKB || !onDeleteConversation) return;
    if (!confirm("确定删除此对话？")) return;
    await onDeleteConversation(currentKB, convId);
    setConversations((prev) => prev.filter((c) => c.id !== convId));
    if (activeConvId === convId) {
      const remaining = conversations.filter((c) => c.id !== convId);
      if (remaining.length > 0) {
        handleSwitchConversation(remaining[0].id);
      } else {
        handleNewConversation();
      }
    }
  };

  const handleRename = async (convId: string) => {
    if (!currentKB || !onRenameConversation || !renameValue.trim()) return;
    await onRenameConversation(currentKB, convId, renameValue);
    setConversations((prev) => prev.map((c) => c.id === convId ? { ...c, name: renameValue } : c));
    setRenamingConv(null);
  };

  const handleExport = async (convId: string) => {
    if (!currentKB || !onExportConversation) return;
    const md = await onExportConversation(currentKB, convId);
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `conversation-${convId}.md`; a.click();
    URL.revokeObjectURL(url);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); handleSend(); }
  };

  const handleUpload = async (file: File) => {
    if (!currentKB) { alert("请先选择知识库"); return; }
    setUploading(true);
    const result = await onUploadFile(file);
    setUploading(false);
    if (result.success) {
      setMessages((prev) => [...prev, { role: "assistant", content: `文档上传成功，已添加 ${result.chunksAdded} 个分块。` }]);
    } else { alert("上传失败: " + result.error); }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
  };

  const handleUrlUpload = async () => {
    if (!urlInput.trim() || !currentKB || !onUploadURL) return;
    setUrlUploading(true);
    const result = await onUploadURL(urlInput);
    setUrlUploading(false);
    if (result.success) {
      setMessages((prev) => [...prev, { role: "assistant", content: `URL 导入成功: ${urlInput}，已添加 ${result.chunksAdded} 个分块。` }]);
      setUrlInput("");
    } else {
      alert("导入失败: " + result.error);
    }
  };

  const handleClear = async () => {
    await onClearHistory();
    setMessages([{ role: "assistant", content: "历史已清空。" }]);
  };

  const handleSearch = async () => {
    if (!currentKB || !searchQuery.trim() || !onSearch) return;
    setSearchLoading(true);
    const result = await onSearch(currentKB, searchQuery, { top_k: searchTopK, strategy: searchStrategy });
    setSearchResults(result);
    setSearchLoading(false);
  };

  return (
    <div className="h-full flex overflow-hidden" style={{ animation: "fade-in 0.3s ease-out" }}>
      {/* Left Sidebar */}
      <div className="w-56 bg-cyber-surface flex flex-col shrink-0" style={{ borderRight: "2px solid var(--color-cyber-border)" }}>
        <div className="p-3" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
          <select value={currentKB || ""} onChange={(e) => e.target.value && onSelectKB(e.target.value)} className="cyber-input text-[12px]">
            <option value="">选择知识库...</option>
            {kbList.map((kb) => <option key={kb.name} value={kb.name}>{kb.name}</option>)}
          </select>
        </div>
        <div className="flex-1 p-3 overflow-y-auto">
          <div className={`rounded p-4 text-center cursor-pointer transition-all mb-3 ${uploading ? "bg-cyber-yellow/5" : "hover:bg-tiffany-glow"}`}
            style={{ border: "2px dashed var(--color-cyber-border)", ...(uploading ? { borderColor: "var(--color-cyber-yellow)" } : {}) }}
            onClick={() => fileInputRef.current?.click()} onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className={`mx-auto mb-2 ${uploading ? "text-cyber-yellow" : "text-tiffany"}`}>
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p className="text-[11px] text-cyber-text-dim mb-1">{uploading ? "上传中..." : "点击或拖拽上传"}</p>
            <p className="text-[9px] text-cyber-text-muted">PDF, Word, TXT 等格式</p>
            <input ref={fileInputRef} type="file" className="hidden" onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])} />
          </div>

          {/* URL Import */}
          <div className="mb-3">
            <div className="text-[9px] text-cyber-text-muted tracking-wider mb-1">URL 导入</div>
            <div className="flex gap-1">
              <input value={urlInput} onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleUrlUpload()}
                placeholder="https://..." className="cyber-input text-[10px] py-1 flex-1" />
              <button onClick={handleUrlUpload} disabled={urlUploading || !urlInput.trim()}
                className="cyber-btn text-[9px] py-1 px-2 shrink-0">
                {urlUploading ? "..." : "导入"}
              </button>
            </div>
            <div className="text-[8px] text-cyber-text-muted mt-1">网页、YouTube、Wikipedia</div>
          </div>
          {currentKB && (
            <>
              {/* Sidebar Tab Toggle */}
              <div className="flex mb-2 rounded overflow-hidden" style={{ border: "1px solid var(--color-cyber-border)" }}>
                <button onClick={() => setSidebarTab("conversations")}
                  className={`flex-1 py-1 text-[9px] tracking-wider uppercase transition-colors ${sidebarTab === "conversations" ? "bg-tiffany text-cyber-bg font-bold" : "text-cyber-text-muted hover:text-tiffany"}`}>
                  对话
                </button>
                <button onClick={() => setSidebarTab("memory")}
                  className={`flex-1 py-1 text-[9px] tracking-wider uppercase transition-colors ${sidebarTab === "memory" ? "bg-lavender text-cyber-bg font-bold" : "text-cyber-text-muted hover:text-lavender"}`}>
                  记忆
                </button>
              </div>

              {sidebarTab === "conversations" ? (
                <>
                  <button onClick={handleNewConversation} className="cyber-btn cyber-btn-primary w-full text-[10px] py-1.5 mb-3">
                    + 新建对话
                  </button>
                  <div className="space-y-0.5">
                    {conversations.map((conv) => (
                      <div key={conv.id} className={`group rounded transition-colors ${activeConvId === conv.id ? "bg-tiffany-glow" : "hover:bg-lavender-glow"}`}>
                        {renamingConv === conv.id ? (
                          <div className="flex gap-1 px-2 py-1">
                            <input value={renameValue} onChange={(e) => setRenameValue(e.target.value)}
                              onKeyDown={(e) => e.key === "Enter" && handleRename(conv.id)}
                              className="cyber-input text-[10px] py-0.5 flex-1" autoFocus />
                            <button onClick={() => handleRename(conv.id)} className="text-[9px] text-tiffany">OK</button>
                          </div>
                        ) : (
                          <button onClick={() => handleSwitchConversation(conv.id)} className="w-full text-left px-2 py-1.5">
                            <div className="flex items-center justify-between">
                              <span className={`text-[11px] truncate ${activeConvId === conv.id ? "text-tiffany font-semibold" : "text-cyber-text-dim"}`}>{conv.name}</span>
                              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button onClick={(e) => { e.stopPropagation(); setRenamingConv(conv.id); setRenameValue(conv.name); }} className="text-[8px] text-cyber-text-muted hover:text-lavender">R</button>
                                <button onClick={(e) => { e.stopPropagation(); handleExport(conv.id); }} className="text-[8px] text-cyber-text-muted hover:text-tiffany">E</button>
                                <button onClick={(e) => { e.stopPropagation(); handleDeleteConversation(conv.id); }} className="text-[8px] text-cyber-text-muted hover:text-cyber-red">X</button>
                              </div>
                            </div>
                            <div className="text-[9px] text-cyber-text-muted">{conv.message_count} msgs · {conv.preview ? conv.preview.slice(0, 30) : "empty"}</div>
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                /* Memory Tab */
                <div className="space-y-2">
                  {memory.summary && (
                    <div className="cyber-card p-2">
                      <div className="text-[9px] text-cyber-text-muted tracking-wider mb-1">摘要</div>
                      <div className="text-[11px] text-cyber-text-dim">{memory.summary}</div>
                    </div>
                  )}
                  <div className="text-[10px] text-cyber-text-muted tracking-wider">记忆条目 ({memory.entries.length})</div>
                  {memory.entries.map((entry) => (
                    <div key={entry.id} className="cyber-card p-2 group">
                      <div className="flex items-start justify-between">
                        <span className="text-[9px] text-lavender bg-lavender-glow px-1 rounded">{entry.category}</span>
                        <button onClick={() => { if (onDeleteMemory && currentKB) onDeleteMemory(currentKB, entry.id).then(() => onLoadMemory?.(currentKB).then(setMemory)); }}
                          className="text-[8px] text-cyber-text-muted hover:text-cyber-red opacity-0 group-hover:opacity-100 transition-opacity">X</button>
                      </div>
                      <div className="text-[11px] text-cyber-text-dim mt-1">{entry.content}</div>
                    </div>
                  ))}
                  <div className="flex gap-1 mt-2">
                    <input value={newMemoryContent} onChange={(e) => setNewMemoryContent(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && newMemoryContent.trim() && onAddMemory && currentKB) {
                          onAddMemory(currentKB, newMemoryContent, "manual", 0.8).then(() => {
                            setNewMemoryContent("");
                            onLoadMemory?.(currentKB).then(setMemory);
                          });
                        }
                      }}
                      placeholder="手动添加记忆..." className="cyber-input text-[10px] py-1 flex-1" />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Tab Bar */}
        <div className="flex items-center" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
          {(["chat", "search"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-[11px] tracking-wider uppercase transition-colors ${tab === t ? "text-tiffany border-b-2 border-tiffany" : "text-cyber-text-muted hover:text-cyber-text"}`}>
              {t === "chat" ? "对话" : "检索测试"}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2 px-3">
            <span className="text-[9px] text-cyber-text-muted tracking-wider">PIPELINE</span>
            <button onClick={() => setPipelineEnabled(!pipelineEnabled)}
              className={`w-8 h-4 rounded-full transition-colors relative ${pipelineEnabled ? "bg-tiffany" : "bg-cyber-border"}`}>
              <div className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${pipelineEnabled ? "translate-x-4" : "translate-x-0.5"}`} />
            </button>
            {pipelineSteps.length > 0 && (
              <button onClick={() => setShowPipelineSteps(!showPipelineSteps)}
                className="text-[9px] text-lavender hover:text-lavender-dim">
                {showPipelineSteps ? "隐藏步骤" : "查看步骤"}
              </button>
            )}
          </div>
        </div>

        {tab === "chat" ? (
          <>
            {/* Pipeline Steps */}
            {showPipelineSteps && pipelineSteps.length > 0 && (
              <div className="px-4 py-2 bg-cyber-bg" style={{ borderBottom: "1px solid var(--color-cyber-border)" }}>
                <div className="text-[9px] text-cyber-text-muted tracking-wider mb-1">PIPELINE 执行步骤</div>
                <div className="flex gap-2 overflow-x-auto">
                  {pipelineSteps.map((step, i) => (
                    <div key={i} className={`cyber-card p-2 min-w-[140px] shrink-0 ${step.status === "ok" ? "border-tiffany/30" : "border-cyber-red/30"}`}>
                      <div className="flex items-center gap-1 mb-1">
                        <span className="text-[9px] font-bold text-tiffany">{step.name}</span>
                        <span className={`text-[8px] ${step.status === "ok" ? "text-cyber-green" : "text-cyber-red"}`}>{step.status}</span>
                        <span className="text-[8px] text-cyber-text-muted ml-auto">{step.latency}s</span>
                      </div>
                      <div className="text-[9px] text-cyber-text-dim line-clamp-2">{step.output_preview}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ background: "var(--color-cyber-content-bg)" }}>
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`} style={{ animation: "slide-in-up 0.2s ease-out" }}>
                  <div className="max-w-[75%]">
                    <div className={`px-4 py-2.5 text-[13px] leading-relaxed ${msg.role === "user" ? "bg-tiffany/10 text-cyber-text rounded-t-lg rounded-bl-lg rounded-br-sm" : "bg-cyber-card text-cyber-text rounded-t-lg rounded-br-lg rounded-bl-sm"}`}
                      style={{ border: msg.role === "user" ? "2px solid var(--color-cyber-msg-user-border)" : "2px solid var(--color-cyber-border)" }}>
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    </div>
                    {/* Sources with retrieval results */}
                    {msg.retrievalResults && msg.retrievalResults.length > 0 && (
                      <div className="mt-1.5 border-2 border-cyber-border rounded bg-cyber-surface overflow-hidden">
                        <button onClick={(e) => { const el = e.currentTarget.nextElementSibling as HTMLElement; el?.classList.toggle("hidden"); e.currentTarget.querySelector(".arrow")?.classList.toggle("rotate-180"); }}
                          className="w-full flex items-center justify-between px-3 py-1.5 text-[11px] text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow transition-colors">
                          <span className="flex items-center gap-1.5">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-lavender"><path d="M4 19.5A2.5 2.5 0 016.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" /></svg>
                            参考来源 ({msg.chunksUsed} 个分块)
                          </span>
                          <span className="arrow transition-transform duration-200">▼</span>
                        </button>
                        <div className="hidden border-t border-cyber-border">
                          {msg.retrievalResults.map((r, ri) => (
                            <button key={ri} onClick={() => setSelectedResult(r)}
                              className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] hover:text-tiffany hover:bg-tiffany-glow transition-colors text-left">
                              <span className="text-tiffany font-mono text-[9px] w-10 shrink-0">{(r.score * 100).toFixed(0)}%</span>
                              <span className="text-cyber-text-dim truncate flex-1">{r.source}</span>
                              {r.heading_path.length > 0 && <span className="text-lavender text-[9px] truncate">{r.heading_path[0]}</span>}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start" style={{ animation: "fade-in 0.2s ease-out" }}>
                  <div className="bg-cyber-card border-2 border-cyber-border rounded-t-lg rounded-br-lg rounded-bl-sm px-4 py-3">
                    <div className="flex items-center gap-2"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /><span className="text-xs text-cyber-text-muted ml-1">思考中</span></div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
            {/* Input */}
            <div className="p-3 bg-cyber-surface" style={{ borderTop: "2px solid var(--color-cyber-border)" }}>
              <div className="flex gap-2">
                <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
                  placeholder={currentKB ? "输入问题... (Ctrl+Enter 发送)" : "请先选择知识库..."} disabled={!currentKB} className="cyber-input flex-1" />
                <button onClick={handleSend} disabled={!currentKB || loading} className="cyber-btn cyber-btn-primary">发送 →</button>
                <button onClick={handleClear} className="cyber-btn cyber-btn-lavender">清空</button>
              </div>
            </div>
          </>
        ) : (
          /* Search Test Panel */
          <div className="flex-1 overflow-y-auto p-4 space-y-4" style={{ background: "var(--color-cyber-content-bg)" }}>
            <div className="cyber-card">
              <div className="flex gap-2 mb-3">
                <input type="text" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  placeholder="输入检索测试查询..." className="cyber-input flex-1" />
                <button onClick={handleSearch} disabled={!currentKB || searchLoading} className="cyber-btn cyber-btn-primary">
                  {searchLoading ? "检索中..." : "搜索"}
                </button>
              </div>
              <div className="flex gap-4 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className="text-cyber-text-muted">策略:</span>
                  <select value={searchStrategy} onChange={(e) => setSearchStrategy(e.target.value)} className="cyber-input text-[11px] py-1 w-32">
                    <option value="hybrid">Hybrid</option>
                    <option value="vector">Vector</option>
                    <option value="bm25">BM25</option>
                    <option value="hybrid_rerank">Hybrid+Rerank</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-cyber-text-muted">Top K:</span>
                  <input type="number" value={searchTopK} onChange={(e) => setSearchTopK(Number(e.target.value))} className="cyber-input text-[11px] py-1 w-16" min={1} max={20} />
                </div>
              </div>
            </div>

            {searchResults && (
              <div className="space-y-2">
                <div className="text-[11px] text-cyber-text-muted">
                  策略: <span className="text-tiffany">{searchResults.strategy}</span> |
                  耗时: <span className="text-tiffany">{searchResults.latency}s</span> |
                  索引: <span className="text-tiffany">{searchResults.total_chunks} chunks</span>
                </div>
                {searchResults.results.map((r, i) => (
                  <div key={r.chunk_id} className="cyber-card p-3 cursor-pointer" onClick={() => setSelectedResult(r)}>
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-tiffany font-mono text-[11px] font-bold">#{i + 1}</span>
                      <div className="flex-1 bg-cyber-bg rounded-full h-2 overflow-hidden border border-cyber-border">
                        <div className="h-full rounded-full" style={{ width: `${Math.min(r.score * 100, 100)}%`, background: `linear-gradient(90deg, var(--color-tiffany), var(--color-lavender))` }} />
                      </div>
                      <span className="text-[11px] text-tiffany font-mono w-12 text-right">{(r.score * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex items-center gap-2 mb-1 text-[10px]">
                      <span className="text-cyber-text-dim">{r.source}</span>
                      {r.heading_path.length > 0 && <span className="text-lavender">› {r.heading_path.join(" › ")}</span>}
                    </div>
                    <div className="text-[12px] text-cyber-text-dim line-clamp-2">{r.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Source Viewer Panel */}
      {selectedResult && (
        <div className="w-80 bg-cyber-surface flex flex-col shrink-0" style={{ animation: "slide-in-left 0.2s ease-out", borderLeft: "2px solid var(--color-cyber-border)" }}>
          <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
            <h3 className="text-xs font-semibold text-lavender tracking-wider uppercase">参考内容</h3>
            <button onClick={() => setSelectedResult(null)} className="w-5 h-5 flex items-center justify-center text-cyber-text-muted hover:text-cyber-red transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            <div className="bg-cyber-card border-2 border-cyber-border rounded p-3 space-y-2">
              <div className="flex items-center justify-between"><span className="text-[10px] text-cyber-text-muted tracking-wider">来源</span><span className="text-[11px] text-tiffany truncate ml-2">{selectedResult.source}</span></div>
              <div className="flex items-center justify-between"><span className="text-[10px] text-cyber-text-muted tracking-wider">相关度</span><span className="text-[11px] text-cyber-green font-mono">{(selectedResult.score * 100).toFixed(1)}%</span></div>
              {selectedResult.heading_path.length > 0 && (
                <div className="flex items-center justify-between"><span className="text-[10px] text-cyber-text-muted tracking-wider">路径</span><span className="text-[11px] text-lavender truncate ml-2">{selectedResult.heading_path.join(" › ")}</span></div>
              )}
              <div className="flex items-center justify-between"><span className="text-[10px] text-cyber-text-muted tracking-wider">ID</span><span className="text-[10px] text-cyber-text-muted font-mono">{selectedResult.chunk_id}</span></div>
            </div>
            <div className="text-[11px] text-cyber-text-dim font-semibold tracking-wider">内容</div>
            <div className="bg-cyber-bg border-2 border-cyber-border rounded p-3 text-[12px] text-cyber-text-dim leading-relaxed whitespace-pre-wrap">
              {selectedResult.content}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
