"use client";

import { useState, useEffect, useCallback } from "react";

interface ButlerPanelProps {
  kbList: Array<{ name: string }>;
  onLoadSchedulerStatus: () => Promise<{ running: boolean; total_tasks: number; active_tasks: number; paused_tasks: number }>;
  onLoadScheduledTasks: (type?: string) => Promise<ScheduledTask[]>;
  onCreateScheduledTask: (task: { name: string; task_type: string; interval: string; config?: Record<string, unknown>; description?: string }) => Promise<{ status: string; task?: ScheduledTask }>;
  onDeleteScheduledTask: (id: string) => Promise<void>;
  onRunScheduledTask: (id: string) => Promise<{ status: string; run?: TaskRun }>;
  onPauseScheduledTask: (id: string) => Promise<void>;
  onResumeScheduledTask: (id: string) => Promise<void>;
  onLoadNotifications: (limit?: number, unreadOnly?: boolean) => Promise<{ notifications: Notification[]; unread_count: number }>;
  onMarkNotificationRead: (id: string) => Promise<void>;
  onMarkAllNotificationsRead: () => Promise<void>;
  onDeleteNotification: (id: string) => Promise<void>;
  onLoadSourceWatches: (kbName?: string) => Promise<SourceWatch[]>;
  onAddSourceWatch: (watch: { url: string; kb_name: string; name?: string; watch_type?: string; interval?: string }) => Promise<{ status: string; watch?: SourceWatch }>;
  onDeleteSourceWatch: (id: string) => Promise<void>;
  onToggleSourceWatch: (id: string) => Promise<void>;
  onCheckSourceNow: (id: string) => Promise<{ status: string }>;
  getExportURL: (type: string, kbName?: string) => string;
  onImportKB?: (file: File, name?: string) => Promise<{ status: string; kb_name: string; doc_count: number; chunk_count: number }>;
  onLoadStaleness?: () => Promise<{ total_docs: number; fresh: number; aging: number; stale: number; stale_docs: Array<{ kb: string; doc: string; age_days: number }> }>;
  onLoadGlobalMemorySummary?: () => Promise<{ total_entries: number; by_category: Record<string, number>; by_kb: Record<string, number>; interests: string[]; preferences: string[]; last_sync: string | null }>;
  onSyncGlobalMemory?: () => Promise<{ status: string; new_entries: number; total: number }>;
  onLoadSuggestions?: () => Promise<Array<{ id: string; title: string; body: string; action: string; category: string; priority: string; details: Record<string, unknown>; created_at: string; dismissed: boolean }>>;
  onGenerateSuggestions?: () => Promise<{ status: string; new_count: number }>;
  onDismissSuggestion?: (id: string) => Promise<void>;
}

interface ScheduledTask {
  task_id: string;
  name: string;
  task_type: string;
  interval: string;
  status: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  last_result: string | null;
  description: string;
}

interface TaskRun {
  run_id: string;
  started_at: string;
  status: string;
  result_summary: string;
  error: string | null;
}

interface Notification {
  id: string;
  title: string;
  body: string;
  level: string;
  source: string;
  read: boolean;
  created_at: string;
  task_id: string | null;
}

interface SourceWatch {
  watch_id: string;
  url: string;
  kb_name: string;
  name: string;
  watch_type: string;
  interval: string;
  enabled: boolean;
  last_fetched_at: string | null;
  last_change_at: string | null;
  fetch_count: number;
  change_count: number;
  last_error: string | null;
}

const INTERVAL_LABELS: Record<string, string> = {
  "5m": "5 分钟", "15m": "15 分钟", "30m": "30 分钟",
  "1h": "1 小时", "6h": "6 小时", "12h": "12 小时", "1d": "每天", "1w": "每周",
};

const TASK_TYPE_LABELS: Record<string, string> = {
  source_monitor: "源监控", kb_analyze: "知识库分析", digest: "摘要生成", memory_sync: "记忆同步", custom: "自定义",
};

const LEVEL_COLORS: Record<string, string> = {
  info: "text-cyber-blue", warning: "text-cyber-yellow", error: "text-cyber-red", success: "text-cyber-green",
};

const LEVEL_BG: Record<string, string> = {
  info: "bg-cyber-blue/10 border-cyber-blue/20", warning: "bg-cyber-yellow/10 border-cyber-yellow/20",
  error: "bg-cyber-red/10 border-cyber-red/20", success: "bg-cyber-green/10 border-cyber-green/20",
};

export default function ButlerPanel(props: ButlerPanelProps) {
  const [tab, setTab] = useState<"overview" | "tasks" | "sources" | "notifications" | "export">("overview");
  const [schedulerStatus, setSchedulerStatus] = useState<{ running: boolean; total_tasks: number; active_tasks: number } | null>(null);
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [watches, setWatches] = useState<SourceWatch[]>([]);
  const [staleness, setStaleness] = useState<{ total_docs: number; fresh: number; aging: number; stale: number; stale_docs: Array<{ kb: string; doc: string; age_days: number }> } | null>(null);
  const [memorySummary, setMemorySummary] = useState<{ total_entries: number; by_category: Record<string, number>; interests: string[]; preferences: string[]; last_sync: string | null } | null>(null);
  const [suggestions, setSuggestions] = useState<Array<{ id: string; title: string; body: string; action: string; category: string; priority: string; details: Record<string, unknown>; created_at: string; dismissed: boolean }>>([]);
  const [loading, setLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);

  // New task form
  const [newTaskName, setNewTaskName] = useState("");
  const [newTaskType, setNewTaskType] = useState("source_monitor");
  const [newTaskInterval, setNewTaskInterval] = useState("1d");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskKb, setNewTaskKb] = useState("");

  // New source form
  const [newSourceUrl, setNewSourceUrl] = useState("");
  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceKb, setNewSourceKb] = useState("");
  const [newSourceInterval, setNewSourceInterval] = useState("1d");

  const refreshAll = useCallback(async () => {
    try {
      const [status, taskList, notifData, watchList] = await Promise.all([
        props.onLoadSchedulerStatus(),
        props.onLoadScheduledTasks(),
        props.onLoadNotifications(30),
        props.onLoadSourceWatches(),
      ]);
      setSchedulerStatus(status);
      setTasks(taskList);
      setNotifications(notifData.notifications);
      setUnreadCount(notifData.unread_count);
      setWatches(watchList);
      // Fetch staleness and memory (optional)
      if (props.onLoadStaleness) {
        try { setStaleness(await props.onLoadStaleness()); } catch { /* ignore */ }
      }
      if (props.onLoadGlobalMemorySummary) {
        try { setMemorySummary(await props.onLoadGlobalMemorySummary()); } catch { /* ignore */ }
      }
      if (props.onLoadSuggestions) {
        try { setSuggestions(await props.onLoadSuggestions()); } catch { /* ignore */ }
      }
    } catch (e) {
      console.error("Failed to refresh butler data:", e);
    }
  }, [props]);

  useEffect(() => { refreshAll(); }, [refreshAll]);

  const handleCreateTask = async () => {
    if (!newTaskName.trim()) return;
    setLoading(true);
    try {
      await props.onCreateScheduledTask({
        name: newTaskName,
        task_type: newTaskType,
        interval: newTaskInterval,
        description: newTaskDesc,
        config: newTaskKb ? { kb_name: newTaskKb } : {},
      });
      setNewTaskName(""); setNewTaskDesc(""); setNewTaskKb("");
      await refreshAll();
    } finally { setLoading(false); }
  };

  const handleAddSource = async () => {
    if (!newSourceUrl.trim() || !newSourceKb.trim()) return;
    setLoading(true);
    try {
      await props.onAddSourceWatch({ url: newSourceUrl, kb_name: newSourceKb, name: newSourceName, interval: newSourceInterval });
      setNewSourceUrl(""); setNewSourceName(""); setNewSourceKb("");
      await refreshAll();
    } finally { setLoading(false); }
  };

  const formatTime = (iso: string | null) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
  };

  const timeAgo = (iso: string | null) => {
    if (!iso) return "";
    try {
      const diff = Date.now() - new Date(iso).getTime();
      if (diff < 60000) return "刚刚";
      if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
      return `${Math.floor(diff / 86400000)} 天前`;
    } catch { return ""; }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ animation: "fade-in 0.3s ease-out" }}>
      {/* Tab bar */}
      <div className="flex items-center shrink-0" style={{ borderBottom: "2px solid var(--color-cyber-border)" }}>
        {(["overview", "tasks", "sources", "notifications", "export"] as const).map((t) => {
          const labels = { overview: "总览", tasks: "定时任务", sources: "源监控", notifications: "通知", export: "导出" };
          return (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 text-[11px] tracking-wider uppercase transition-colors relative ${tab === t ? "text-tiffany border-b-2 border-tiffany" : "text-cyber-text-muted hover:text-cyber-text"}`}>
              {labels[t]}
              {t === "notifications" && unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-3.5 h-3.5 flex items-center justify-center text-[8px] font-bold bg-cyber-red text-white rounded-full">{unreadCount > 9 ? "9+" : unreadCount}</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex-1 overflow-y-auto p-4" style={{ background: "var(--color-cyber-content-bg)" }}>
        {/* ── Overview ── */}
        {tab === "overview" && (
          <div className="max-w-4xl space-y-4">
            {/* Proactive Suggestions */}
            {suggestions.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">管家建议 SUGGESTIONS</div>
                  {props.onGenerateSuggestions && (
                    <button onClick={async () => {
                      if (props.onGenerateSuggestions) {
                        await props.onGenerateSuggestions();
                        await refreshAll();
                      }
                    }} className="text-[9px] text-cyber-text-muted hover:text-tiffany">刷新建议</button>
                  )}
                </div>
                <div className="space-y-1.5">
                  {suggestions.filter(s => !s.dismissed).slice(0, 5).map((s) => {
                    const prioColor = s.priority === "high" ? "border-cyber-red/30 bg-cyber-red/5" : s.priority === "normal" ? "border-tiffany/20 bg-tiffany/5" : "border-cyber-border bg-cyber-card";
                    const catIcon: Record<string, string> = { staleness: "\u{26A0}\u{FE0F}", interest: "\u{1F4A1}", quality: "\u{1F50D}", pattern: "\u{1F4CA}" };
                    return (
                      <div key={s.id} className={`border rounded-lg p-3 flex items-start gap-3 ${prioColor}`}>
                        <span className="text-sm mt-0.5">{catIcon[s.category] || "\u{1F4CC}"}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-[11px] text-cyber-text font-semibold">{s.title}</div>
                          <div className="text-[10px] text-cyber-text-dim mt-0.5">{s.body}</div>
                        </div>
                        {props.onDismissSuggestion && (
                          <button onClick={async () => {
                            await props.onDismissSuggestion!(s.id);
                            setSuggestions(prev => prev.filter(x => x.id !== s.id));
                          }} className="text-[9px] text-cyber-text-muted hover:text-cyber-red shrink-0">忽略</button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase mb-2">管家状态 BUTLER STATUS</div>
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "调度器", value: schedulerStatus?.running ? "运行中" : "已停止", color: schedulerStatus?.running ? "text-cyber-green" : "text-cyber-red" },
                { label: "定时任务", value: `${schedulerStatus?.active_tasks || 0} 活跃`, color: "text-tiffany" },
                { label: "源监控", value: `${watches.filter(w => w.enabled).length} 个`, color: "text-lavender" },
                { label: "未读通知", value: `${unreadCount}`, color: unreadCount > 0 ? "text-cyber-yellow" : "text-cyber-text-muted" },
              ].map(({ label, value, color }) => (
                <div key={label} className="cyber-card p-3 text-center">
                  <div className={`text-[18px] font-bold ${color}`}>{value}</div>
                  <div className="text-[10px] text-cyber-text-muted mt-1">{label}</div>
                </div>
              ))}
            </div>

            {/* Staleness overview */}
            {staleness && staleness.total_docs > 0 && (
              <div>
                <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase mb-2">文档新鲜度 FRESHNESS</div>
                <div className="cyber-card p-3">
                  <div className="flex items-center gap-4 mb-2">
                    <span className="flex items-center gap-1.5 text-[11px]">
                      <span className="w-2 h-2 rounded-full bg-cyber-green" /> {staleness.fresh} 新鲜
                    </span>
                    <span className="flex items-center gap-1.5 text-[11px]">
                      <span className="w-2 h-2 rounded-full bg-cyber-yellow" /> {staleness.aging} 老化
                    </span>
                    <span className="flex items-center gap-1.5 text-[11px]">
                      <span className="w-2 h-2 rounded-full bg-cyber-red" /> {staleness.stale} 过期
                    </span>
                    <span className="text-[10px] text-cyber-text-muted">共 {staleness.total_docs} 篇</span>
                  </div>
                  {staleness.stale_docs.length > 0 && (
                    <div className="space-y-1">
                      {staleness.stale_docs.slice(0, 3).map((d, i) => (
                        <div key={i} className="text-[10px] text-cyber-red flex items-center gap-2">
                          <span className="font-mono">{d.kb}</span>
                          <span className="text-cyber-text-muted">/</span>
                          <span className="truncate">{d.doc}</span>
                          <span className="text-cyber-text-muted shrink-0">{d.age_days} 天前</span>
                        </div>
                      ))}
                      {staleness.stale_docs.length > 3 && (
                        <div className="text-[10px] text-cyber-text-muted">还有 {staleness.stale_docs.length - 3} 篇...</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* User Profile / Memory */}
            {memorySummary && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">用户画像 PROFILE</div>
                  {props.onSyncGlobalMemory && (
                    <button onClick={async () => {
                      if (props.onSyncGlobalMemory) {
                        const r = await props.onSyncGlobalMemory();
                        alert(`同步完成：${r.new_entries} 条新记忆，共 ${r.total} 条`);
                        await refreshAll();
                      }
                    }} className="text-[9px] text-cyber-text-muted hover:text-tiffany">同步记忆</button>
                  )}
                </div>
                <div className="cyber-card p-3 space-y-2">
                  {memorySummary.interests.length > 0 && (
                    <div>
                      <div className="text-[10px] text-cyber-text-muted mb-1">关注领域</div>
                      <div className="flex flex-wrap gap-1.5">
                        {memorySummary.interests.slice(-10).map((t, i) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] bg-tiffany/10 text-tiffany border border-tiffany/20">{t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {memorySummary.preferences.length > 0 && (
                    <div>
                      <div className="text-[10px] text-cyber-text-muted mb-1">偏好</div>
                      <div className="flex flex-wrap gap-1.5">
                        {memorySummary.preferences.slice(-5).map((p, i) => (
                          <span key={i} className="px-2 py-0.5 rounded text-[10px] bg-lavender/10 text-lavender border border-lavender/20">{p}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="text-[10px] text-cyber-text-muted">
                    共 {memorySummary.total_entries} 条记忆
                    {memorySummary.last_sync && ` · 上次同步: ${new Date(memorySummary.last_sync).toLocaleString("zh-CN")}`}
                  </div>
                </div>
              </div>
            )}

            {/* Recent notifications */}
            <div>
              <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase mb-2">最近通知 RECENT</div>
              {notifications.length === 0 ? (
                <div className="cyber-card p-4 text-center text-[12px] text-cyber-text-muted">暂无通知</div>
              ) : (
                <div className="space-y-1.5">
                  {notifications.slice(0, 5).map((n) => (
                    <div key={n.id} className={`cyber-card p-3 flex items-start gap-3 ${n.read ? "opacity-60" : ""}`}>
                      <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${n.level === "error" ? "bg-cyber-red" : n.level === "warning" ? "bg-cyber-yellow" : "bg-cyber-green"}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-cyber-text font-semibold">{n.title}</div>
                        <div className="text-[10px] text-cyber-text-dim truncate">{n.body}</div>
                      </div>
                      <span className="text-[9px] text-cyber-text-muted shrink-0">{timeAgo(n.created_at)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Quick actions */}
            <div>
              <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase mb-2">快速操作 ACTIONS</div>
              <div className="flex gap-2 flex-wrap">
                <button onClick={() => setTab("tasks")} className="cyber-btn text-[10px]">创建定时任务</button>
                <button onClick={() => setTab("sources")} className="cyber-btn text-[10px]">添加监控源</button>
                <button onClick={() => setTab("export")} className="cyber-btn text-[10px]">导出数据</button>
              </div>
            </div>
          </div>
        )}

        {/* ── Tasks ── */}
        {tab === "tasks" && (
          <div className="max-w-4xl space-y-4">
            {/* Create task form */}
            <div className="cyber-card p-4 space-y-3">
              <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">创建定时任务 NEW TASK</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">任务名称</label>
                  <input value={newTaskName} onChange={(e) => setNewTaskName(e.target.value)} className="cyber-input text-[11px]" placeholder="每日知识库巡检" />
                </div>
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">类型</label>
                  <select value={newTaskType} onChange={(e) => setNewTaskType(e.target.value)} className="cyber-input text-[11px]">
                    <option value="source_monitor">源监控</option>
                    <option value="kb_analyze">知识库分析</option>
                    <option value="digest">摘要生成</option>
                    <option value="memory_sync">记忆同步</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">执行间隔</label>
                  <select value={newTaskInterval} onChange={(e) => setNewTaskInterval(e.target.value)} className="cyber-input text-[11px]">
                    {Object.entries(INTERVAL_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">关联知识库（可选）</label>
                  <select value={newTaskKb} onChange={(e) => setNewTaskKb(e.target.value)} className="cyber-input text-[11px]">
                    <option value="">全部</option>
                    {props.kbList.map(kb => <option key={kb.name} value={kb.name}>{kb.name}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-[10px] text-cyber-text-muted block mb-1">描述（可选）</label>
                <input value={newTaskDesc} onChange={(e) => setNewTaskDesc(e.target.value)} className="cyber-input text-[11px]" placeholder="每天检查所有源的更新" />
              </div>
              <button onClick={handleCreateTask} disabled={loading || !newTaskName.trim()} className="cyber-btn cyber-btn-primary text-[10px]">
                {loading ? "创建中..." : "创建任务"}
              </button>
            </div>

            {/* Task list */}
            <div className="space-y-1.5">
              {tasks.length === 0 && <div className="cyber-card p-4 text-center text-[12px] text-cyber-text-muted">暂无定时任务</div>}
              {tasks.map((t) => (
                <div key={t.task_id} className="cyber-card p-3 flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${t.enabled ? "bg-cyber-green" : "bg-cyber-text-muted"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-cyber-text font-semibold">{t.name}</span>
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-tiffany/10 text-tiffany">{TASK_TYPE_LABELS[t.task_type] || t.task_type}</span>
                      <span className="text-[9px] text-cyber-text-muted">{INTERVAL_LABELS[t.interval] || t.interval}</span>
                    </div>
                    <div className="text-[10px] text-cyber-text-dim truncate">
                      {t.last_result || "尚未执行"} {t.last_run_at ? `(${timeAgo(t.last_run_at)})` : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button onClick={() => { props.onRunScheduledTask(t.task_id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-tiffany" title="立即执行">运行</button>
                    <button onClick={() => { (t.enabled ? props.onPauseScheduledTask : props.onResumeScheduledTask)(t.task_id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-tiffany">
                      {t.enabled ? "暂停" : "恢复"}
                    </button>
                    <button onClick={() => { if (confirm(`确定删除任务 "${t.name}"？`)) props.onDeleteScheduledTask(t.task_id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-cyber-red">删除</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Sources ── */}
        {tab === "sources" && (
          <div className="max-w-4xl space-y-4">
            {/* Add source form */}
            <div className="cyber-card p-4 space-y-3">
              <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">添加监控源 NEW SOURCE</div>
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="text-[10px] text-cyber-text-muted block mb-1">URL</label>
                  <input value={newSourceUrl} onChange={(e) => setNewSourceUrl(e.target.value)} className="cyber-input text-[11px] font-mono" placeholder="https://example.com/docs" />
                </div>
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">名称（可选）</label>
                  <input value={newSourceName} onChange={(e) => setNewSourceName(e.target.value)} className="cyber-input text-[11px]" placeholder="竞品文档" />
                </div>
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">目标知识库</label>
                  <select value={newSourceKb} onChange={(e) => setNewSourceKb(e.target.value)} className="cyber-input text-[11px]">
                    <option value="">选择知识库</option>
                    {props.kbList.map(kb => <option key={kb.name} value={kb.name}>{kb.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-cyber-text-muted block mb-1">检查间隔</label>
                  <select value={newSourceInterval} onChange={(e) => setNewSourceInterval(e.target.value)} className="cyber-input text-[11px]">
                    {Object.entries(INTERVAL_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </div>
              </div>
              <button onClick={handleAddSource} disabled={loading || !newSourceUrl.trim() || !newSourceKb.trim()} className="cyber-btn cyber-btn-primary text-[10px]">
                {loading ? "添加中..." : "添加监控"}
              </button>
            </div>

            {/* Source list */}
            <div className="space-y-1.5">
              {watches.length === 0 && <div className="cyber-card p-4 text-center text-[12px] text-cyber-text-muted">暂无监控源</div>}
              {watches.map((w) => (
                <div key={w.watch_id} className="cyber-card p-3 flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${w.enabled ? "bg-cyber-green" : "bg-cyber-text-muted"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-cyber-text font-semibold truncate">{w.name || w.url}</span>
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-lavender/10 text-lavender">{w.kb_name}</span>
                      <span className="text-[9px] text-cyber-text-muted">{INTERVAL_LABELS[w.interval] || w.interval}</span>
                    </div>
                    <div className="text-[10px] text-cyber-text-dim">
                      {w.last_error ? <span className="text-cyber-red">{w.last_error}</span> : <>
                        已抓取 {w.fetch_count} 次，{w.change_count} 次变化
                        {w.last_change_at && <span> (最近: {timeAgo(w.last_change_at)})</span>}
                      </>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button onClick={() => { props.onCheckSourceNow(w.watch_id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-tiffany">检查</button>
                    <button onClick={() => { props.onToggleSourceWatch(w.watch_id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-tiffany">
                      {w.enabled ? "暂停" : "恢复"}
                    </button>
                    <button onClick={() => { if (confirm("确定删除？")) props.onDeleteSourceWatch(w.watch_id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-cyber-red">删除</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Notifications ── */}
        {tab === "notifications" && (
          <div className="max-w-4xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">通知 NOTIFICATIONS ({unreadCount} 未读)</div>
              <div className="flex gap-2">
                <button onClick={() => { props.onMarkAllNotificationsRead().then(refreshAll); }} className="text-[10px] text-cyber-text-muted hover:text-tiffany">全部已读</button>
              </div>
            </div>
            <div className="space-y-1.5">
              {notifications.length === 0 && <div className="cyber-card p-4 text-center text-[12px] text-cyber-text-muted">暂无通知</div>}
              {notifications.map((n) => (
                <div key={n.id} className={`border rounded-lg p-3 flex items-start gap-3 transition-all ${LEVEL_BG[n.level] || "bg-cyber-card border-cyber-border"} ${n.read ? "opacity-60" : ""}`}>
                  <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${n.level === "error" ? "bg-cyber-red" : n.level === "warning" ? "bg-cyber-yellow" : "bg-cyber-green"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-cyber-text font-semibold">{n.title}</div>
                    <div className="text-[10px] text-cyber-text-dim mt-0.5">{n.body}</div>
                    <div className="text-[9px] text-cyber-text-muted mt-1">{timeAgo(n.created_at)} · {n.source}</div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {!n.read && <button onClick={() => { props.onMarkNotificationRead(n.id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-tiffany">已读</button>}
                    <button onClick={() => { props.onDeleteNotification(n.id).then(refreshAll); }} className="text-[9px] text-cyber-text-muted hover:text-cyber-red">删除</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Export / Import ── */}
        {tab === "export" && (
          <div className="max-w-4xl space-y-4">
            {/* Import */}
            <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">导入 IMPORT</div>
            <div className="cyber-card p-4 space-y-3">
              <div className="text-[12px] text-cyber-text font-semibold">导入知识库包</div>
              <div className="text-[11px] text-cyber-text-dim">上传 KB-Studio 导出的 ZIP 文件，一键恢复知识库</div>
              <label className="cyber-btn text-[10px] cursor-pointer inline-block">
                {importLoading ? "导入中..." : "选择 ZIP 文件导入"}
                <input type="file" accept=".zip" className="hidden" onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file || !props.onImportKB) return;
                  setImportLoading(true);
                  try {
                    const result = await props.onImportKB(file);
                    alert(`导入成功！知识库 "${result.kb_name}"：${result.doc_count} 篇文档，${result.chunk_count} 个分块`);
                    await refreshAll();
                  } catch (err) {
                    alert("导入失败: " + (err instanceof Error ? err.message : String(err)));
                  } finally {
                    setImportLoading(false);
                    e.target.value = "";
                  }
                }} />
              </label>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex-1 h-px bg-cyber-border" />
              <span className="text-[9px] text-cyber-text-muted tracking-wider">或导出</span>
              <div className="flex-1 h-px bg-cyber-border" />
            </div>

            {/* Export */}
            <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">导出 EXPORT</div>

            <div className="cyber-card p-4 space-y-3">
              <div className="text-[12px] text-cyber-text font-semibold">完整备份</div>
              <div className="text-[11px] text-cyber-text-dim">导出所有知识库、配置、工具为 ZIP 包</div>
              <a href={props.getExportURL("all")} download className="cyber-btn cyber-btn-primary text-[10px] inline-block">下载完整备份 (.zip)</a>
            </div>

            {props.kbList.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] text-cyber-text-muted tracking-wider uppercase">按知识库导出</div>
                {props.kbList.map((kb) => (
                  <div key={kb.name} className="cyber-card p-3 flex items-center gap-3">
                    <span className="text-[11px] text-cyber-text font-mono flex-1">{kb.name}</span>
                    <div className="flex gap-2">
                      <a href={props.getExportURL("zip", kb.name)} download className="text-[10px] text-cyber-text-muted hover:text-tiffany">ZIP</a>
                      <a href={props.getExportURL("markdown", kb.name)} download className="text-[10px] text-cyber-text-muted hover:text-tiffany">Markdown</a>
                      <a href={props.getExportURL("report", kb.name)} download className="text-[10px] text-cyber-text-muted hover:text-tiffany">质量报告</a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
