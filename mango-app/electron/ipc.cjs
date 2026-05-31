const { ipcMain, shell, clipboard } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { fetchDiscordBridgeStatus } = require("./discord-bridge.cjs");
const { diagnosticsSnapshot } = require("./diagnostics.cjs");
const { wrapIpcSync, wrapIpcAsync } = require("./ipc-result.cjs");

function registerIpcHandlers(deps) {
  const {
    appRoot,
    workspaceRoot,
    recentLogs,
    getStatus,
    loadSettings,
    saveSettings,
    startMango,
    stopMango,
    runManualTextTurn,
    runDuoChat,
    runSmartCmd,
    buildDiagnostics,
  } = deps;

  ipcMain.handle("mango:get-discord-bridge-status", wrapIpcAsync(() => fetchDiscordBridgeStatus()));
  ipcMain.handle("mango:get-status", wrapIpcSync(() => getStatus()));
  ipcMain.handle("mango:get-recent-logs", wrapIpcSync(() => recentLogs));
  ipcMain.handle("mango:get-settings", wrapIpcSync(() => loadSettings()));
  ipcMain.handle("mango:save-settings", wrapIpcSync((_event, settings) => saveSettings(settings || {})));
  ipcMain.handle("mango:start", wrapIpcSync((_event, settings) => startMango(settings || {})));
  ipcMain.handle("mango:stop", wrapIpcSync(() => stopMango()));
  ipcMain.handle("mango:send-text", wrapIpcAsync((_event, text, history) => runManualTextTurn(text, history)));
  ipcMain.handle("mango:run-duo", wrapIpcAsync((_event, payload) => runDuoChat(payload || {})));
  ipcMain.handle(
    "mango:open-logs-folder",
    wrapIpcAsync(async () => {
      const logsPath = path.join(appRoot, "logs");
      if (!fs.existsSync(logsPath)) fs.mkdirSync(logsPath, { recursive: true });
      await shell.openPath(logsPath);
      return { path: logsPath };
    }),
  );
  ipcMain.handle(
    "mango:copy-diagnostics",
    wrapIpcSync(() => {
      const text = buildDiagnostics();
      clipboard.writeText(text);
      return { text };
    }),
  );
  ipcMain.handle("mango:smart-snapshot", () => {
    const r = runSmartCmd(["snapshot"]);
    if (!r.ok) return { ok: false, error: r.stderr || r.stdout };
    try {
      return { ok: true, data: JSON.parse(r.stdout) };
    } catch {
      return { ok: false, error: "Invalid smart snapshot JSON" };
    }
  });
  ipcMain.handle("mango:smart-brief", () => {
    const r = runSmartCmd(["brief"]);
    return { ok: r.ok, text: r.stdout, error: r.stderr };
  });
  ipcMain.handle("mango:smart-card-add", (_event, payload) => {
    const title = String(payload?.title || "Note");
    const content = String(payload?.content || "");
    const category = String(payload?.category || "fact");
    const r = runSmartCmd(["card-add", "--title", title, "--content", content, "--category", category]);
    if (!r.ok) return { ok: false, error: r.stderr || r.stdout };
    try {
      return { ok: true, card: JSON.parse(r.stdout) };
    } catch {
      return { ok: true };
    }
  });
  ipcMain.handle("mango:smart-card-delete", (_event, cardId) => {
    const r = runSmartCmd(["card-delete", "--id", String(cardId || "")]);
    return { ok: r.ok, error: r.stderr || r.stdout };
  });
  ipcMain.handle("mango:smart-inbox-add", (_event, text) => {
    const r = runSmartCmd(["inbox-add", "--text", String(text || "")]);
    if (!r.ok) return { ok: false, error: r.stderr || r.stdout };
    try {
      return { ok: true, item: JSON.parse(r.stdout) };
    } catch {
      return { ok: true };
    }
  });
  ipcMain.handle(
    "mango:save-usage-report",
    wrapIpcSync((_event, kind, content) => {
      const logsPath = path.join(appRoot, "logs");
      if (!fs.existsSync(logsPath)) fs.mkdirSync(logsPath, { recursive: true });
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const ext = kind === "csv" ? "csv" : "json";
      const fp = path.join(logsPath, `mango-usage-report-${ts}.${ext}`);
      fs.writeFileSync(fp, String(content || ""), "utf8");
      shell.showItemInFolder(fp);
      return { path: fp };
    }),
  );
}

module.exports = { registerIpcHandlers };
