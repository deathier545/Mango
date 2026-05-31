const fs = require("node:fs");
const path = require("node:path");

function redactSecrets(text) {
  return String(text)
    .replace(/gsk_[A-Za-z0-9_-]+/g, "gsk_[REDACTED]")
    .replace(/(GROQ_API_KEY=).+/g, "$1[REDACTED]")
    .replace(/(MANGO_DISCORD_BOT_TOKEN=).+/g, "$1[REDACTED]")
    .replace(/(ELEVENLABS_API_KEY=).+/g, "$1[REDACTED]");
}

function diagnosticsSnapshot({
  getStatus,
  loadSettings,
  recentLogs,
  workspaceRoot,
  appRoot,
  pythonExecPath,
}) {
  const status = {
    ...getStatus(),
    settings: loadSettings(),
  };
  const tail = recentLogs
    .slice(-40)
    .map((e) => redactSecrets(`[${new Date(e.ts).toISOString()}] ${e.kind}: ${e.line}`));
  const envPath = path.join(workspaceRoot, ".env");
  return JSON.stringify(
    {
      status,
      runtime: {
        platform: process.platform,
        node: process.version,
        electron: process.versions.electron || null,
        python: pythonExecPath(),
        workspaceRoot,
        appRoot,
        hasEnv: fs.existsSync(envPath),
        hasVenv: fs.existsSync(path.join(workspaceRoot, ".venv")),
        groqKeySet: Boolean(String(process.env.GROQ_API_KEY || "").trim()),
        discordTokenSet: Boolean(String(process.env.MANGO_DISCORD_BOT_TOKEN || "").trim()),
      },
      tail,
    },
    null,
    2,
  );
}

module.exports = {
  redactSecrets,
  diagnosticsSnapshot,
};
