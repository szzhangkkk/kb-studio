"use client";

import { useState, useEffect, useCallback } from "react";
import { ToolDefinition, ToolTestResult, GeneratedTool, MCPStatus, ToolCreateInput } from "@/hooks/useKBStudio";

interface ToolsPanelProps {
  onLoadTools: (source?: string) => Promise<ToolDefinition[]>;
  onGetTool: (name: string) => Promise<{ tool: ToolDefinition; code?: string }>;
  onCreateTool: (tool: ToolCreateInput) => Promise<{ status: string; tool?: ToolDefinition }>;
  onUpdateTool: (name: string, updates: Record<string, unknown>) => Promise<{ status: string }>;
  onDeleteTool: (name: string) => Promise<void>;
  onTestTool: (name: string, args?: Record<string, unknown>) => Promise<ToolTestResult>;
  onToggleTool: (name: string, enabled: boolean) => Promise<void>;
  onGenerateTool: (description: string, context?: string) => Promise<{ status: string; tool?: GeneratedTool }>;
  onRefineTool: (code: string, feedback: string) => Promise<{ status: string; tool?: GeneratedTool }>;
  onSaveGeneratedTool: (tool: ToolCreateInput) => Promise<{ status: string }>;
  onLoadMCPStatus: () => Promise<MCPStatus>;
  onGetMCPConfig: (host?: string, port?: number) => Promise<Record<string, unknown>>;
}

const QUICK_PRESETS = [
  { id: "http_request", label: "HTTP 请求", icon: "\u{1F310}", description: "发送 HTTP GET/POST 请求到指定 URL，返回响应数据", context: "支持自定义 headers、超时设置，处理 JSON 响应" },
  { id: "data_process", label: "数据处理", icon: "\u{1F4CA}", description: "对输入的 JSON 数据进行过滤、转换、统计等操作", context: "支持常见的数据操作如分组、聚合、排序" },
  { id: "text_analysis", label: "文本分析", icon: "\u{1F4DD}", description: "分析输入文本的情感、关键词、摘要等信息", context: "支持中文文本，返回结构化分析结果" },
  { id: "file_read", label: "文件读取", icon: "\u{1F4C2}", description: "读取指定路径的文件内容，支持文本和 JSON 格式", context: "安全读取，限制文件大小，返回文件内容和元信息" },
  { id: "datetime", label: "日期时间", icon: "\u{1F550}", description: "获取当前时间、时区转换、日期计算", context: "支持 Unix 时间戳、ISO 格式、自定义格式" },
  { id: "json_transform", label: "JSON 转换", icon: "\u{1F504}", description: "在不同 JSON 结构之间转换数据，支持字段映射和格式化", context: "支持嵌套对象、数组操作、路径提取" },
];

interface GenHistoryEntry {
  version: number;
  tool: GeneratedTool;
  feedback: string;
}

export default function ToolsPanel({
  onLoadTools, onGetTool, onCreateTool, onUpdateTool, onDeleteTool,
  onTestTool, onToggleTool, onGenerateTool, onRefineTool, onSaveGeneratedTool,
  onLoadMCPStatus, onGetMCPConfig,
}: ToolsPanelProps) {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [selectedTool, setSelectedTool] = useState<string | null>(null);
  const [tab, setTab] = useState<"generate" | "edit" | "test" | "mcp">("generate");
  const [loading, setLoading] = useState(false);

  // Editor state
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editParams, setEditParams] = useState("{}");
  const [editCode, setEditCode] = useState("def run(args, context=None):\n    return \"Hello\"");
  const [editTags, setEditTags] = useState("");
  const [isNew, setIsNew] = useState(false);

  // Test state
  const [testArgs, setTestArgs] = useState("{}");
  const [testResult, setTestResult] = useState<ToolTestResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  // Generate state
  const [genDesc, setGenDesc] = useState("");
  const [genContext, setGenContext] = useState("");
  const [genResult, setGenResult] = useState<GeneratedTool | null>(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genFeedback, setGenFeedback] = useState("");
  const [genHistory, setGenHistory] = useState<GenHistoryEntry[]>([]);
  const [viewHistoryVersion, setViewHistoryVersion] = useState<number | null>(null);

  // MCP state
  const [mcpStatus, setMcpStatus] = useState<MCPStatus | null>(null);
  const [mcpConfig, setMcpConfig] = useState<Record<string, unknown> | null>(null);
  const [mcpHost, setMcpHost] = useState("localhost");
  const [mcpPort, setMcpPort] = useState(8000);

  const refreshTools = useCallback(async () => {
    const t = await onLoadTools();
    setTools(t);
  }, [onLoadTools]);

  useEffect(() => { refreshTools(); }, [refreshTools]);

  const handleSelectTool = async (name: string) => {
    setSelectedTool(name);
    setIsNew(false);
    const data = await onGetTool(name);
    setEditName(data.tool.name);
    setEditDesc(data.tool.description);
    setEditParams(JSON.stringify(data.tool.parameters, null, 2));
    setEditCode(data.code || "def run(args, context=None):\n    return \"ok\"");
    setEditTags(data.tool.tags?.join(", ") || "");
    setTab("edit");
  };

  const handleNewTool = (preset?: { description: string; context: string }) => {
    setSelectedTool(null);
    setIsNew(true);
    setGenDesc(preset?.description || "");
    setGenContext(preset?.context || "");
    setGenResult(null);
    setGenHistory([]);
    setGenFeedback("");
    setViewHistoryVersion(null);
    setTab("generate");
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      let params: Record<string, unknown>;
      try { params = JSON.parse(editParams); } catch { alert("Parameters JSON 格式错误"); setLoading(false); return; }

      if (isNew) {
        const result = await onCreateTool({ name: editName, description: editDesc, parameters: params, code: editCode, tags: editTags.split(",").map(s => s.trim()).filter(Boolean) });
        if (result.status === "ok") { await refreshTools(); setSelectedTool(editName); setIsNew(false); setTab("test"); }
        else alert("创建失败: " + JSON.stringify(result));
      } else {
        await onUpdateTool(editName, { description: editDesc, parameters: params, code: editCode, tags: editTags.split(",").map(s => s.trim()).filter(Boolean) });
        await refreshTools();
      }
    } finally { setLoading(false); }
  };

  const handleDelete = async () => {
    if (!selectedTool) return;
    if (!confirm(`确定删除工具 "${selectedTool}"？`)) return;
    await onDeleteTool(selectedTool);
    setSelectedTool(null);
    await refreshTools();
  };

  const handleTest = async () => {
    if (!selectedTool) return;
    setTestLoading(true);
    try {
      let args: Record<string, unknown>;
      try { args = JSON.parse(testArgs); } catch { alert("参数 JSON 格式错误"); setTestLoading(false); return; }
      const result = await onTestTool(selectedTool, args);
      setTestResult(result);
    } finally { setTestLoading(false); }
  };

  const handleToggle = async (tool: ToolDefinition) => {
    await onToggleTool(tool.name, !tool.enabled);
    await refreshTools();
  };

  const handleGenerate = async () => {
    setGenLoading(true);
    try {
      const result = await onGenerateTool(genDesc, genContext);
      if (result.tool) {
        setGenResult(result.tool);
        setEditCode(result.tool.code);
        setGenHistory([{ version: 1, tool: result.tool, feedback: "" }]);
        setViewHistoryVersion(null);
      }
    } finally { setGenLoading(false); }
  };

  const handleRefine = async () => {
    if (!genResult) return;
    setGenLoading(true);
    try {
      const result = await onRefineTool(JSON.stringify(genResult), genFeedback);
      if (result.tool) {
        setGenResult(result.tool);
        setGenHistory(prev => [...prev, { version: prev.length + 1, tool: result.tool!, feedback: genFeedback }]);
        setGenFeedback("");
        setViewHistoryVersion(null);
      }
    } finally { setGenLoading(false); }
  };

  const handleSaveGenerated = async () => {
    if (!genResult) return;
    setLoading(true);
    try {
      await onSaveGeneratedTool({ name: genResult.name, description: genResult.description, parameters: genResult.parameters, code: genResult.code });
      await refreshTools();
      setSelectedTool(genResult.name);
      setEditName(genResult.name);
      setEditDesc(genResult.description);
      setEditParams(JSON.stringify(genResult.parameters, null, 2));
      setEditCode(genResult.code);
      setEditTags("");
      setIsNew(false);
      setGenResult(null);
      setGenHistory([]);
      setTab("edit");
    } finally { setLoading(false); }
  };

  const handleSaveAndTest = async () => {
    if (!genResult) return;
    setLoading(true);
    try {
      await onSaveGeneratedTool({ name: genResult.name, description: genResult.description, parameters: genResult.parameters, code: genResult.code });
      await refreshTools();
      setSelectedTool(genResult.name);
      setTestArgs("{}");
      setTestResult(null);
      setGenResult(null);
      setGenHistory([]);
      setTab("test");
    } finally { setLoading(false); }
  };

  const handleLoadMCP = async () => {
    const status = await onLoadMCPStatus();
    setMcpStatus(status);
    const config = await onGetMCPConfig(mcpHost, mcpPort);
    setMcpConfig(config);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => alert("已复制"));
  };

  const sourceBadge = (source: string) => {
    const colors: Record<string, string> = { builtin: "bg-tiffany/20 text-tiffany", custom: "bg-lavender/20 text-lavender", generated: "bg-cyber-yellow/20 text-cyber-yellow" };
    return <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${colors[source] || ""}`}>{source}</span>;
  };

  const displayCode = viewHistoryVersion !== null
    ? genHistory.find(h => h.version === viewHistoryVersion)?.tool.code || ""
    : genResult?.code || "";

  return (
    <div className="h-full flex overflow-hidden" style={{ animation: "fade-in 0.3s ease-out" }}>
      {/* Tool List */}
      <div className="w-56 bg-cyber-surface flex flex-col shrink-0" style={{ borderRight: "2px solid var(--color-cyber-border)" }}>
        <div className="p-3 flex items-center justify-between" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
          <span className="text-[11px] text-cyber-text-muted tracking-wider uppercase">TOOLS</span>
          <button onClick={() => handleNewTool()} className="cyber-btn text-[10px] py-0.5 px-2">+ NEW</button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {tools.map((t) => (
            <button key={t.name} onClick={() => handleSelectTool(t.name)}
              className={`w-full flex items-center gap-2 px-2 py-1.5 text-[11px] rounded transition-colors text-left ${selectedTool === t.name ? "text-tiffany bg-tiffany-glow" : "text-cyber-text-dim hover:text-lavender hover:bg-lavender-glow"}`}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="truncate font-mono">{t.name}</span>
                  {sourceBadge(t.source)}
                </div>
                <div className="text-[9px] text-cyber-text-muted truncate">{t.description}</div>
              </div>
              <div className={`w-2 h-2 rounded-full shrink-0 ${t.enabled ? "bg-cyber-green" : "bg-cyber-text-muted"}`} />
            </button>
          ))}
          {tools.length === 0 && <div className="px-2 py-4 text-[11px] text-cyber-text-muted text-center">暂无工具</div>}
        </div>
      </div>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Tab Bar */}
        <div className="flex items-center" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
          {(["generate", "edit", "test", "mcp"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-[11px] tracking-wider uppercase transition-colors ${tab === t ? "text-tiffany border-b-2 border-tiffany" : "text-cyber-text-muted hover:text-cyber-text"}`}>
              {({ edit: "编辑", test: "测试", generate: "生成", mcp: "MCP" })[t]}
            </button>
          ))}
          {selectedTool && !isNew && (() => {
            const sel = tools.find(t => t.name === selectedTool);
            if (!sel) return null;
            return (
            <div className="ml-auto flex items-center gap-2 px-3">
              <button onClick={() => handleToggle(sel)} className="text-[10px] text-cyber-text-muted hover:text-tiffany">
                {sel.enabled ? "禁用" : "启用"}
              </button>
              {sel.source !== "builtin" && (
                <button onClick={handleDelete} className="text-[10px] text-cyber-text-muted hover:text-cyber-red">删除</button>
              )}
            </div>
            );
          })()}
        </div>

        <div className="flex-1 overflow-y-auto p-4" style={{ background: "var(--color-cyber-content-bg)" }}>
          {/* Generate Tab */}
          {tab === "generate" && (
            <div className="space-y-4 max-w-3xl">
              {/* Quick presets - show when no generation has happened */}
              {genHistory.length === 0 && !genResult && (
                <div>
                  <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-2">快速开始 QUICK START</label>
                  <div className="grid grid-cols-3 gap-2">
                    {QUICK_PRESETS.map((preset) => (
                      <button key={preset.id} onClick={() => handleNewTool(preset)}
                        className="cyber-card p-3 text-left hover:border-tiffany-dim transition-all group">
                        <div className="text-lg mb-1">{preset.icon}</div>
                        <div className="text-[11px] font-semibold text-cyber-text group-hover:text-tiffany">{preset.label}</div>
                        <div className="text-[9px] text-cyber-text-muted line-clamp-2 mt-0.5">{preset.description}</div>
                      </button>
                    ))}
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <div className="flex-1 h-px bg-cyber-border" />
                    <span className="text-[9px] text-cyber-text-muted tracking-wider">或自定义描述</span>
                    <div className="flex-1 h-px bg-cyber-border" />
                  </div>
                </div>
              )}

              {/* Description input */}
              <div>
                <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">描述你想要的工具</label>
                <textarea value={genDesc} onChange={(e) => setGenDesc(e.target.value)}
                  className="cyber-input w-full text-[12px] h-24 resize-y"
                  placeholder="例如：把用户输入的文本转成大写&#10;例如：查询天气信息，输入城市名返回天气" />
              </div>
              <div>
                <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">额外上下文（可选）</label>
                <input value={genContext} onChange={(e) => setGenContext(e.target.value)}
                  className="cyber-input w-full text-[12px]" placeholder="特定的知识库名、业务逻辑等" />
              </div>

              {/* Generate / Regenerate button */}
              <div className="flex gap-2">
                <button onClick={handleGenerate} disabled={genLoading || !genDesc.trim()} className="cyber-btn cyber-btn-primary">
                  {genLoading ? "生成中..." : genHistory.length > 0 ? "重新生成" : "AI 生成工具"}
                </button>
              </div>

              {/* Generation result with history */}
              {genResult && (
                <div className="cyber-card p-4 space-y-3">
                  {/* Header */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-[12px] text-tiffany font-mono">{genResult.name}</span>
                      {genResult.warnings?.length > 0 && (
                        <span className="text-[10px] text-cyber-yellow">{genResult.warnings.length} warnings</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-[9px] text-cyber-text-muted">v{genHistory.length}</span>
                    </div>
                  </div>
                  <div className="text-[11px] text-cyber-text-dim">{genResult.description}</div>

                  {/* Version history */}
                  {genHistory.length > 1 && (
                    <div className="flex flex-wrap gap-1.5">
                      {genHistory.map((entry) => (
                        <button key={entry.version} onClick={() => setViewHistoryVersion(viewHistoryVersion === entry.version ? null : entry.version)}
                          className={`px-2 py-0.5 rounded text-[10px] border transition-colors ${
                            (viewHistoryVersion === null && entry.version === genHistory.length) || viewHistoryVersion === entry.version
                              ? "border-tiffany text-tiffany bg-tiffany-glow"
                              : "border-cyber-border text-cyber-text-muted hover:text-cyber-text hover:border-cyber-text-muted"
                          }`}>
                          v{entry.version}{entry.feedback ? `: ${entry.feedback.slice(0, 15)}${entry.feedback.length > 15 ? "..." : ""}` : " 初始"}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Code editor */}
                  <div>
                    <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">
                      {viewHistoryVersion !== null ? `v${viewHistoryVersion} 代码（只读）` : "生成的代码"}
                    </label>
                    <textarea
                      value={displayCode}
                      onChange={(e) => { if (viewHistoryVersion === null && genResult) setGenResult({ ...genResult, code: e.target.value }); }}
                      readOnly={viewHistoryVersion !== null}
                      className={`cyber-input w-full text-[11px] font-mono h-48 resize-y ${viewHistoryVersion !== null ? "opacity-70" : ""}`}
                    />
                  </div>

                  {/* Warnings */}
                  {genResult.warnings?.length > 0 && (
                    <div className="text-[10px] text-cyber-yellow space-y-0.5">
                      {genResult.warnings.map((w, i) => <div key={i}>{"⚠"} {w}</div>)}
                    </div>
                  )}

                  {/* Refine feedback */}
                  <div className="flex gap-2">
                    <input value={genFeedback} onChange={(e) => setGenFeedback(e.target.value)}
                      className="cyber-input flex-1 text-[11px]" placeholder="输入改进反馈，例如：添加错误处理、支持超时..." />
                    <button onClick={handleRefine} disabled={genLoading || !genFeedback.trim()} className="cyber-btn text-[10px]">
                      {genLoading ? "优化中..." : "优化"}
                    </button>
                  </div>

                  {/* Save actions */}
                  <div className="flex gap-2 pt-1 border-t border-cyber-border">
                    <button onClick={handleSaveGenerated} disabled={loading} className="cyber-btn cyber-btn-primary text-[10px]">
                      {loading ? "保存中..." : "保存并继续编辑"}
                    </button>
                    <button onClick={handleSaveAndTest} disabled={loading} className="cyber-btn text-[10px]">
                      保存并测试
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Edit Tab */}
          {tab === "edit" && (
            <div className="space-y-4 max-w-3xl">
              {!selectedTool && !isNew ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-cyber-text-muted mb-4">
                    <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" />
                  </svg>
                  <div className="text-[12px] text-cyber-text-dim mb-2">选择左侧工具进行编辑</div>
                  <div className="text-[11px] text-cyber-text-muted mb-4">或创建一个新工具</div>
                  <button onClick={() => handleNewTool()} className="cyber-btn cyber-btn-primary text-[11px]">
                    AI 生成新工具
                  </button>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">NAME (snake_case)</label>
                      <input value={editName} onChange={(e) => setEditName(e.target.value)} disabled={!isNew}
                        className="cyber-input w-full text-[12px] font-mono" placeholder="my_tool" />
                    </div>
                    <div>
                      <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">TAGS</label>
                      <input value={editTags} onChange={(e) => setEditTags(e.target.value)}
                        className="cyber-input w-full text-[12px]" placeholder="tag1, tag2" />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">DESCRIPTION</label>
                    <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)}
                      className="cyber-input w-full text-[12px]" placeholder="工具描述（LLM 会根据这个决定何时调用）" />
                  </div>
                  <div>
                    <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">PARAMETERS (JSON Schema)</label>
                    <textarea value={editParams} onChange={(e) => setEditParams(e.target.value)}
                      className="cyber-input w-full text-[11px] font-mono h-24 resize-y" />
                  </div>
                  <div>
                    <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">CODE</label>
                    <textarea value={editCode} onChange={(e) => setEditCode(e.target.value)}
                      className="cyber-input w-full text-[11px] font-mono h-64 resize-y" spellCheck={false} />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={handleSave} disabled={loading} className="cyber-btn cyber-btn-primary">
                      {loading ? "保存中..." : isNew ? "创建工具" : "保存修改"}
                    </button>
                    {!isNew && selectedTool && (
                      <button onClick={() => setTab("test")} className="cyber-btn text-[10px]">运行测试</button>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Test Tab */}
          {tab === "test" && (
            <div className="space-y-4 max-w-3xl">
              <div className="text-[11px] text-cyber-text-muted">
                测试工具: <span className="text-tiffany font-mono">{selectedTool || "未选择"}</span>
              </div>
              <div>
                <label className="text-[10px] text-cyber-text-muted tracking-wider block mb-1">INPUT (JSON)</label>
                <textarea value={testArgs} onChange={(e) => setTestArgs(e.target.value)}
                  className="cyber-input w-full text-[11px] font-mono h-32 resize-y" placeholder='{"key": "value"}' />
              </div>
              <button onClick={handleTest} disabled={!selectedTool || testLoading} className="cyber-btn cyber-btn-primary">
                {testLoading ? "执行中..." : "运行测试"}
              </button>
              {testResult && (
                <div className="cyber-card p-3">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`text-[11px] font-bold ${testResult.error ? "text-cyber-red" : "text-cyber-green"}`}>
                      {testResult.error ? "错误" : "成功"}
                    </span>
                    <span className="text-[10px] text-cyber-text-muted">{testResult.duration_ms}ms</span>
                  </div>
                  <pre className="text-[11px] text-cyber-text-dim whitespace-pre-wrap bg-cyber-bg p-2 rounded border border-cyber-border overflow-auto max-h-64">
                    {testResult.error || testResult.result}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* MCP Tab */}
          {tab === "mcp" && (
            <div className="space-y-4 max-w-3xl">
              <div className="flex items-center gap-3">
                <button onClick={handleLoadMCP} className="cyber-btn cyber-btn-primary">刷新状态</button>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-cyber-text-muted">Host:</span>
                  <input value={mcpHost} onChange={(e) => setMcpHost(e.target.value)} className="cyber-input w-28 text-[11px] py-0.5" />
                  <span className="text-cyber-text-muted">Port:</span>
                  <input type="number" value={mcpPort} onChange={(e) => setMcpPort(Number(e.target.value))} className="cyber-input w-16 text-[11px] py-0.5" />
                </div>
              </div>

              {mcpStatus && (
                <div className="cyber-card p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${mcpStatus.running ? "bg-cyber-green" : "bg-cyber-red"}`} />
                    <span className="text-[12px] font-bold">{mcpStatus.running ? "MCP 运行中" : "MCP 未运行"}</span>
                    {mcpStatus.tool_count !== undefined && (
                      <span className="text-[10px] text-cyber-text-muted">{mcpStatus.tool_count} tools</span>
                    )}
                  </div>
                  {mcpStatus.error && <div className="text-[11px] text-cyber-yellow">{mcpStatus.error}</div>}
                </div>
              )}

              {mcpConfig && (
                <div className="space-y-3">
                  <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">连接配置</div>
                  {Object.entries(mcpConfig).map(([client, config]) => (
                    <div key={client} className="cyber-card p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[11px] text-tiffany font-bold">{client.replace(/_/g, " ")}</span>
                        <button onClick={() => copyToClipboard(JSON.stringify(config, null, 2))} className="text-[9px] text-cyber-text-muted hover:text-tiffany">复制</button>
                      </div>
                      <pre className="text-[10px] text-cyber-text-dim bg-cyber-bg p-2 rounded border border-cyber-border overflow-auto">
                        {JSON.stringify(config, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
