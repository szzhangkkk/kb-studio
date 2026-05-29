"use client";

import { useState, useEffect, useCallback } from "react";
import { KnowledgeBase, DocumentInfo, ChunkInfo, Finding, FindingsSummary } from "@/hooks/useKBStudio";

interface KBPanelProps {
  kbList: KnowledgeBase[];
  onCreateKB: (name: string, desc: string, prompt: string) => Promise<{ success: boolean; error?: string }>;
  onDeleteKB: (name: string) => Promise<void>;
  onSelectKB: (name: string) => void;
  onLoadDocuments: (kbName: string) => Promise<DocumentInfo[]>;
  onGetDocumentContent: (kbName: string, filename: string) => Promise<string>;
  onGetDocumentChunks: (kbName: string, filename: string) => Promise<ChunkInfo[]>;
  onDeleteDocument: (kbName: string, filename: string) => Promise<{ success: boolean; error?: string }>;
  onRechunkDocument: (kbName: string, filename: string, strategy: string, maxChunkSize: number, overlap: number) => Promise<{ success: boolean; error?: string }>;
  onLoadFindings?: (kbName: string, typeFilter?: string, statusFilter?: string) => Promise<Finding[]>;
  onLoadFindingsSummary?: (kbName: string) => Promise<FindingsSummary>;
  onResolveFinding?: (kbName: string, findingId: string) => Promise<void>;
  onDismissFinding?: (kbName: string, findingId: string) => Promise<void>;
  onAnalyzeKB?: (kbName: string) => Promise<{ findings_count?: number; findings_summary?: Record<string, number> }>;
}

const defaultPrompt = "根据知识库中的文档回答用户问题。如果文档中没有相关信息，请如实说明。";

export default function KBPanel({
  kbList, onCreateKB, onDeleteKB, onSelectKB,
  onLoadDocuments, onGetDocumentContent, onGetDocumentChunks,
  onDeleteDocument, onRechunkDocument,
  onLoadFindings, onLoadFindingsSummary, onResolveFinding, onDismissFinding, onAnalyzeKB,
}: KBPanelProps) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [creating, setCreating] = useState(false);
  const [selectedKB, setSelectedKB] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Preview state
  const [previewDoc, setPreviewDoc] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);

  // Chunks state
  const [chunksDoc, setChunksDoc] = useState<string | null>(null);
  const [chunks, setChunks] = useState<ChunkInfo[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);

  // Rechunk dialog
  const [rechunkDoc, setRechunkDoc] = useState<string | null>(null);
  const [rechunkStrategy, setRechunkStrategy] = useState("semantic");
  const [rechunkSize, setRechunkSize] = useState(512);
  const [rechunkOverlap, setRechunkOverlap] = useState(128);

  // Findings state
  const [kbTab, setKbTab] = useState<"docs" | "findings">("docs");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingsSummary, setFindingsSummary] = useState<FindingsSummary | null>(null);
  const [loadingFindings, setLoadingFindings] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [findingFilter, setFindingFilter] = useState<string>("open");

  const loadDocs = useCallback(async (kbName: string) => {
    setLoadingDocs(true);
    const docs = await onLoadDocuments(kbName);
    setDocuments(docs);
    setLoadingDocs(false);
  }, [onLoadDocuments]);

  useEffect(() => {
    if (selectedKB) loadDocs(selectedKB);
  }, [selectedKB, loadDocs]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    const result = await onCreateKB(name, desc, prompt);
    if (result.success) { setName(""); setDesc(""); setPrompt(defaultPrompt); }
    else alert("创建失败: " + result.error);
    setCreating(false);
  };

  const handleDeleteKB = async (kbName: string) => {
    if (!confirm(`确定删除 "${kbName}"？此操作不可恢复。`)) return;
    await onDeleteKB(kbName);
    if (selectedKB === kbName) setSelectedKB(null);
  };

  const handlePreview = async (filename: string) => {
    if (!selectedKB) return;
    setPreviewDoc(filename);
    setPreviewLoading(true);
    const content = await onGetDocumentContent(selectedKB, filename);
    setPreviewContent(content);
    setPreviewLoading(false);
  };

  const handleViewChunks = async (filename: string) => {
    if (!selectedKB) return;
    setChunksDoc(filename);
    setChunksLoading(true);
    const c = await onGetDocumentChunks(selectedKB, filename);
    setChunks(c);
    setChunksLoading(false);
  };

  const handleDeleteDoc = async (filename: string) => {
    if (!selectedKB) return;
    if (!confirm(`确定删除文档 "${filename}"？`)) return;
    await onDeleteDocument(selectedKB, filename);
    loadDocs(selectedKB);
  };

  const handleRechunk = async () => {
    if (!selectedKB || !rechunkDoc) return;
    await onRechunkDocument(selectedKB, rechunkDoc, rechunkStrategy, rechunkSize, rechunkOverlap);
    setRechunkDoc(null);
    loadDocs(selectedKB);
  };

  const loadFindingsData = useCallback(async (kbName: string) => {
    if (!onLoadFindings || !onLoadFindingsSummary) return;
    setLoadingFindings(true);
    try {
      const [f, s] = await Promise.all([
        onLoadFindings(kbName, findingFilter === "all" ? undefined : findingFilter),
        onLoadFindingsSummary(kbName),
      ]);
      setFindings(f);
      setFindingsSummary(s);
    } finally {
      setLoadingFindings(false);
    }
  }, [onLoadFindings, onLoadFindingsSummary, findingFilter]);

  useEffect(() => {
    if (selectedKB && kbTab === "findings") loadFindingsData(selectedKB);
  }, [selectedKB, kbTab, loadFindingsData]);

  const handleAnalyze = async () => {
    if (!selectedKB || !onAnalyzeKB) return;
    setAnalyzing(true);
    try {
      await onAnalyzeKB(selectedKB);
      await loadFindingsData(selectedKB);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResolveFinding = async (findingId: string) => {
    if (!selectedKB || !onResolveFinding) return;
    await onResolveFinding(selectedKB, findingId);
    loadFindingsData(selectedKB);
  };

  const handleDismissFinding = async (findingId: string) => {
    if (!selectedKB || !onDismissFinding) return;
    await onDismissFinding(selectedKB, findingId);
    loadFindingsData(selectedKB);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const formatTime = (iso: string) => {
    try { return new Date(iso).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); }
    catch { return iso; }
  };

  // ── Document Detail Views ──

  if (previewDoc) {
    return (
      <div className="h-full flex flex-col overflow-hidden" style={{ animation: "fade-in 0.2s ease-out" }}>
        <div className="flex items-center gap-3 px-6 py-3" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
          <button onClick={() => setPreviewDoc(null)} className="cyber-btn text-[11px] py-1 px-3">← 返回</button>
          <span className="text-sm font-semibold text-cyber-text">{previewDoc}</span>
          <span className="text-[10px] text-cyber-text-muted tracking-wider">MARKDOWN 预览</span>
        </div>
        <div className="flex-1 overflow-y-auto p-6">
          {previewLoading ? (
            <div className="text-center py-12 text-cyber-text-muted">加载中...</div>
          ) : (
            <pre className="bg-cyber-bg border-2 border-cyber-border rounded p-4 text-[12px] text-cyber-text-dim whitespace-pre-wrap leading-relaxed overflow-auto">
              {previewContent}
            </pre>
          )}
        </div>
      </div>
    );
  }

  if (chunksDoc) {
    return (
      <div className="h-full flex flex-col overflow-hidden" style={{ animation: "fade-in 0.2s ease-out" }}>
        <div className="flex items-center gap-3 px-6 py-3" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
          <button onClick={() => { setChunksDoc(null); setExpandedChunk(null); }} className="cyber-btn text-[11px] py-1 px-3">← 返回</button>
          <span className="text-sm font-semibold text-cyber-text">{chunksDoc}</span>
          <span className="text-[10px] text-cyber-text-muted tracking-wider">{chunks.length} 个分块</span>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-2">
          {chunksLoading ? (
            <div className="text-center py-12 text-cyber-text-muted">加载中...</div>
          ) : chunks.map((c, i) => (
            <div key={c.chunk_id} className="cyber-card p-3 cursor-pointer" onClick={() => setExpandedChunk(expandedChunk === c.chunk_id ? null : c.chunk_id)}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-semibold text-tiffany">#{i + 1} {c.chunk_id}</span>
                {c.heading_path.length > 0 && (
                  <span className="text-[10px] text-lavender">{c.heading_path.join(" > ")}</span>
                )}
              </div>
              <div className={`text-[12px] text-cyber-text-dim ${expandedChunk === c.chunk_id ? "" : "line-clamp-2"}`}>
                {c.content}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Main View ──

  return (
    <div className="h-full overflow-y-auto p-6" style={{ animation: "fade-in 0.3s ease-out" }}>
      {/* Create Form */}
      <div className="cyber-card mb-6">
        <div className="flex items-center gap-2 mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-tiffany">
            <circle cx="12" cy="12" r="10" /><path d="M12 8v8m-4-4h8" />
          </svg>
          <h3 className="text-sm font-semibold tracking-wide text-cyber-text uppercase">创建知识库</h3>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">名称 *</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="cyber-input" placeholder="my-knowledge-base" />
          </div>
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">描述</label>
            <input type="text" value={desc} onChange={(e) => setDesc(e.target.value)} className="cyber-input" placeholder="可选描述" />
          </div>
        </div>
        <div className="mb-4">
          <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">System Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} className="cyber-input min-h-[80px] resize-y" />
        </div>
        <button onClick={handleCreate} disabled={creating} className="cyber-btn cyber-btn-primary">
          {creating ? "创建中..." : "// 创建知识库"}
        </button>
      </div>

      {/* KB List or Document List */}
      {selectedKB ? (
        <div className="cyber-card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <button onClick={() => setSelectedKB(null)} className="cyber-btn text-[11px] py-1 px-3">← 返回</button>
              <h3 className="text-sm font-semibold text-tiffany">{selectedKB}</h3>
              <span className="text-[10px] text-cyber-text-muted">{documents.length} 个文档</span>
            </div>
            <button onClick={() => onSelectKB(selectedKB)} className="cyber-btn cyber-btn-lavender text-[11px] py-1 px-3">
              打开对话 →
            </button>
          </div>

          {/* Tab bar */}
          <div className="flex gap-1 mb-4 border-b-2 border-cyber-border pb-2">
            <button
              onClick={() => setKbTab("docs")}
              className={`text-[11px] px-3 py-1.5 rounded-t font-semibold tracking-wider uppercase transition-colors ${
                kbTab === "docs" ? "text-tiffany bg-tiffany-glow border-b-2 border-tiffany" : "text-cyber-text-muted hover:text-cyber-text"
              }`}
            >
              文档 {documents.length}
            </button>
            <button
              onClick={() => setKbTab("findings")}
              className={`text-[11px] px-3 py-1.5 rounded-t font-semibold tracking-wider uppercase transition-colors flex items-center gap-1.5 ${
                kbTab === "findings" ? "text-tiffany bg-tiffany-glow border-b-2 border-tiffany" : "text-cyber-text-muted hover:text-cyber-text"
              }`}
            >
              质量检查
              {findingsSummary && findingsSummary.by_status.open > 0 && (
                <span className="inline-flex items-center justify-center w-4 h-4 text-[9px] font-bold text-white bg-red-500 rounded-full">
                  {findingsSummary.by_status.open}
                </span>
              )}
            </button>
          </div>

          {/* Documents Tab */}
          {kbTab === "docs" && (loadingDocs ? (
            <div className="text-center py-12 text-cyber-text-muted">加载中...</div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-cyber-text-dim">暂无文档</p>
              <p className="text-xs text-cyber-text-muted mt-1">在对话面板中上传文档</p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div key={doc.filename} className="flex items-center gap-4 px-4 py-3 bg-cyber-bg border-2 border-cyber-border rounded hover:border-tiffany/30 transition-colors">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tiffany shrink-0">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" />
                  </svg>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-semibold text-cyber-text truncate">{doc.filename}</div>
                    <div className="text-[10px] text-cyber-text-muted flex gap-3">
                      <span>{formatSize(doc.size_bytes)}</span>
                      <span>{doc.chunk_count} 分块</span>
                      <span>{formatTime(doc.upload_time)}</span>
                      {doc.chunk_strategy && <span className="text-lavender">{doc.chunk_strategy}</span>}
                    </div>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <button onClick={() => handlePreview(doc.filename)} className="cyber-btn text-[10px] py-1 px-2">预览</button>
                    <button onClick={() => handleViewChunks(doc.filename)} className="cyber-btn cyber-btn-lavender text-[10px] py-1 px-2">分块</button>
                    <button onClick={() => { setRechunkDoc(doc.filename); setRechunkStrategy(doc.chunk_strategy || "semantic"); }} className="cyber-btn text-[10px] py-1 px-2">重分块</button>
                    <button onClick={() => handleDeleteDoc(doc.filename)} className="cyber-btn cyber-btn-danger text-[10px] py-1 px-2">删除</button>
                  </div>
                </div>
              ))}
            </div>
          ))}

          {/* Findings Tab */}
          {kbTab === "findings" && (
            <div>
              {/* Summary + Actions */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  {findingsSummary && (
                    <div className="flex gap-2 text-[10px]">
                      {findingsSummary.by_type.contradiction > 0 && (
                        <span className="px-2 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 font-semibold">
                          {findingsSummary.by_type.contradiction} 矛盾
                        </span>
                      )}
                      {findingsSummary.by_type.duplicate > 0 && (
                        <span className="px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 font-semibold">
                          {findingsSummary.by_type.duplicate} 重复
                        </span>
                      )}
                      {findingsSummary.by_type.update > 0 && (
                        <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-semibold">
                          {findingsSummary.by_type.update} 更新
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <select value={findingFilter} onChange={(e) => setFindingFilter(e.target.value)} className="cyber-input text-[10px] py-1 px-2">
                    <option value="open">待处理</option>
                    <option value="resolved">已解决</option>
                    <option value="dismissed">已忽略</option>
                    <option value="all">全部</option>
                  </select>
                  {onAnalyzeKB && (
                    <button onClick={handleAnalyze} disabled={analyzing} className="cyber-btn cyber-btn-primary text-[10px] py-1 px-3">
                      {analyzing ? "分析中..." : "全量扫描"}
                    </button>
                  )}
                </div>
              </div>

              {loadingFindings ? (
                <div className="text-center py-12 text-cyber-text-muted">加载中...</div>
              ) : findings.length === 0 ? (
                <div className="text-center py-12">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tiffany mx-auto mb-3 opacity-50">
                    <path d="M9 12l2 2 4-4" /><circle cx="12" cy="12" r="10" />
                  </svg>
                  <p className="text-sm text-cyber-text-dim">
                    {findingFilter === "open" ? "没有待处理的质量问题" : "没有找到匹配的记录"}
                  </p>
                  <p className="text-xs text-cyber-text-muted mt-1">
                    {findingFilter === "open" && onAnalyzeKB ? "上传文档时会自动检测，也可以点击\"全量扫描\"" : ""}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {findings.map((f) => (
                    <FindingCard
                      key={f.id}
                      finding={f}
                      onResolve={() => handleResolveFinding(f.id)}
                      onDismiss={() => handleDismissFinding(f.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="cyber-card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-lavender">
                <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
              <h3 className="text-sm font-semibold tracking-wide text-cyber-text uppercase">知识库列表</h3>
            </div>
            <span className="text-[11px] text-cyber-text-muted px-2 py-0.5 bg-cyber-bg border-2 border-cyber-border rounded">
              {kbList.length} 个
            </span>
          </div>

          {kbList.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-cyber-text-dim mb-1">还没有知识库</p>
              <p className="text-xs text-cyber-text-muted">点击上方按钮创建第一个知识库</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {kbList.map((kb, i) => (
                <div key={kb.name} className="cyber-card cursor-pointer group" style={{ animation: `slide-in-up ${0.1 + i * 0.05}s ease-out` }} onClick={() => setSelectedKB(kb.name)}>
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="text-sm font-semibold text-cyber-text group-hover:text-tiffany transition-colors truncate">{kb.name}</h4>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-cyber-text-muted group-hover:text-tiffany transition-colors shrink-0 ml-2">
                      <path d="M5 12h14m-4-4l4 4-4 4" />
                    </svg>
                  </div>
                  <p className="text-xs text-cyber-text-dim mb-3 line-clamp-2">{kb.description || "无描述"}</p>
                  <div className="flex items-center gap-4 text-[10px] text-cyber-text-muted mb-3">
                    <span className="flex items-center gap-1">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-tiffany"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /></svg>
                      {kb.doc_count} 文档
                    </span>
                    <span className="flex items-center gap-1">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-lavender"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></svg>
                      {kb.chunk_count} 分块
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={(e) => { e.stopPropagation(); setSelectedKB(kb.name); }} className="cyber-btn text-[10px] py-1 px-3 flex-1">文档</button>
                    <button onClick={(e) => { e.stopPropagation(); onSelectKB(kb.name); }} className="cyber-btn cyber-btn-lavender text-[10px] py-1 px-3 flex-1">对话</button>
                    <button onClick={(e) => { e.stopPropagation(); handleDeleteKB(kb.name); }} className="cyber-btn cyber-btn-danger text-[10px] py-1 px-3">删除</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Rechunk Dialog */}
      {rechunkDoc && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setRechunkDoc(null)}>
          <div className="cyber-card w-96" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-tiffany mb-4">重新分块: {rechunkDoc}</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] text-cyber-text-muted mb-1 tracking-wider uppercase">策略</label>
                <select value={rechunkStrategy} onChange={(e) => setRechunkStrategy(e.target.value)} className="cyber-input">
                  <option value="semantic">Semantic</option>
                  <option value="heading">Heading</option>
                  <option value="sliding_window">Sliding Window</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-cyber-text-muted mb-1 tracking-wider uppercase">最大分块大小</label>
                <input type="number" value={rechunkSize} onChange={(e) => setRechunkSize(Number(e.target.value))} className="cyber-input" />
              </div>
              <div>
                <label className="block text-[11px] text-cyber-text-muted mb-1 tracking-wider uppercase">重叠</label>
                <input type="number" value={rechunkOverlap} onChange={(e) => setRechunkOverlap(Number(e.target.value))} className="cyber-input" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={handleRechunk} className="cyber-btn cyber-btn-primary flex-1">执行重分块</button>
              <button onClick={() => setRechunkDoc(null)} className="cyber-btn cyber-btn-lavender">取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FindingCard({ finding, onResolve, onDismiss }: { finding: Finding; onResolve: () => void; onDismiss: () => void }) {
  const [expanded, setExpanded] = useState(false);

  const typeConfig = {
    contradiction: { label: "矛盾", color: "text-red-700 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950", border: "border-red-200 dark:border-red-800", icon: "!" },
    duplicate: { label: "重复", color: "text-amber-700 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-950", border: "border-amber-200 dark:border-amber-800", icon: "=" },
    update: { label: "更新", color: "text-blue-700 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950", border: "border-blue-200 dark:border-blue-800", icon: "~" },
  };

  const cfg = typeConfig[finding.type] || typeConfig.update;
  const statusLabel = finding.status === "resolved" ? "已解决" : finding.status === "dismissed" ? "已忽略" : "待处理";

  return (
    <div className={`border-2 ${cfg.border} rounded-lg overflow-hidden transition-all`}>
      <div
        className="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-cyber-bg/50"
        onClick={() => setExpanded(!expanded)}
      >
        <span className={`shrink-0 w-5 h-5 rounded flex items-center justify-center text-[11px] font-bold text-white ${
          finding.type === "contradiction" ? "bg-red-500" : finding.type === "duplicate" ? "bg-amber-500" : "bg-blue-500"
        }`}>
          {cfg.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[11px] font-semibold ${cfg.color} ${cfg.bg} px-1.5 py-0.5 rounded`}>{cfg.label}</span>
            <span className="text-[10px] text-cyber-text-muted">{finding.new_chunk.source}</span>
            <span className="text-[10px] text-cyber-text-muted">vs</span>
            <span className="text-[10px] text-cyber-text-muted">{finding.existing_chunk.source}</span>
            {finding.status !== "open" && (
              <span className="text-[10px] text-cyber-text-muted ml-auto">{statusLabel}</span>
            )}
          </div>
          <p className="text-[12px] text-cyber-text-dim">{finding.explanation}</p>
        </div>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`text-cyber-text-muted shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>

      {expanded && (
        <div className="px-4 pb-3 space-y-3 border-t border-cyber-border/50">
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div>
              <div className="text-[10px] text-cyber-text-muted mb-1 tracking-wider uppercase">新文档片段</div>
              <div className={`${cfg.bg} rounded p-2 text-[11px] text-cyber-text-dim leading-relaxed max-h-32 overflow-y-auto`}>
                {finding.new_chunk.content}
              </div>
              <div className="text-[10px] text-cyber-text-muted mt-1">{finding.new_chunk.source} / {finding.new_chunk.chunk_id}</div>
            </div>
            <div>
              <div className="text-[10px] text-cyber-text-muted mb-1 tracking-wider uppercase">已有文档片段</div>
              <div className="bg-cyber-bg rounded p-2 text-[11px] text-cyber-text-dim leading-relaxed max-h-32 overflow-y-auto border border-cyber-border">
                {finding.existing_chunk.content}
              </div>
              <div className="text-[10px] text-cyber-text-muted mt-1">{finding.existing_chunk.source} / {finding.existing_chunk.chunk_id}</div>
            </div>
          </div>

          {finding.status === "open" && (
            <div className="flex gap-2 pt-1">
              <button onClick={onResolve} className="cyber-btn text-[10px] py-1 px-3 flex items-center gap-1">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-600"><path d="M9 12l2 2 4-4" /></svg>
                标记已解决
              </button>
              <button onClick={onDismiss} className="cyber-btn text-[10px] py-1 px-3 flex items-center gap-1">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-cyber-text-muted"><path d="M18 6L6 18M6 6l12 12" /></svg>
                忽略
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
