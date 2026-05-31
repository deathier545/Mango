const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");

const DISCORD_CONTROL_HEADER = "X-Mango-Discord-Control";
const MAX_STATUS_BODY = 64_000;

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
          if (body.length > MAX_STATUS_BODY) {
            req.destroy();
            resolve({ reachable: false, ok: false, musicOn: false, ownerVoice: null });
          }
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

function discordBridgeAutoStartEnabled() {
  const raw = String(process.env.MANGO_DISCORD_AUTO_START_BRIDGE || "").trim().toLowerCase();
  if (raw === "0" || raw === "false" || raw === "no" || raw === "off") return false;
  if (raw === "1" || raw === "true" || raw === "yes" || raw === "on") return true;
  return true;
}

function createDiscordBridgeManager({ workspaceRoot, pythonExecPath, pushLog, isProcessAlive, terminateProcessTree }) {
  let discordBridgeProc = null;

  function startIfNeeded() {
    if (discordBridgeProc && isProcessAlive(discordBridgeProc)) return;
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

    discordBridgeProc = spawn(py, ["-m", "mango", "--discord-voice"], {
      cwd: workspaceRoot,
      env: process.env,
      windowsHide: true,
      stdio: ["ignore", outFd, errFd],
    });
    discordBridgeProc.on("exit", () => {
      discordBridgeProc = null;
    });
    discordBridgeProc.on("error", (err) => {
      pushLog("error", `Discord bridge process error: ${err.message}`);
      discordBridgeProc = null;
    });
    pushLog("system", `Starting Discord voice bridge with ${py}`);
  }

  function stop() {
    if (!discordBridgeProc) return;
    const proc = discordBridgeProc;
    discordBridgeProc = null;
    terminateProcessTree(proc);
  }

  function getProc() {
    return discordBridgeProc;
  }

  return { startIfNeeded, stop, getProc };
}

module.exports = {
  fetchDiscordBridgeStatus,
  createDiscordBridgeManager,
};
