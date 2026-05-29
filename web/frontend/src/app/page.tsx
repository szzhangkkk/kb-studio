"use client";

import { useState, useEffect, useCallback } from "react";
import { useKBStudio, ToolDefinition } from "@/hooks/useKBStudio";
import { useWebSocket } from "@/hooks/useWebSocket";
import ActivityBar from "@/components/ActivityBar";
import ExplorerSidebar from "@/components/ExplorerSidebar";
import StatusBar from "@/components/StatusBar";
import WelcomePanel from "@/components/panels/WelcomePanel";
import KBPanel from "@/components/panels/KBPanel";
import ChatPanel from "@/components/panels/ChatPanel";
import ConfigPanel from "@/components/panels/ConfigPanel";
import ToolsPanel from "@/components/panels/ToolsPanel";
import ButlerPanel from "@/components/panels/ButlerPanel";

export default function Home() {
  const [activePanel, setActivePanel] = useState("welcome");
  const [selectedKBForDocs, setSelectedKBForDocs] = useState<string | null>(null);
  const [toolList, setToolList] = useState<ToolDefinition[]>([]);
  const [selectedTool, setSelectedTool] = useState<string | null>(null);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const kb = useKBStudio();

  // Poll notification count
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await kb.loadNotifications(1, true);
        setUnreadNotifications(data.unread_count || 0);
      } catch { /* ignore */ }
    };
    poll();
    const interval = setInterval(poll, 30000);
    return () => clearInterval(interval);
  }, [kb.loadNotifications]);

  // WebSocket for real-time updates
  useWebSocket((msg) => {
    if (msg.type === "notification") {
      setUnreadNotifications(prev => prev + 1);
    }
  });

  useEffect(() => { kb.loadKBList(); /* eslint-disable-next-line */ }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "P") {
        e.preventDefault();
        const panels = ["welcome", "kb", "chat", "tools", "butler", "config"];
        const idx = panels.indexOf(activePanel);
        setActivePanel(panels[(idx + 1) % panels.length]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [activePanel]);

  const handlePanelChange = useCallback((panel: string) => {
    setActivePanel(panel);
    setSelectedKBForDocs(null);
    if (panel === "kb") kb.loadKBList();
    if (panel === "config") kb.loadProviders();
    if (panel === "tools") kb.loadTools().then(setToolList);
  }, [kb]);

  const handleSelectKBFromSidebar = useCallback((name: string) => {
    kb.selectKB(name);
    setActivePanel("chat");
    setSelectedKBForDocs(null);
  }, [kb]);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="flex flex-1 min-h-0">
        <ActivityBar activePanel={activePanel} onPanelChange={handlePanelChange} kbCount={kb.kbList.length} unreadNotifications={unreadNotifications} />

        <ExplorerSidebar
          activePanel={activePanel}
          kbList={kb.kbList}
          currentKB={kb.currentKB}
          onSelectKB={handleSelectKBFromSidebar}
          selectedKBForDocs={selectedKBForDocs}
          onLoadDocuments={kb.loadDocuments}
          toolList={activePanel === "tools" ? toolList : undefined}
          selectedTool={selectedTool}
          onSelectTool={(name) => setSelectedTool(name)}
        />

        <div className="flex-1 min-w-0 overflow-hidden" style={{ background: "linear-gradient(135deg, var(--color-cyber-main-bg-start), var(--color-cyber-main-bg-mid), var(--color-cyber-main-bg-end))" }}>
          {activePanel === "welcome" && <WelcomePanel onNavigate={handlePanelChange} />}
          {activePanel === "kb" && (
            <KBPanel
              kbList={kb.kbList}
              onCreateKB={kb.createKB}
              onDeleteKB={kb.deleteKB}
              onSelectKB={handleSelectKBFromSidebar}
              onLoadDocuments={kb.loadDocuments}
              onGetDocumentContent={kb.getDocumentContent}
              onGetDocumentChunks={kb.getDocumentChunks}
              onDeleteDocument={kb.deleteDocument}
              onRechunkDocument={kb.rechunkDocument}
              onLoadFindings={kb.loadFindings}
              onLoadFindingsSummary={kb.loadFindingsSummary}
              onResolveFinding={kb.resolveFinding}
              onDismissFinding={kb.dismissFinding}
              onAnalyzeKB={kb.analyzeKB}
            />
          )}
          {activePanel === "chat" && (
            <ChatPanel
              kbList={kb.kbList}
              currentKB={kb.currentKB}
              onSelectKB={kb.selectKB}
              onSendMessage={kb.sendMessage}
              onUploadFile={kb.uploadFile}
              onUploadURL={kb.uploadURL}
              onClearHistory={kb.clearHistory}
              onSearch={kb.searchKB}
              onLoadConversations={kb.loadConversations}
              onCreateConversation={kb.createConversation}
              onDeleteConversation={kb.deleteConversation}
              onGetConversationHistory={kb.getConversationHistory}
              onRenameConversation={kb.renameConversation}
              onExportConversation={kb.exportConversation}
              onSetActiveConversation={kb.setActiveConversation}
              onLoadMemory={kb.loadMemory}
              onAddMemory={kb.addMemory}
              onDeleteMemory={kb.deleteMemory}
              onLoadPipeline={kb.loadPipeline}
              onUpdatePipeline={kb.updatePipeline}
              onPipelineChat={kb.pipelineChat}
            />
          )}
          {activePanel === "config" && (
            <ConfigPanel
              providers={kb.providers}
              onTestConnection={kb.testConnection}
              onSaveConfig={kb.saveConfig}
              onLoadProviders={kb.loadProviders}
            />
          )}
          {activePanel === "tools" && (
            <ToolsPanel
              onLoadTools={kb.loadTools}
              onGetTool={kb.getTool}
              onCreateTool={kb.createTool}
              onUpdateTool={kb.updateTool}
              onDeleteTool={kb.deleteTool}
              onTestTool={kb.testTool}
              onToggleTool={kb.toggleTool}
              onGenerateTool={kb.generateTool}
              onRefineTool={kb.refineTool}
              onSaveGeneratedTool={kb.saveGeneratedTool}
              onLoadMCPStatus={kb.loadMCPStatus}
              onGetMCPConfig={kb.getMCPConfig}
            />
          )}
          {activePanel === "butler" && (
            <ButlerPanel
              kbList={kb.kbList}
              onLoadSchedulerStatus={kb.loadSchedulerStatus}
              onLoadScheduledTasks={kb.loadScheduledTasks}
              onCreateScheduledTask={kb.createScheduledTask}
              onDeleteScheduledTask={kb.deleteScheduledTask}
              onRunScheduledTask={kb.runScheduledTask}
              onPauseScheduledTask={kb.pauseScheduledTask}
              onResumeScheduledTask={kb.resumeScheduledTask}
              onLoadNotifications={kb.loadNotifications}
              onMarkNotificationRead={kb.markNotificationRead}
              onMarkAllNotificationsRead={kb.markAllNotificationsRead}
              onDeleteNotification={kb.deleteNotification}
              onLoadSourceWatches={kb.loadSourceWatches}
              onAddSourceWatch={kb.addSourceWatch}
              onDeleteSourceWatch={kb.deleteSourceWatch}
              onToggleSourceWatch={kb.toggleSourceWatch}
              onCheckSourceNow={kb.checkSourceNow}
              getExportURL={kb.getExportURL}
              onImportKB={kb.importKB}
              onLoadStaleness={kb.loadStaleness}
              onLoadGlobalMemorySummary={kb.loadGlobalMemorySummary}
              onSyncGlobalMemory={kb.syncGlobalMemory}
              onLoadSuggestions={kb.loadSuggestions}
              onGenerateSuggestions={kb.generateSuggestions}
              onDismissSuggestion={kb.dismissSuggestion}
            />
          )}
        </div>
      </div>

      <StatusBar statusKB={kb.statusKB} statusLLM={kb.statusLLM} statusEmb={kb.statusEmb} />
    </div>
  );
}
