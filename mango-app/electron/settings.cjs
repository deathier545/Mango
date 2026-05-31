const fs = require("node:fs");

const INTERRUPT_PROFILES = new Set(["strict", "normal", "fast"]);

const defaultSettings = {
  wakeEnabled: true,
  strictTools: false,
  powershellConfirmation: true,
  safeMode: false,
  groqModel: "llama-3.3-70b-versatile",
  edgeVoice: "en-US-GuyNeural",
  edgeRate: "+0%",
  edgePitch: "+0Hz",
  edgeVolume: "+0%",
  interruptProfile: "normal",
  promptTokenRatePer1k: 0,
  completionTokenRatePer1k: 0,
};

function sanitizeSettings(raw = {}) {
  const profile = String(raw.interruptProfile || defaultSettings.interruptProfile).toLowerCase();
  return {
    wakeEnabled: Boolean(raw.wakeEnabled),
    strictTools: Boolean(raw.strictTools),
    powershellConfirmation: raw.powershellConfirmation !== false,
    safeMode: Boolean(raw.safeMode),
    groqModel: String(raw.groqModel || defaultSettings.groqModel).slice(0, 120),
    edgeVoice: String(raw.edgeVoice || defaultSettings.edgeVoice).slice(0, 120),
    edgeRate: String(raw.edgeRate || defaultSettings.edgeRate).slice(0, 20),
    edgePitch: String(raw.edgePitch || defaultSettings.edgePitch).slice(0, 20),
    edgeVolume: String(raw.edgeVolume || defaultSettings.edgeVolume).slice(0, 20),
    interruptProfile: INTERRUPT_PROFILES.has(profile) ? profile : "normal",
    promptTokenRatePer1k: Number.isFinite(Number(raw.promptTokenRatePer1k))
      ? Math.max(0, Number(raw.promptTokenRatePer1k))
      : 0,
    completionTokenRatePer1k: Number.isFinite(Number(raw.completionTokenRatePer1k))
      ? Math.max(0, Number(raw.completionTokenRatePer1k))
      : 0,
  };
}

function createSettingsStore(settingsFile) {
  function loadSettings() {
    try {
      if (!fs.existsSync(settingsFile)) return sanitizeSettings({});
      const raw = fs.readFileSync(settingsFile, "utf8");
      const parsed = JSON.parse(raw);
      return sanitizeSettings({ ...defaultSettings, ...parsed });
    } catch {
      return sanitizeSettings({});
    }
  }

  function saveSettings(next) {
    const merged = sanitizeSettings({ ...defaultSettings, ...(next || {}) });
    fs.writeFileSync(settingsFile, JSON.stringify(merged, null, 2), "utf8");
    return merged;
  }

  return { loadSettings, saveSettings };
}

module.exports = {
  defaultSettings,
  INTERRUPT_PROFILES,
  sanitizeSettings,
  createSettingsStore,
};
