const { app, BrowserWindow, ipcMain, shell, clipboard, Tray, Menu, nativeImage } = require("electron");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const appRoot = path.resolve(__dirname, "..");
const workspaceRoot = path.resolve(appRoot, "..");
const mangoDevPort = String(process.env.MANGO_DEV_PORT || "5180").trim() || "5180";
const mangoDevUrl =
  process.env.VITE_DEV_SERVER_URL || `http://localhost:${mangoDevPort}`;

let win = null;
let tray = null;
let mangoProc = null;
let discordBridgeStarted = false;
const alwaysOnTop = process.env.MANGO_ALWAYS_ON_TOP === "1";
let stdoutBuffer = "";
let stderrBuffer = "";
let startedAt = null;
const recentLogs = [];
const defaultSettings = {
  wakeEnabled: true,
  strictTools: false,
  powershellConfirmation: true,
  groqModel: "llama-3.3-70b-versatile",
  edgeVoice: "en-US-GuyNeural",
  edgeRate: "+0%",
  edgePitch: "+0Hz",
  edgeVolume: "+0%",
  interruptProfile: "normal",
  promptTokenRatePer1k: 0,
  completionTokenRatePer1k: 0,
};
const settingsFile = path.join(appRoot, ".mango-app-settings.json");
const DISCORD_CONTROL_HEADER = "X-Mango-Discord-Control";
const INTERRUPT_PROFILES = new Set(["strict", "normal", "fast"]);

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

function fetchDiscordBridgeStatus() {
  const portRaw = String(process.env.MANGO_DISCORD_VOICE_CONTROL_PORT || "37564").trim() || "37564";
  const port = Number(portRaw) || 37564;
  const secret = String(process.env.MANGO_DISCORD_CONTROL_SECRET || "").trim();

  return new Promise((resolve) => {
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port,
        path: "/v1/voice/status",
        method: "GET",
        headers: secret ? { [DISCORD_CONTROL_HEADER]: secret } : {},
        timeout: 4000,
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode !== 200) {
            resolve({ reachable: false, ok: false, musicOn: false, ownerVoice: null });
            return;
          }
          try {
            const data = JSON.parse(body || "{}");
            const lines = Array.isArray(data.lines) ? data.lines.join(" ") : "";
            resolve({
              reachable: true,
              ok: Boolean(data.ok),
              ownerVoice: data.owner_voice ?? null,
              musicOn: /music stream:\s*on/i.test(lines),
            });
          } catch {
            resolve({ reachable: false, ok: false, musicOn: false, ownerVoice: null });
          }
        });
      },
    );
    req.on("timeout", () => {
      req.destroy();
      resolve({ reachable: false, ok: false, musicOn: false, ownerVoice: null });
    });
    req.on("error", () => {
      resolve({ reachable: false, ok: false, musicOn: false, ownerVoice: null });
    });
    req.end();
  });
}

function pushLog(kind, line) {
  const entry = { ts: Date.now(), kind, line };
  recentLogs.push(entry);
  if (recentLogs.length > 500) {
    recentLogs.shift();
  }
  if (win && !win.isDestroyed()) {
    win.webContents.send("mango:event", { type: "log", payload: entry });
  }
  const parsed = parseLogLine(line);
  if (parsed && win && !win.isDestroyed()) {
    win.webContents.send("mango:event", { type: "parsed", payload: parsed });
  }
}

function parseLogLine(line) {
  if (!line) return null;
  const globeVisibleMatch = line.match(/MANGO_GLOBE_VISIBLE:\s*([01])/i);
  if (globeVisibleMatch) {
    return {
      kind: "globe_state",
      visible: globeVisibleMatch[1] === "1",
    };
  }
  const globeMatch = line.match(/MANGO_GLOBE:\s*(\{.*\})/);
  if (globeMatch) {
    try {
      const payload = JSON.parse(globeMatch[1]);
      const lat = Number(payload.lat);
      const lng = Number(payload.lng);
      const zoom = Number(payload.zoom);
      return {
        kind: "globe",
        url: String(payload.url || ""),
        label: String(payload.label || "Map"),
        lat: Number.isFinite(lat) ? lat : null,
        lng: Number.isFinite(lng) ? lng : null,
        zoom: Number.isFinite(zoom) ? zoom : null,
      };
    } catch {
      // ignore malformed marker and continue with other parsers
    }
  }
  const stateMatch = line.match(/MANGO_STATE:\s*(idle|listening|thinking|speaking|awaiting|stopped|error)/i);
  if (stateMatch) {
    return {
      kind: "state",
      state: stateMatch[1].toLowerCase(),
      text: line,
    };
  }
  const audioLevelMatch = line.match(/MANGO_AUDIO_LEVEL:\s*([0-9]*\.?[0-9]+)/);
  if (audioLevelMatch) {
    return {
      kind: "audio_level",
      level: Math.max(0, Math.min(1, Number(audioLevelMatch[1]))),
    };
  }
  const usage = parseUsageLine(line);
  if (usage) return usage;
  const metric = parseMetricLine(line);
  if (metric) return metric;
  if (line.includes("Startup intro:")) {
    return { kind: "state", state: "speaking", text: line };
  }
  if (
    line.includes("Mango ready.") ||
    line.includes("Ctrl+C to exit.") ||
    line.includes("Wake hands-free:") ||
    line.includes("Always-listen") ||
    line.includes("Listening — hold")
  ) {
    return { kind: "state", state: "listening", text: line };
  }
  if (line.includes("Wake phrase heard")) {
    return { kind: "state", state: "listening", text: line };
  }
  if (line.includes("Starting transcription")) {
    return { kind: "state", state: "thinking", text: line };
  }
  if (line.includes("Playing TTS")) {
    return { kind: "state", state: "speaking", text: line };
  }
  if (line.includes("TTS finished")) {
    return { kind: "state", state: "listening", text: line };
  }
  if (line.includes("Mango reply:")) {
    const idx = line.indexOf("Mango reply:");
    const reply = line.slice(idx + "Mango reply:".length).trim();
    return { kind: "reply", text: reply };
  }
  if (line.includes("You said")) {
    const idx = line.indexOf("You said");
    const transcript = line.slice(idx).replace(/^You said \([^)]+\):\s*/, "").trim();
    return { kind: "transcript", text: transcript };
  }
  if (line.includes("PowerShell approval armed")) {
    return { kind: "state", state: "awaiting", text: "PowerShell confirmed." };
  }
  if (line.includes("HOST_PENDING_POWERSHELL") || line.includes("Need approval for PowerShell")) {
    return { kind: "state", state: "awaiting", text: "Awaiting confirmation." };
  }
  return null;
}

function parseUsageLine(line) {
  if (!line.includes("LLM usage:")) return null;
  const promptMatch = line.match(/'prompt_tokens':\s*([0-9]+)/);
  const completionMatch = line.match(/'completion_tokens':\s*([0-9]+)/);
  const totalMatch = line.match(/'total_tokens':\s*([0-9]+)/);
  const totalTimeMatch = line.match(/'total_time':\s*([0-9.]+)/);
  const queueTimeMatch = line.match(/'queue_time':\s*([0-9.]+)/);
  if (!promptMatch || !completionMatch || !totalMatch) return null;
  return {
    kind: "metric_usage",
    promptTokens: Number(promptMatch[1]),
    completionTokens: Number(completionMatch[1]),
    totalTokens: Number(totalMatch[1]),
    totalTime: totalTimeMatch ? Number(totalTimeMatch[1]) : null,
    queueTime: queueTimeMatch ? Number(queueTimeMatch[1]) : null,
  };
}

function parseMetricLine(line) {
  if (!line.includes("metric {")) return null;
  const eventMatch = line.match(/'event':\s*'([^']+)'/);
  if (!eventMatch) return null;
  const event = eventMatch[1];
  const sourceMatch = line.match(/'source':\s*'([^']+)'/);
  const cidMatch = line.match(/'correlation_id':\s*'([^']+)'/);
  const toolMatch = line.match(/'tool':\s*'([^']+)'/);
  const riskMatch = line.match(/'risk':\s*'([^']+)'/);
  const okMatch = line.match(/'ok':\s*(True|False|true|false)/);
  const sttMatch = line.match(/'stt_s':\s*([0-9.]+)/);
  const llmMatch = line.match(/'llm_s':\s*([0-9.]+)/);
  const ttsMatch = line.match(/'tts_s':\s*([0-9.]+)/);

  if (event.startsWith("turn_")) {
    return {
      kind: "metric_turn",
      event,
      correlationId: cidMatch ? cidMatch[1] : null,
      source: sourceMatch ? sourceMatch[1] : "",
      sttS: sttMatch ? Number(sttMatch[1]) : null,
      llmS: llmMatch ? Number(llmMatch[1]) : null,
      ttsS: ttsMatch ? Number(ttsMatch[1]) : null,
    };
  }
  if (event === "tool_start" || event === "tool_done") {
    const durMatch = line.match(/'duration_ms':\s*([0-9]+)/);
    return {
      kind: "metric_tool",
      event,
      correlationId: cidMatch ? cidMatch[1] : null,
      tool: toolMatch ? toolMatch[1] : "unknown",
      risk: riskMatch ? riskMatch[1] : "unknown",
      ok: okMatch ? /^true$/i.test(okMatch[1]) : null,
      durationMs: durMatch ? Number(durMatch[1]) : null,
    };
  }
  if (event === "noise_guidance") {
    const noiseFloorMatch = line.match(/'noise_floor':\s*([0-9.]+)/);
    const recommendationMatch = line.match(/'recommendation':\s*'([^']+)'/);
    const sourceMatch2 = line.match(/'source':\s*'([^']+)'/);
    return {
      kind: "noise_guidance",
      source: sourceMatch2 ? sourceMatch2[1] : "vad",
      noiseFloor: noiseFloorMatch ? Number(noiseFloorMatch[1]) : null,
      recommendation: recommendationMatch ? recommendationMatch[1] : "ptt_or_strict_interrupt",
    };
  }
  return null;
}

function streamToLines(chunk, kind) {
  const txt = chunk.toString("utf8");
  const isOut = kind === "stdout";
  const next = (isOut ? stdoutBuffer : stderrBuffer) + txt;
  const lines = next.split(/\r?\n/);
  const leftover = lines.pop() || "";
  if (isOut) stdoutBuffer = leftover;
  else stderrBuffer = leftover;
  for (const line of lines) {
    if (line.trim()) pushLog(kind, line);
  }
}

function pythonExecPath() {
  const candidates = [
    path.join(workspaceRoot, ".venv", "Scripts", "python.exe"),
    path.join(workspaceRoot, ".venv", "Scripts", "python"),
    path.join(appRoot, ".venv", "Scripts", "python.exe"),
    path.join(appRoot, ".venv", "Scripts", "python"),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return "python";
}

function loadSettings() {
  try {
    if (!fs.existsSync(settingsFile)) return { ...defaultSettings };
    const raw = fs.readFileSync(settingsFile, "utf8");
    const parsed = JSON.parse(raw);
    return { ...defaultSettings, ...parsed };
  } catch {
    return { ...defaultSettings };
  }
}

function saveSettings(next) {
  const merged = { ...defaultSettings, ...next };
  fs.writeFileSync(settingsFile, JSON.stringify(merged, null, 2), "utf8");
  return merged;
}

function emitStatus() {
  if (win && !win.isDestroyed()) {
    win.webContents.send("mango:event", {
      type: "status",
      payload: {
        running: !!mangoProc,
        pid: mangoProc ? mangoProc.pid : null,
        startedAt,
      },
    });
  }
}

function discordBridgeAutoStartEnabled() {
  const raw = String(process.env.MANGO_DISCORD_AUTO_START_BRIDGE || "").trim().toLowerCase();
  if (raw === "0" || raw === "false" || raw === "no" || raw === "off") return false;
  if (raw === "1" || raw === "true" || raw === "yes" || raw === "on") return true;
  return true;
}

function startDiscordBridgeIfNeeded() {
  if (discordBridgeStarted) return;
  if (!discordBridgeAutoStartEnabled()) return;
  if (!String(process.env.MANGO_DISCORD_BOT_TOKEN || "").trim()) return;

  const py = pythonExecPath();
  const logDir = path.join(workspaceRoot, "logs");
  fs.mkdirSync(logDir, { recursive: true });
  const outPath = path.join(logDir, "discord-voice.log");
  const errPath = path.join(logDir, "discord-voice.err.log");
  let outFd;
  let errFd;
  try {
    outFd = fs.openSync(outPath, "a");
    errFd = fs.openSync(errPath, "a");
  } catch (err) {
    pushLog("error", `Discord bridge log open failed: ${err.message}`);
    return;
  }

  const child = spawn(py, ["-m", "mango", "--discord-voice"], {
    cwd: workspaceRoot,
    env: process.env,
    detached: true,
    stdio: ["ignore", outFd, errFd],
    windowsHide: true,
  });
  child.unref();
  discordBridgeStarted = true;
  pushLog("system", `Starting Discord voice bridge with ${py}`);
}

function mangoChildEnv(cfg) {
  const interruptProfile = String(cfg.interruptProfile || defaultSettings.interruptProfile).toLowerCase();
    return {
    ...process.env,
    MANGO_DESKTOP: "1",
    MANGO_TTS_PROVIDER: "edge",
    MANGO_ELEVENLABS_QUOTA_EXCEEDED: "1",
    MANGO_TOOL_NARRATION_AFTER: "0",
    MANGO_DISCORD_AUTO_START_BRIDGE: "1",
    MANGO_DISABLE_LEGACY_HUD: "1",
    MANGO_WAKEWORD: cfg.wakeEnabled ? "1" : "0",
    MANGO_STRICT_TOOLS: cfg.strictTools ? "1" : "0",
    MANGO_REQUIRE_POWERSHELL_CONFIRMATION: cfg.powershellConfirmation ? "1" : "0",
    MANGO_EDGE_VOICE: String(cfg.edgeVoice || defaultSettings.edgeVoice),
    MANGO_EDGE_RATE: String(cfg.edgeRate || defaultSettings.edgeRate),
    MANGO_EDGE_PITCH: String(cfg.edgePitch || defaultSettings.edgePitch),
    MANGO_EDGE_VOLUME: String(cfg.edgeVolume || defaultSettings.edgeVolume),
    MANGO_INTERRUPT_PROFILE: INTERRUPT_PROFILES.has(interruptProfile) ? interruptProfile : "normal",
    MANGO_HUD: "0",
    MANGO_JARVIS_HUD: "0",
    GROQ_MODEL: cfg.groqModel || defaultSettings.groqModel,
  };
}

function startMango(overrideSettings = {}) {
  if (mangoProc) {
    return { running: true, pid: mangoProc.pid, startedAt };
  }
  const py = pythonExecPath();
  const cfg = saveSettings({ ...loadSettings(), ...overrideSettings });
  const childEnv = mangoChildEnv(cfg);
  startDiscordBridgeIfNeeded();
  mangoProc = spawn(py, ["-m", "mango"], {
    cwd: workspaceRoot,
    env: childEnv,
    windowsHide: true,
  });
  startedAt = Date.now();
  stdoutBuffer = "";
  stderrBuffer = "";
  pushLog("system", `Starting Mango with ${py}`);
  mangoProc.stdout.on("data", (d) => streamToLines(d, "stdout"));
  mangoProc.stderr.on("data", (d) => streamToLines(d, "stderr"));
  mangoProc.on("error", (err) => {
    pushLog("error", `Mango process error: ${err.message}`);
  });
  mangoProc.on("exit", (code, signal) => {
    pushLog("system", `Mango exited (code=${code} signal=${signal || "none"})`);
    mangoProc = null;
    startedAt = null;
    emitStatus();
  });
  emitStatus();
  return { running: true, pid: mangoProc.pid, startedAt };
}

function terminateMangoProcessTree(proc) {
  if (!proc || !proc.pid) return;
  if (process.platform === "win32") {
    try {
      spawnSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], {
        windowsHide: true,
        stdio: "ignore",
      });
      return;
    } catch {
      // Fall back to normal kill below.
    }
  }
  try {
    proc.kill();
  } catch {
    // ignore
  }
}

function stopMango() {
  if (!mangoProc) return { running: false, pid: null, startedAt: null };
  const proc = mangoProc;
  mangoProc = null;
  startedAt = null;
  terminateMangoProcessTree(proc);
  emitStatus();
  return { running: false, pid: null, startedAt: null };
}

function runManualTextTurn(text, history = []) {
  return new Promise((resolve) => {
    const userText = String(text || "").trim();
    if (!userText) {
      resolve({ ok: false, error: "Empty message." });
      return;
    }
    const py = pythonExecPath();
    const cfg = loadSettings();
    const proc = spawn(py, ["-m", "mango.text_chat_cli"], {
      cwd: workspaceRoot,
      env: mangoChildEnv(cfg),
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let out = "";
    let err = "";
    let outLeft = "";
    let errLeft = "";
    let finished = false;
    let timeout = null;
    const MANUAL_TEXT_INACTIVITY_MS = 240000;
    const armTimeout = () => {
      if (timeout) {
        clearTimeout(timeout);
      }
      timeout = setTimeout(() => {
        try {
          if (!proc.killed) proc.kill();
        } catch {
          // ignore
        }
        done({
          ok: false,
          error: "Manual message timed out during long response playback. Please try again.",
        });
      }, MANUAL_TEXT_INACTIVITY_MS);
    };
    const done = (payload) => {
      if (finished) return;
      finished = true;
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      resolve(payload);
    };
    const parseResultLine = () => {
      const lines = out.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      for (let i = lines.length - 1; i >= 0; i -= 1) {
        if (!lines[i].startsWith("MANGO_TEXT_RESULT:")) continue;
        const raw = lines[i].slice("MANGO_TEXT_RESULT:".length).trim();
        try {
          const parsed = JSON.parse(raw);
          return {
            ok: !!parsed.ok,
            reply: typeof parsed.reply === "string" ? parsed.reply : "",
            error: typeof parsed.error === "string" ? parsed.error : "",
          };
        } catch {
          return null;
        }
      }
      return null;
    };
    const streamChildChunk = (chunk, kind) => {
      armTimeout();
      const txt = chunk.toString("utf8");
      if (kind === "stdout") {
        out += txt;
        const merged = outLeft + txt;
        const lines = merged.split(/\r?\n/);
        outLeft = lines.pop() || "";
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith("MANGO_TEXT_RESULT:")) continue;
          pushLog("stdout", trimmed);
        }
        return;
      }
      err += txt;
      const merged = errLeft + txt;
      const lines = merged.split(/\r?\n/);
      errLeft = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        pushLog("stderr", trimmed);
      }
    };

    proc.stdout.on("data", (d) => streamChildChunk(d, "stdout"));
    proc.stderr.on("data", (d) => streamChildChunk(d, "stderr"));
    proc.on("error", (e) => {
      done({ ok: false, error: `Manual text process failed: ${e.message}` });
    });
    proc.on("exit", () => {
      const parsed = parseResultLine();
      if (parsed) {
        done(parsed);
        return;
      }
      const tail = err.trim() || out.trim() || "No response from text bridge.";
      done({ ok: false, error: tail.slice(0, 500) });
    });
    armTimeout();

    try {
      proc.stdin.write(JSON.stringify({ text: userText, history, speak: true }));
      proc.stdin.end();
    } catch {
      done({ ok: false, error: "Could not submit manual message to Mango." });
    }
  });
}

function runSmartCmd(args) {
  const py = pythonExecPath();
  try {
    const result = spawnSync(py, ["-m", "mango", "--smart", ...args], {
      cwd: workspaceRoot,
      env: process.env,
      encoding: "utf8",
      windowsHide: true,
      timeout: 120000,
    });
    return {
      ok: result.status === 0,
      stdout: (result.stdout || "").trim(),
      stderr: (result.stderr || "").trim(),
    };
  } catch (err) {
    return { ok: false, stdout: "", stderr: String(err) };
  }
}

function diagnosticsSnapshot() {
  const status = {
    running: !!mangoProc,
    pid: mangoProc ? mangoProc.pid : null,
    startedAt,
    settings: loadSettings(),
  };
  const tail = recentLogs.slice(-40).map((e) => `[${new Date(e.ts).toISOString()}] ${e.kind}: ${e.line}`);
  return JSON.stringify({ status, tail }, null, 2);
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
  ipcMain.handle("mango:get-discord-bridge-status", () => fetchDiscordBridgeStatus());
  ipcMain.handle("mango:get-status", () => ({
    running: !!mangoProc,
    pid: mangoProc ? mangoProc.pid : null,
    startedAt,
  }));
  ipcMain.handle("mango:get-recent-logs", () => recentLogs);
  ipcMain.handle("mango:get-settings", () => loadSettings());
  ipcMain.handle("mango:save-settings", (_event, settings) => saveSettings(settings || {}));
  ipcMain.handle("mango:start", (_event, settings) => startMango(settings || {}));
  ipcMain.handle("mango:stop", () => stopMango());
  ipcMain.handle("mango:send-text", (_event, text, history) => runManualTextTurn(text, history));
  ipcMain.handle("mango:open-logs-folder", async () => {
    const logsPath = path.join(appRoot, "logs");
    if (!fs.existsSync(logsPath)) fs.mkdirSync(logsPath, { recursive: true });
    await shell.openPath(logsPath);
    return { ok: true, path: logsPath };
  });
  ipcMain.handle("mango:copy-diagnostics", () => {
    const text = diagnosticsSnapshot();
    clipboard.writeText(text);
    return { ok: true, text };
  });
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

  ipcMain.handle("mango:save-usage-report", (_event, kind, content) => {
    const logsPath = path.join(appRoot, "logs");
    if (!fs.existsSync(logsPath)) fs.mkdirSync(logsPath, { recursive: true });
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    const ext = kind === "csv" ? "csv" : "json";
    const fp = path.join(logsPath, `mango-usage-report-${ts}.${ext}`);
    fs.writeFileSync(fp, String(content || ""), "utf8");
    shell.showItemInFolder(fp);
    return { ok: true, path: fp };
  });
  createWindow();
  createTray();
});

app.on("before-quit", () => {
  app.isQuitting = true;
});

app.on("window-all-closed", () => {
  if (mangoProc) {
    terminateMangoProcessTree(mangoProc);
  }
  if (process.platform !== "darwin") app.quit();
});
