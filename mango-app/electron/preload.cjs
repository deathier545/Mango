const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("mango", {
  getStatus: () => ipcRenderer.invoke("mango:get-status"),
  getDiscordBridgeStatus: () => ipcRenderer.invoke("mango:get-discord-bridge-status"),
  getRecentLogs: () => ipcRenderer.invoke("mango:get-recent-logs"),
  getSettings: () => ipcRenderer.invoke("mango:get-settings"),
  saveSettings: (settings) => ipcRenderer.invoke("mango:save-settings", settings),
  start: (settings) => ipcRenderer.invoke("mango:start", settings || {}),
  stop: () => ipcRenderer.invoke("mango:stop"),
  sendText: (text, history) => ipcRenderer.invoke("mango:send-text", text, history || []),
  runDuo: (payload) => ipcRenderer.invoke("mango:run-duo", payload || {}),
  stopDuo: () => ipcRenderer.invoke("mango:stop-duo"),
  openLogsFolder: () => ipcRenderer.invoke("mango:open-logs-folder"),
  copyDiagnostics: () => ipcRenderer.invoke("mango:copy-diagnostics"),
  saveUsageReport: (kind, content) =>
    ipcRenderer.invoke("mango:save-usage-report", kind, content),
  smartSnapshot: () => ipcRenderer.invoke("mango:smart-snapshot"),
  smartBrief: () => ipcRenderer.invoke("mango:smart-brief"),
  smartCardAdd: (payload) => ipcRenderer.invoke("mango:smart-card-add", payload),
  smartCardDelete: (cardId) => ipcRenderer.invoke("mango:smart-card-delete", cardId),
  smartInboxAdd: (text) => ipcRenderer.invoke("mango:smart-inbox-add", text),
  bridgeVersion: 2,
  onEvent: (cb) => {
    if (typeof cb !== "function") return () => {};
    const handler = (_event, payload) => cb(payload);
    ipcRenderer.on("mango:event", handler);
    return () => ipcRenderer.removeListener("mango:event", handler);
  },
});
