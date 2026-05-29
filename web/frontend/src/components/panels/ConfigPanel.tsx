"use client";

import { useState, useEffect } from "react";
import { ProviderInfo, ConnectionStatus } from "@/hooks/useKBStudio";

interface ConfigPanelProps {
  providers: ProviderInfo[];
  onTestConnection: () => Promise<ConnectionStatus>;
  onSaveConfig: (config: {
    llm: { provider: string; api_key: string; model: string; base_url: string };
    embedding: { provider: string; model: string; api_key: string };
  }) => Promise<boolean>;
  onLoadProviders: () => Promise<ProviderInfo[]>;
}

const providerModels: Record<string, string> = {
  deepseek: "deepseek-chat",
  qwen: "qwen-max",
  zhipu: "glm-4-plus",
  moonshot: "moonshot-v1-128k",
  claude: "claude-sonnet-4-6",
  openai: "gpt-4o",
  ollama: "qwen2.5:7b",
};

export default function ConfigPanel({
  providers,
  onTestConnection,
  onSaveConfig,
  onLoadProviders,
}: ConfigPanelProps) {
  const [llmProvider, setLlmProvider] = useState("deepseek");
  const [llmModel, setLlmModel] = useState("deepseek-chat");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [embProvider, setEmbProvider] = useState("local");
  const [embModel, setEmbModel] = useState("BAAI/bge-small-zh-v1.5");
  const [embApiKey, setEmbApiKey] = useState("");
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedProviderCard, setSelectedProviderCard] = useState<string | null>(null);

  useEffect(() => {
    onLoadProviders();
  }, []); // eslint-disable-line

  const handleTestConnection = async () => {
    setTesting(true);
    const status = await onTestConnection();
    setConnectionStatus(status);
    setTesting(false);
  };

  const handleSelectProvider = (id: string, model: string) => {
    setLlmProvider(id);
    setLlmModel(model);
    setSelectedProviderCard(id);
  };

  const handleProviderChange = (value: string) => {
    setLlmProvider(value);
    setLlmModel(providerModels[value] || "");
    setSelectedProviderCard(value);
  };

  const handleSave = async () => {
    setSaving(true);
    const ok = await onSaveConfig({
      llm: { provider: llmProvider, api_key: llmApiKey, model: llmModel, base_url: llmBaseUrl },
      embedding: { provider: embProvider, model: embModel, api_key: embApiKey },
    });
    setSaving(false);
    if (ok) alert("配置已保存！");
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5" style={{ animation: "fade-in 0.3s ease-out" }}>
      {/* Connection Test */}
      <div className="cyber-card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tiffany">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
            <h3 className="text-sm font-semibold tracking-wide text-cyber-text uppercase">连接测试</h3>
          </div>
          <button onClick={handleTestConnection} disabled={testing} className="cyber-btn cyber-btn-lavender text-[11px]">
            {testing ? "测试中..." : "// 测试连接"}
          </button>
        </div>

        {connectionStatus && (
          <div className="space-y-2">
            {connectionStatus.llm && (
              <div className={`flex items-center gap-2 px-3 py-2 rounded text-[12px] ${
                connectionStatus.llm.status === "ok"
                  ? "bg-cyber-green/5 border border-cyber-green/20 text-cyber-green"
                  : "bg-cyber-red/5 border border-cyber-red/20 text-cyber-red"
              }`}>
                <span className="w-1.5 h-1.5 rounded-full" style={{
                  background: connectionStatus.llm.status === "ok" ? "var(--color-cyber-green)" : "var(--color-cyber-red)",
                  boxShadow: `0 0 6px ${connectionStatus.llm.status === "ok" ? "var(--color-cyber-glow-green-strong)" : "var(--color-cyber-glow-red)"}`,
                }} />
                LLM: {connectionStatus.llm.status === "ok" ? "连接成功" : connectionStatus.llm.error}
              </div>
            )}
            {connectionStatus.embedding && (
              <div className={`flex items-center gap-2 px-3 py-2 rounded text-[12px] ${
                connectionStatus.embedding.status === "ok"
                  ? "bg-cyber-green/5 border border-cyber-green/20 text-cyber-green"
                  : "bg-cyber-red/5 border border-cyber-red/20 text-cyber-red"
              }`}>
                <span className="w-1.5 h-1.5 rounded-full" style={{
                  background: connectionStatus.embedding.status === "ok" ? "var(--color-cyber-green)" : "var(--color-cyber-red)",
                  boxShadow: `0 0 6px ${connectionStatus.embedding.status === "ok" ? "var(--color-cyber-glow-green-strong)" : "var(--color-cyber-glow-red)"}`,
                }} />
                Embedding: {connectionStatus.embedding.status === "ok"
                  ? `连接成功 (维度: ${connectionStatus.embedding.dimension})`
                  : connectionStatus.embedding.error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Provider Grid */}
      <div className="cyber-card">
        <div className="flex items-center gap-2 mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-lavender">
            <rect x="2" y="3" width="20" height="14" rx="2" />
            <path d="M8 21h8m-4-4v4" />
          </svg>
          <h3 className="text-sm font-semibold tracking-wide text-cyber-text uppercase">LLM 提供商</h3>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {providers.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelectProvider(p.id, p.models[0])}
              className={`relative p-3 rounded text-left transition-all ${
                selectedProviderCard === p.id
                  ? "bg-tiffany/10 border border-tiffany/40"
                  : "bg-cyber-bg border border-cyber-border hover:border-lavender/40 hover:bg-lavender-glow"
              }`}
            >
              {selectedProviderCard === p.id && (
                <div className="absolute top-1.5 right-1.5 w-4 h-4 bg-tiffany text-cyber-bg rounded-full flex items-center justify-center">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              )}
              <div className="text-[12px] font-semibold text-cyber-text mb-0.5">{p.name}</div>
              <div className="text-[9px] text-cyber-text-muted mb-1">{p.id}</div>
              <div className="text-[10px] text-cyber-text-dim truncate">{p.models.slice(0, 2).join(", ")}</div>
            </button>
          ))}
        </div>
      </div>

      {/* LLM Config Form */}
      <div className="cyber-card">
        <div className="flex items-center gap-2 mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-tiffany">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.73 12.73l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
          </svg>
          <h3 className="text-sm font-semibold tracking-wide text-cyber-text uppercase">LLM 配置</h3>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">提供商</label>
            <select value={llmProvider} onChange={(e) => handleProviderChange(e.target.value)} className="cyber-input">
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">通义千问</option>
              <option value="zhipu">智谱 GLM</option>
              <option value="moonshot">Moonshot (Kimi)</option>
              <option value="claude">Anthropic Claude</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama (本地)</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">模型</label>
            <input
              type="text"
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              className="cyber-input"
              placeholder="deepseek-chat"
            />
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">API Key</label>
          <input
            type="password"
            value={llmApiKey}
            onChange={(e) => setLlmApiKey(e.target.value)}
            className="cyber-input"
            placeholder="sk-..."
          />
        </div>

        <div className="mb-4">
          <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">
            Base URL（可选）
          </label>
          <input
            type="text"
            value={llmBaseUrl}
            onChange={(e) => setLlmBaseUrl(e.target.value)}
            className="cyber-input"
            placeholder="https://api.deepseek.com/v1"
          />
        </div>

        <button onClick={handleSave} disabled={saving} className="cyber-btn cyber-btn-primary">
          {saving ? "保存中..." : "// 保存配置"}
        </button>
      </div>

      {/* Embedding Config */}
      <div className="cyber-card">
        <div className="flex items-center gap-2 mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-lavender">
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" />
          </svg>
          <h3 className="text-sm font-semibold tracking-wide text-cyber-text uppercase">Embedding 配置</h3>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">提供商</label>
            <select value={embProvider} onChange={(e) => setEmbProvider(e.target.value)} className="cyber-input">
              <option value="local">本地模型（推荐）</option>
              <option value="api">API 服务</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">模型</label>
            <input
              type="text"
              value={embModel}
              onChange={(e) => setEmbModel(e.target.value)}
              className="cyber-input"
            />
          </div>
        </div>

        {embProvider === "api" && (
          <div>
            <label className="block text-[11px] text-cyber-text-muted mb-1.5 tracking-wider uppercase">API Key</label>
            <input
              type="password"
              value={embApiKey}
              onChange={(e) => setEmbApiKey(e.target.value)}
              className="cyber-input"
              placeholder="输入 Embedding API Key"
            />
          </div>
        )}
      </div>
    </div>
  );
}
