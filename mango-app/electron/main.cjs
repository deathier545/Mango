const { app, BrowserWindow, Tray, Menu, nativeImage } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { parseLogLine, createLogStream } = require("./log-parser.cjs");
const { createSettingsStore } = require("./settings.cjs");
const { createDiscordBridgeManager } = require("./discord-bridge.cjs");
const {
  isProcessAlive,
  pythonExecPath,
  terminateMangoProcessTree,
  createProcessManager,
} = require("./process-manager.cjs");
const { redactSecrets, diagnosticsSnapshot } = require("./diagnostics.cjs");
const { registerIpcHandlers } = require("./ipc.cjs");

const appRoot = path.resolve(__dirname, "..");
const workspaceRoot = path.resolve(appRoot, "..");
const mangoDevPort = String(process.env.MANGO_DEV_PORT || "5180").trim() || "5180";
const mangoDevUrl =
  process.env.VITE_DEV_SERVER_URL || `http://localhost:${mangoDevPort}`;
const settingsFile = path.join(appRoot, ".mango-app-settings.json");
const alwaysOnTop = process.env.MANGO_ALWAYS_ON_TOP === "1";

let win = null;
let tray = null;
const recentLogs = [];

const { loadSettings, saveSettings } = createSettingsStore(settingsFile);

function loadWorkspaceEnvFile() {
  const candidates = [
    path.join(workspaceRoot, ".env"),
    path.join(workspaceRoot, ".env.local"),
  ];
  for (const envPath of candidates) {
    if (!fs.existsSync(envPath)) continue;
    try {
      const text = fs.readFileSync(envPath, "utf8");
      for (const rawLine of text.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith("#")) continue;
        const eq = line.indexOf("=");
        if (eq <= 0) continue;
        const key = line.slice(0, eq).trim();
        let val = line.slice(eq + 1).trim();
        if (
          (val.startsWith('"') && val.endsWith('"')) ||
          (val.startsWith("'") && val.endsWith("'"))
        ) {
          val = val.slice(1, -1);
        }
        if (!(key in process.env) || !String(process.env[key] || "").trim()) {
          process.env[key] = val;
        }
      }
    } catch {
      // ignore unreadable env files
    }
  }
}

function emitStatus() {
  if (win && !win.isDestroyed()) {
    win.webContents.send("mango:event", {
      type: "status",
      payload: processManager.getStatus(),
    });
  }
}

function pushLog(kind, line) {
  const safeLine = redactSecrets(line);
  const entry = { ts: Date.now(), kind, line: safeLine };
  recentLogs.push(entry);
  if (recentLogs.length > 500) {
    recentLogs.shift();
  }
  if (win && !win.isDestroyed()) {
    win.webContents.send("mango:event", { type: "log", payload: entry });
  }
  const parsed = parseLogLine(safeLine);
  if (parsed && win && !win.isDestroyed()) {
    win.webContents.send("mango:event", { type: "parsed", payload: parsed });
  }
}

const { streamToLines, reset: resetStreamBuffers } = createLogStream((kind, line) => {
  pushLog(kind, line);
});

const discordBridge = createDiscordBridgeManager({
  workspaceRoot,
  pythonExecPath: () => pythonExecPath(workspaceRoot, appRoot),
  pushLog,
  isProcessAlive,
  terminateProcessTree: terminateMangoProcessTree,
});

const processManager = createProcessManager({
  workspaceRoot,
  appRoot,
  pushLog,
  emitStatus,
  loadSettings,
  saveSettings,
  startDiscordBridge: () => discordBridge.startIfNeeded(),
  streamToLines,
  resetStreamBuffers,
});

function buildDiagnostics() {
  return diagnosticsSnapshot({
    getStatus: () => processManager.getStatus(),
    loadSettings,
    recentLogs,
    workspaceRoot,
    appRoot,
    pythonExecPath: () => pythonExecPath(workspaceRoot, appRoot),
  });
}

function createTray() {
  if (tray) return;
  const icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip("Mango Console");
  const menu = Menu.buildFromTemplate([
    {
      label: "Show Mango Console",
      click: () => {
        if (win && !win.isDestroyed()) {
          win.show();
          win.focus();
        }
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);
  tray.on("double-click", () => {
    if (win && !win.isDestroyed()) {
      win.show();
      win.focus();
    }
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1200,
    height: 780,
    minWidth: 980,
    minHeight: 640,
    title: "Mango Console",
    alwaysOnTop,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (!app.isPackaged) {
    win.loadURL(mangoDevUrl);
  } else {
    win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
  win.on("close", (e) => {
    if (process.platform === "darwin") return;
    if (app.isQuitting) return;
    e.preventDefault();
    win.hide();
  });
}

loadWorkspaceEnvFile();

app.whenReady().then(() => {
  registerIpcHandlers({
    appRoot,
    workspaceRoot,
    recentLogs,
    getStatus: () => processManager.getStatus(),
    loadSettings,
    saveSettings,
    startMango: (settings) => processManager.startMango(settings),
    stopMango: () => processManager.stopMango(),
    runManualTextTurn: (text, history) => processManager.runManualTextTurn(text, history),
    runDuoChat: (payload) => processManager.runDuoChat(payload),
    runSmartCmd: (args) => processManager.runSmartCmd(args),
    buildDiagnostics,
  });
  createWindow();
  createTray();
});

app.on("before-quit", () => {
  app.isQuitting = true;
  processManager.stopMango();
  discordBridge.stop();
});

app.on("window-all-closed", () => {
  processManager.stopMango();
  discordBridge.stop();
  if (process.platform !== "darwin") app.quit();
});
