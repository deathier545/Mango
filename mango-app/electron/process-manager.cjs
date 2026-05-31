const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { defaultSettings, INTERRUPT_PROFILES } = require("./settings.cjs");

function isProcessAlive(proc) {
  if (!proc || !proc.pid) return false;
  try {
    process.kill(proc.pid, 0);
    return true;
  } catch {
    return false;
  }
}

function pythonExecPath(workspaceRoot, appRoot) {
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

function createProcessManager({
  workspaceRoot,
  appRoot,
  pushLog,
  emitStatus,
  loadSettings,
  saveSettings,
  startDiscordBridge,
  streamToLines,
  resetStreamBuffers,
}) {
  let mangoProc = null;
  let startedAt = null;

  function mangoChildEnv(cfg) {
    const interruptProfile = String(cfg.interruptProfile || defaultSettings.interruptProfile).toLowerCase();
    const safeMode =
      Boolean(cfg.safeMode) ||
      String(process.env.MANGO_SAFE_MODE || "")
        .trim()
        .toLowerCase() === "1";
    return {
      ...process.env,
      MANGO_DESKTOP: "1",
      MANGO_SAFE_MODE: safeMode ? "1" : "0",
      MANGO_PTT_ONLY: safeMode ? "1" : process.env.MANGO_PTT_ONLY || "0",
      MANGO_TTS_PROVIDER: "edge",
      MANGO_ELEVENLABS_QUOTA_EXCEEDED: "1",
      MANGO_TOOL_NARRATION_AFTER: "0",
      MANGO_DISCORD_AUTO_START_BRIDGE: safeMode ? "0" : "1",
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

  function getStatus() {
    const running = isProcessAlive(mangoProc);
    if (!running && mangoProc) {
      mangoProc = null;
      startedAt = null;
    }
    return {
      running,
      pid: running && mangoProc ? mangoProc.pid : null,
      startedAt: running ? startedAt : null,
    };
  }

  function startMango(overrideSettings = {}) {
    if (mangoProc && isProcessAlive(mangoProc)) {
      return { running: true, pid: mangoProc.pid, startedAt };
    }
    mangoProc = null;
    startedAt = null;

    const py = pythonExecPath(workspaceRoot, appRoot);
    const cfg = saveSettings({ ...loadSettings(), ...overrideSettings });
    const childEnv = mangoChildEnv(cfg);
    startDiscordBridge();
    mangoProc = spawn(py, ["-m", "mango"], {
      cwd: workspaceRoot,
      env: childEnv,
      windowsHide: true,
    });
    startedAt = Date.now();
    resetStreamBuffers();
    pushLog("system", `Starting Mango with ${py}`);
    mangoProc.stdout.on("data", (d) => streamToLines(d, "stdout"));
    mangoProc.stderr.on("data", (d) => streamToLines(d, "stderr"));
    mangoProc.on("error", (err) => {
      pushLog("error", `Mango process error: ${err.message}`);
    });
    mangoProc.on("exit", (code, signal) => {
      const sessionStartedAt = startedAt;
      if (sessionStartedAt && Date.now() - sessionStartedAt < 5000 && code !== 0 && code !== null) {
        pushLog(
          "error",
          `Mango failed during startup. Exit code ${code}. Check .env, microphone, model, and dependencies.`,
        );
      }
      pushLog("system", `Mango exited (code=${code} signal=${signal || "none"})`);
      mangoProc = null;
      startedAt = null;
      emitStatus();
    });
    emitStatus();
    return { running: true, pid: mangoProc.pid, startedAt };
  }

  function stopMango() {
    if (!mangoProc || !isProcessAlive(mangoProc)) {
      mangoProc = null;
      startedAt = null;
      emitStatus();
      return { running: false, pid: null, startedAt: null };
    }
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
      const py = pythonExecPath(workspaceRoot, appRoot);
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
        if (timeout) clearTimeout(timeout);
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

  function runDuoChat(payload = {}) {
    return new Promise((resolve) => {
      const topic = String(payload.topic || "").trim();
      if (!topic) {
        resolve({ ok: false, error: "Empty topic." });
        return;
      }
      const rounds = Math.max(1, Math.min(6, Number(payload.rounds) || 2));
      const speak = payload.speak !== false;
      const py = pythonExecPath(workspaceRoot, appRoot);
      const cfg = loadSettings();
      const proc = spawn(py, ["-m", "mango.duo_chat_cli"], {
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
      const DUO_INACTIVITY_MS = 600000;
      const armTimeout = () => {
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => {
          try {
            if (!proc.killed) proc.kill();
          } catch {
            // ignore
          }
          done({ ok: false, error: "Duo conversation timed out." });
        }, DUO_INACTIVITY_MS);
      };
      const done = (result) => {
        if (finished) return;
        finished = true;
        if (timeout) {
          clearTimeout(timeout);
          timeout = null;
        }
        resolve(result);
      };
      const parseResultLine = () => {
        const lines = out.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
        for (let i = lines.length - 1; i >= 0; i -= 1) {
          if (!lines[i].startsWith("MANGO_DUO_RESULT:")) continue;
          const raw = lines[i].slice("MANGO_DUO_RESULT:".length).trim();
          try {
            const parsed = JSON.parse(raw);
            return {
              ok: !!parsed.ok,
              lines: Array.isArray(parsed.lines) ? parsed.lines : [],
              topic: typeof parsed.topic === "string" ? parsed.topic : topic,
              rounds: typeof parsed.rounds === "number" ? parsed.rounds : rounds,
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
            if (!trimmed || trimmed.startsWith("MANGO_DUO_RESULT:")) continue;
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
        done({ ok: false, error: `Duo process failed: ${e.message}` });
      });
      proc.on("exit", () => {
        const parsed = parseResultLine();
        if (parsed) {
          done(parsed);
          return;
        }
        const tail = err.trim() || out.trim() || "No response from duo bridge.";
        done({ ok: false, error: tail.slice(0, 500) });
      });
      armTimeout();

      try {
        proc.stdin.write(JSON.stringify({ topic, rounds, speak }));
        proc.stdin.end();
      } catch {
        done({ ok: false, error: "Could not submit duo request." });
      }
    });
  }

  function runSmartCmd(args) {
    const py = pythonExecPath(workspaceRoot, appRoot);
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

  return {
    getStatus,
    startMango,
    stopMango,
    runManualTextTurn,
    runDuoChat,
    runSmartCmd,
    mangoChildEnv,
    getMangoProc: () => mangoProc,
  };
}

module.exports = {
  isProcessAlive,
  pythonExecPath,
  terminateMangoProcessTree,
  createProcessManager,
};
