"use client";

import { useState, useCallback } from "react";

const API = "";

async function safeFetch(url: string, options?: RequestInit): Promise<Response> {
  try {
    const resp = await fetch(url, options);
    if (!resp.ok) {
      const text = await resp.text().catch(() => resp.statusText);
      throw new Error(`HTTP ${resp.status}: ${text}`);
    }
    return resp;
  } catch (err) {
    console.error(`API error [${url}]:`, err);
    throw err;
  }
}

export interface KnowledgeBase {
  name: string;
  description: string;
  system_prompt: string;
  doc_count: number;
  chunk_count: number;
}

export interface ChatSource {
  file: string;
  chunk_index: number;
  score: number;
  content?: string;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
  chunks_used: number;
  latency?: number;
  retrieval_results?: RetrievalResult[];
  metadata?: Record<string, unknown>;
}

export interface RetrievalResult {
  chunk_id: string;
  content: string;
  score: number;
  source: string;
  heading_path: string[];
}

export interface SearchResult {
  query: string;
  strategy: string;
  latency: number;
  total_chunks: number;
  results: RetrievalResult[];
}

export interface RetrievalConfig {
  top_k: number;
  strategy: string;
  vector_weight: number;
  bm25_weight: number;
  chunk_strategy: string;
  chunk_params: { max_chunk_size: number; overlap: number };
}

export interface Conversation {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
  system_prompt?: string;
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  timestamp?: string;
}

export interface MemoryEntry {
  id: string;
  content: string;
  category: string;
  created_at: string;
  importance: number;
}

export interface MemoryData {
  entries: MemoryEntry[];
  summary: string;
}

export interface PipelineStep {
  name: string;
  role_prompt: string;
  kb_names: string[];
  top_k: number;
  enabled: boolean;
}

export interface PipelineConfig {
  enabled: boolean;
  steps: PipelineStep[];
}

export interface PipelineResult {
  mode: string;
  answer: string;
  analysis?: string;
  review?: string;
  sources: string[];
  retrieval_results?: RetrievalResult[];
  steps_log?: { name: string; status: string; output_preview: string; latency: number }[];
  latency: number;
}

export interface ProviderInfo {
  id: string;
  name: string;
  models: string[];
}

export interface ConnectionStatus {
  llm?: { status: string; error?: string };
  embedding?: { status: string; dimension?: number; error?: string };
}

export interface DocumentInfo {
  filename: string;
  size_bytes: number;
  chunk_count: number;
  upload_time: string;
  chunk_strategy?: string;
  chunk_params?: Record<string, number>;
}

export interface ChunkInfo {
  chunk_id: string;
  content: string;
  source: string;
  heading_path: string[];
  metadata: Record<string, unknown>;
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  source: "builtin" | "custom" | "generated";
  enabled: boolean;
  tags: string[];
}

export interface ToolTestResult {
  result: string;
  error: string | null;
  duration_ms: number;
}

export interface GeneratedTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  code: string;
  warnings: string[];
}

export interface MCPStatus {
  running: boolean;
  tool_count: number;
  tools?: ToolDefinition[];
  error?: string;
}

export interface ToolCreateInput {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  code: string;
  tags?: string[];
}

export interface ToolUpdateInput {
  description?: string;
  parameters?: Record<string, unknown>;
  code?: string;
  enabled?: boolean;
  tags?: string[];
}

export interface Finding {
  id: string;
  type: "contradiction" | "duplicate" | "update";
  severity: "high" | "medium" | "low";
  new_chunk: { chunk_id: string; content: string; source: string };
  existing_chunk: { chunk_id: string; content: string; source: string };
  explanation: string;
  status: "open" | "resolved" | "dismissed";
  created_at: string;
}

export interface FindingsSummary {
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

export function useKBStudio() {
  const [currentKB, setCurrentKB] = useState<string | null>(null);
  const [kbList, setKBList] = useState<KnowledgeBase[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [statusKB, setStatusKB] = useState("未选择知识库");
  const [statusLLM, setStatusLLM] = useState("LLM 未配置");
  const [statusEmb, setStatusEmb] = useState("Embedding: 本地");

  const loadKBList = useCallback(async () => {
    const resp = await safeFetch(`${API}/kb/list`);
    const data = await resp.json();
    setKBList(data.knowledge_bases || []);
    return data.knowledge_bases || [];
  }, []);

  const createKB = useCallback(
    async (name: string, description: string, systemPrompt: string) => {
      const resp = await safeFetch(`${API}/kb/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description,
          system_prompt: systemPrompt,
        }),
      });
      const data = await resp.json();
      if (data.status === "ok") {
        await loadKBList();
        return { success: true };
      }
      return { success: false, error: data.detail || JSON.stringify(data) };
    },
    [loadKBList]
  );

  const deleteKB = useCallback(
    async (name: string) => {
      await safeFetch(`${API}/kb/${name}`, { method: "DELETE" });
      await loadKBList();
    },
    [loadKBList]
  );

  const selectKB = useCallback((name: string) => {
    setCurrentKB(name);
    setStatusKB(`知识库: ${name}`);
  }, []);

  const uploadFile = useCallback(
    async (file: File) => {
      if (!currentKB) return { success: false, error: "请先选择知识库" };
      const formData = new FormData();
      formData.append("file", file);
      const resp = await safeFetch(`${API}/kb/${currentKB}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await resp.json();
      if (data.status === "ok") {
        return { success: true, chunksAdded: data.chunks_added };
      }
      return { success: false, error: data.detail || JSON.stringify(data) };
    },
    [currentKB]
  );

  const sendMessage = useCallback(
    async (question: string, conversationId?: string): Promise<ChatResponse | null> => {
      if (!currentKB) return null;
      const resp = await safeFetch(`${API}/kb/${currentKB}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, conversation_id: conversationId }),
      });
      return resp.json();
    },
    [currentKB]
  );

  const clearHistory = useCallback(async () => {
    if (!currentKB) return;
    await fetch(`${API}/kb/${currentKB}/history`, { method: "DELETE" });
  }, [currentKB]);

  const testConnection = useCallback(async (): Promise<ConnectionStatus> => {
    const resp = await safeFetch(`${API}/test-connection`, { method: "POST" });
    const data = await resp.json();
    if (data.llm?.status === "ok") setStatusLLM("LLM ✓");
    else setStatusLLM("LLM ✗");
    if (data.embedding?.status === "ok")
      setStatusEmb(`Embedding: ${data.embedding.dimension}d`);
    else setStatusEmb("Embedding ✗");
    return data;
  }, []);

  const loadProviders = useCallback(async () => {
    const resp = await safeFetch(`${API}/providers`);
    const data = await resp.json();
    setProviders(data);
    return data;
  }, []);

  const saveConfig = useCallback(
    async (config: {
      llm: { provider: string; api_key: string; model: string; base_url: string };
      embedding: { provider: string; model: string; api_key: string };
    }) => {
      const resp = await safeFetch(`${API}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await resp.json();
      return data.status === "ok";
    },
    []
  );

  // ── Document Management ──

  const loadDocuments = useCallback(async (kbName: string): Promise<DocumentInfo[]> => {
    const resp = await safeFetch(`${API}/kb/${kbName}/documents`);
    const data = await resp.json();
    return data.documents || [];
  }, []);

  const getDocumentContent = useCallback(async (kbName: string, filename: string): Promise<string> => {
    const resp = await safeFetch(`${API}/kb/${kbName}/documents/${filename}`);
    const data = await resp.json();
    return data.content || "";
  }, []);

  const getDocumentChunks = useCallback(async (kbName: string, filename: string): Promise<ChunkInfo[]> => {
    const resp = await safeFetch(`${API}/kb/${kbName}/documents/${filename}/chunks`);
    const data = await resp.json();
    return data.chunks || [];
  }, []);

  const deleteDocument = useCallback(async (kbName: string, filename: string) => {
    const resp = await safeFetch(`${API}/kb/${kbName}/documents/${filename}`, { method: "DELETE" });
    const data = await resp.json();
    if (data.status === "ok") {
      await loadKBList();
      return { success: true, chunksRemoved: data.chunks_removed };
    }
    return { success: false, error: data.detail || "Delete failed" };
  }, [loadKBList]);

  const rechunkDocument = useCallback(async (
    kbName: string, filename: string,
    strategy: string, maxChunkSize: number, overlap: number
  ) => {
    const resp = await safeFetch(`${API}/kb/${kbName}/documents/${filename}/rechunk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy, max_chunk_size: maxChunkSize, overlap }),
    });
    const data = await resp.json();
    if (data.status === "ok") {
      return { success: true, oldCount: data.old_chunk_count, newCount: data.new_chunk_count };
    }
    return { success: false, error: data.detail || "Rechunk failed" };
  }, []);

  // ── Search & Retrieval Config ──

  const searchKB = useCallback(async (
    kbName: string, query: string,
    params: { top_k?: number; strategy?: string; vector_weight?: number; bm25_weight?: number } = {}
  ): Promise<SearchResult | null> => {
    const resp = await safeFetch(`${API}/kb/${kbName}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, ...params }),
    });
    return resp.json();
  }, []);

  const getRetrievalConfig = useCallback(async (kbName: string): Promise<RetrievalConfig> => {
    const resp = await safeFetch(`${API}/kb/${kbName}/config/retrieval`);
    return resp.json();
  }, []);

  const updateRetrievalConfig = useCallback(async (kbName: string, config: Partial<RetrievalConfig>) => {
    const resp = await safeFetch(`${API}/kb/${kbName}/config/retrieval`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    const data = await resp.json();
    return data.status === "ok";
  }, []);

  return {
    currentKB,
    setCurrentKB,
    kbList,
    providers,
    statusKB,
    statusLLM,
    statusEmb,
    loadKBList,
    createKB,
    deleteKB,
    selectKB,
    uploadFile,
    sendMessage,
    clearHistory,
    testConnection,
    loadProviders,
    saveConfig,
    loadDocuments,
    getDocumentContent,
    getDocumentChunks,
    deleteDocument,
    rechunkDocument,
    uploadURL: useCallback(async (url: string) => {
      if (!currentKB) return { success: false, error: "请先选择知识库" };
      const resp = await safeFetch(`${API}/kb/${currentKB}/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (data.status === "ok") {
        return { success: true, chunksAdded: data.chunks_added, file: data.file };
      }
      return { success: false, error: data.detail || "URL conversion failed" };
    }, [currentKB]),
    searchKB,
    getRetrievalConfig,
    updateRetrievalConfig,
    loadConversations: useCallback(async (kbName: string) => {
      const resp = await safeFetch(`${API}/kb/${kbName}/conversations`);
      const data = await resp.json();
      return data as { conversations: Conversation[]; active_conversation_id: string | null };
    }, []),
    createConversation: useCallback(async (kbName: string, convName: string = "New Chat") => {
      const resp = await safeFetch(`${API}/kb/${kbName}/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: convName }),
      });
      return resp.json();
    }, []),
    deleteConversation: useCallback(async (kbName: string, convId: string) => {
      await safeFetch(`${API}/kb/${kbName}/conversations/${convId}`, { method: "DELETE" });
    }, []),
    getConversationHistory: useCallback(async (kbName: string, convId: string): Promise<ConversationMessage[]> => {
      const resp = await safeFetch(`${API}/kb/${kbName}/conversations/${convId}`);
      const data = await resp.json();
      return data.messages || [];
    }, []),
    renameConversation: useCallback(async (kbName: string, convId: string, newName: string) => {
      await safeFetch(`${API}/kb/${kbName}/conversations/${convId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName }),
      });
    }, []),
    exportConversation: useCallback(async (kbName: string, convId: string) => {
      const resp = await safeFetch(`${API}/kb/${kbName}/conversations/${convId}/export`);
      const data = await resp.json();
      return data.content || "";
    }, []),
    setActiveConversation: useCallback(async (kbName: string, convId: string) => {
      await safeFetch(`${API}/kb/${kbName}/conversations/${convId}/set-active`, { method: "POST" });
    }, []),

    // ── Memory ──
    loadMemory: useCallback(async (kbName: string): Promise<MemoryData> => {
      const resp = await safeFetch(`${API}/kb/${kbName}/memory`);
      return resp.json();
    }, []),
    addMemory: useCallback(async (kbName: string, content: string, category: string = "general", importance: number = 0.5) => {
      const resp = await safeFetch(`${API}/kb/${kbName}/memory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, category, importance }),
      });
      return resp.json();
    }, []),
    deleteMemory: useCallback(async (kbName: string, entryId: string) => {
      await safeFetch(`${API}/kb/${kbName}/memory/${entryId}`, { method: "DELETE" });
    }, []),
    updateMemorySummary: useCallback(async (kbName: string, summary: string) => {
      await safeFetch(`${API}/kb/${kbName}/memory/summary`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary }),
      });
    }, []),

    // ── Pipeline ──
    loadPipeline: useCallback(async (kbName: string): Promise<PipelineConfig> => {
      const resp = await safeFetch(`${API}/kb/${kbName}/pipeline`);
      return resp.json();
    }, []),
    updatePipeline: useCallback(async (kbName: string, config: PipelineConfig) => {
      await safeFetch(`${API}/kb/${kbName}/pipeline`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
    }, []),
    pipelineChat: useCallback(async (kbName: string, question: string, conversationId?: string): Promise<PipelineResult | null> => {
      const resp = await safeFetch(`${API}/kb/${kbName}/pipeline/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, conversation_id: conversationId }),
      });
      return resp.json();
    }, []),

    // ── Tools ──
    loadTools: useCallback(async (source?: string): Promise<ToolDefinition[]> => {
      const url = source ? `${API}/tools?source=${source}` : `${API}/tools`;
      const resp = await safeFetch(url);
      const data = await resp.json();
      return data.tools || [];
    }, []),
    getTool: useCallback(async (name: string) => {
      const resp = await safeFetch(`${API}/tools/${name}`);
      return resp.json();
    }, []),
    createTool: useCallback(async (tool: ToolCreateInput) => {
      const resp = await safeFetch(`${API}/tools`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tool),
      });
      return resp.json();
    }, []),
    updateTool: useCallback(async (name: string, updates: ToolUpdateInput) => {
      const resp = await safeFetch(`${API}/tools/${name}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      return resp.json();
    }, []),
    deleteTool: useCallback(async (name: string) => {
      await safeFetch(`${API}/tools/${name}`, { method: "DELETE" });
    }, []),
    testTool: useCallback(async (name: string, args: Record<string, unknown> = {}): Promise<ToolTestResult> => {
      const resp = await safeFetch(`${API}/tools/${name}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ args }),
      });
      return resp.json();
    }, []),
    toggleTool: useCallback(async (name: string, enabled: boolean) => {
      const action = enabled ? "enable" : "disable";
      await safeFetch(`${API}/tools/${name}/${action}`, { method: "POST" });
    }, []),
    generateTool: useCallback(async (description: string, context: string = "") => {
      const resp = await safeFetch(`${API}/tools/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description, context }),
      });
      return resp.json();
    }, []),
    refineTool: useCallback(async (code: string, feedback: string) => {
      const resp = await safeFetch(`${API}/tools/generate/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, feedback }),
      });
      return resp.json();
    }, []),
    saveGeneratedTool: useCallback(async (tool: ToolCreateInput) => {
      const resp = await safeFetch(`${API}/tools/generate/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tool),
      });
      return resp.json();
    }, []),
    loadMCPStatus: useCallback(async (): Promise<MCPStatus> => {
      const resp = await safeFetch(`${API}/mcp/status`);
      return resp.json();
    }, []),
    getMCPConfig: useCallback(async (host: string = "localhost", port: number = 8000) => {
      const resp = await safeFetch(`${API}/mcp/config?host=${host}&port=${port}`);
      return resp.json();
    }, []),

    // ── Findings (Knowledge Quality) ──
    loadFindings: useCallback(async (kbName: string, typeFilter?: string, statusFilter?: string): Promise<Finding[]> => {
      let url = `${API}/kb/${kbName}/findings`;
      const params = new URLSearchParams();
      if (typeFilter) params.set("type", typeFilter);
      if (statusFilter) params.set("status", statusFilter);
      const qs = params.toString();
      if (qs) url += `?${qs}`;
      const resp = await safeFetch(url);
      const data = await resp.json();
      return data.findings || [];
    }, []),
    loadFindingsSummary: useCallback(async (kbName: string): Promise<FindingsSummary> => {
      const resp = await safeFetch(`${API}/kb/${kbName}/findings/summary`);
      return resp.json();
    }, []),
    resolveFinding: useCallback(async (kbName: string, findingId: string) => {
      await safeFetch(`${API}/kb/${kbName}/findings/${findingId}/resolve`, { method: "POST" });
    }, []),
    dismissFinding: useCallback(async (kbName: string, findingId: string) => {
      await safeFetch(`${API}/kb/${kbName}/findings/${findingId}/dismiss`, { method: "POST" });
    }, []),
    analyzeKB: useCallback(async (kbName: string) => {
      const resp = await safeFetch(`${API}/kb/${kbName}/analyze`, { method: "POST" });
      return resp.json();
    }, []),

    // ── Scheduler ──
    loadSchedulerStatus: useCallback(async () => {
      const resp = await safeFetch(`${API}/scheduler/status`);
      return resp.json();
    }, []),
    loadScheduledTasks: useCallback(async (taskType?: string) => {
      const url = taskType ? `${API}/scheduler/tasks?task_type=${taskType}` : `${API}/scheduler/tasks`;
      const resp = await safeFetch(url);
      const data = await resp.json();
      return data.tasks || [];
    }, []),
    createScheduledTask: useCallback(async (task: { name: string; task_type: string; interval: string; config?: Record<string, unknown>; description?: string }) => {
      const resp = await safeFetch(`${API}/scheduler/tasks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(task) });
      return resp.json();
    }, []),
    deleteScheduledTask: useCallback(async (taskId: string) => {
      await safeFetch(`${API}/scheduler/tasks/${taskId}`, { method: "DELETE" });
    }, []),
    runScheduledTask: useCallback(async (taskId: string) => {
      const resp = await safeFetch(`${API}/scheduler/tasks/${taskId}/run`, { method: "POST" });
      return resp.json();
    }, []),
    pauseScheduledTask: useCallback(async (taskId: string) => {
      const resp = await safeFetch(`${API}/scheduler/tasks/${taskId}/pause`, { method: "POST" });
      return resp.json();
    }, []),
    resumeScheduledTask: useCallback(async (taskId: string) => {
      const resp = await safeFetch(`${API}/scheduler/tasks/${taskId}/resume`, { method: "POST" });
      return resp.json();
    }, []),

    // ── Notifications ──
    loadNotifications: useCallback(async (limit = 50, unreadOnly = false) => {
      const resp = await safeFetch(`${API}/notifications?limit=${limit}&unread_only=${unreadOnly}`);
      return resp.json();
    }, []),
    markNotificationRead: useCallback(async (id: string) => {
      await safeFetch(`${API}/notifications/${id}/read`, { method: "POST" });
    }, []),
    markAllNotificationsRead: useCallback(async () => {
      await safeFetch(`${API}/notifications/read-all`, { method: "POST" });
    }, []),
    deleteNotification: useCallback(async (id: string) => {
      await safeFetch(`${API}/notifications/${id}`, { method: "DELETE" });
    }, []),

    // ── Source Monitor ──
    loadSourceWatches: useCallback(async (kbName?: string) => {
      const url = kbName ? `${API}/sources?kb_name=${kbName}` : `${API}/sources`;
      const resp = await safeFetch(url);
      const data = await resp.json();
      return data.watches || [];
    }, []),
    addSourceWatch: useCallback(async (watch: { url: string; kb_name: string; name?: string; watch_type?: string; interval?: string }) => {
      const resp = await safeFetch(`${API}/sources`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(watch) });
      return resp.json();
    }, []),
    deleteSourceWatch: useCallback(async (watchId: string) => {
      await safeFetch(`${API}/sources/${watchId}`, { method: "DELETE" });
    }, []),
    toggleSourceWatch: useCallback(async (watchId: string) => {
      const resp = await safeFetch(`${API}/sources/${watchId}/toggle`, { method: "POST" });
      return resp.json();
    }, []),
    checkSourceNow: useCallback(async (watchId: string) => {
      const resp = await safeFetch(`${API}/sources/${watchId}/check`, { method: "POST" });
      return resp.json();
    }, []),

    // ── Suggestions ──
    loadSuggestions: useCallback(async () => {
      const resp = await safeFetch(`${API}/suggestions`);
      const data = await resp.json();
      return data.suggestions || [];
    }, []),
    generateSuggestions: useCallback(async () => {
      const resp = await safeFetch(`${API}/suggestions/generate`, { method: "POST" });
      return resp.json();
    }, []),
    dismissSuggestion: useCallback(async (id: string) => {
      await safeFetch(`${API}/suggestions/${id}/dismiss`, { method: "POST" });
    }, []),

    // ── Global Memory ──
    loadGlobalMemory: useCallback(async () => {
      const resp = await safeFetch(`${API}/memory/global`);
      return resp.json();
    }, []),
    loadGlobalMemorySummary: useCallback(async () => {
      const resp = await safeFetch(`${API}/memory/global/summary`);
      return resp.json();
    }, []),
    syncGlobalMemory: useCallback(async () => {
      const resp = await safeFetch(`${API}/memory/global/sync`, { method: "POST" });
      return resp.json();
    }, []),

    // ── Staleness ──
    loadStaleness: useCallback(async () => {
      const resp = await safeFetch(`${API}/staleness`);
      return resp.json();
    }, []),

    // ── Export ──
    getExportURL: useCallback((type: string, kbName?: string) => {
      if (type === "all") return `${API}/export/all/zip`;
      if (kbName) return `${API}/export/kb/${kbName}/${type}`;
      return "";
    }, []),

    // ── Import ──
    importKB: useCallback(async (file: File, name?: string) => {
      const formData = new FormData();
      formData.append("file", file);
      if (name) formData.append("name", name);
      const resp = await fetch(`${API}/import/kb`, { method: "POST", body: formData });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: "Import failed" }));
        throw new Error(err.detail || "Import failed");
      }
      return resp.json();
    }, []),
  };
}
