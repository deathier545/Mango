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

function parseMangoEventLine(line) {
  const match = line.match(/MANGO_EVENT:\s*(\{.*\})\s*$/);
  if (!match) return null;
  try {
    const payload = JSON.parse(match[1]);
    const type = String(payload.type || "");
    if (type === "state") {
      const state = String(payload.state || "idle").toLowerCase();
      return { kind: "state", state, text: line };
    }
    if (type === "transcript") {
      return { kind: "transcript", text: String(payload.text || "") };
    }
    if (type === "reply") {
      return { kind: "reply", text: String(payload.text || "") };
    }
    if (type === "globe_state") {
      return { kind: "globe_state", visible: Boolean(payload.visible) };
    }
    if (type === "globe") {
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
    }
    if (type === "audio_level") {
      const level = Number(payload.level);
      if (!Number.isFinite(level)) return null;
      return { kind: "audio_level", level: Math.max(0, Math.min(1, level)) };
    }
    if (type === "duo_phase") {
      return {
        kind: "duo_phase",
        speaker: String(payload.speaker || "mango"),
        phase: String(payload.phase || "idle"),
        text: String(payload.text || ""),
      };
    }
    if (type === "duo_done") {
      return {
        kind: "duo_done",
        ok: Boolean(payload.ok),
        lines: Array.isArray(payload.lines) ? payload.lines : [],
        error: String(payload.error || ""),
      };
    }
    if (type === "metric") {
      const event = String(payload.event || "");
      if (event.startsWith("turn_")) {
        return {
          kind: "metric_turn",
          event,
          correlationId: payload.correlation_id ? String(payload.correlation_id) : null,
          source: payload.source ? String(payload.source) : "",
          sttS: payload.stt_s != null ? Number(payload.stt_s) : null,
          llmS: payload.llm_s != null ? Number(payload.llm_s) : null,
          ttsS: payload.tts_s != null ? Number(payload.tts_s) : null,
        };
      }
      if (event === "tool_start" || event === "tool_done") {
        return {
          kind: "metric_tool",
          event,
          correlationId: payload.correlation_id ? String(payload.correlation_id) : null,
          tool: payload.tool ? String(payload.tool) : "unknown",
          risk: payload.risk ? String(payload.risk) : "unknown",
          ok: payload.ok == null ? null : Boolean(payload.ok),
          durationMs: payload.duration_ms != null ? Number(payload.duration_ms) : null,
        };
      }
      if (event === "noise_guidance") {
        return {
          kind: "noise_guidance",
          source: payload.source ? String(payload.source) : "vad",
          noiseFloor: payload.noise_floor != null ? Number(payload.noise_floor) : null,
          recommendation: payload.recommendation
            ? String(payload.recommendation)
            : "ptt_or_strict_interrupt",
        };
      }
    }
  } catch {
    // ignore malformed marker
  }
  return null;
}

function parseLogLine(line) {
  if (!line) return null;
  const mangoEvent = parseMangoEventLine(line);
  if (mangoEvent) return mangoEvent;
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
      // ignore malformed marker
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

function createLogStream(onLine) {
  let stdoutBuffer = "";
  let stderrBuffer = "";

  function streamToLines(chunk, kind) {
    const txt = chunk.toString("utf8");
    const isOut = kind === "stdout";
    const next = (isOut ? stdoutBuffer : stderrBuffer) + txt;
    const lines = next.split(/\r?\n/);
    const leftover = lines.pop() || "";
    if (isOut) stdoutBuffer = leftover;
    else stderrBuffer = leftover;
    for (const line of lines) {
      if (line.trim()) onLine(kind, line);
    }
  }

  function reset() {
    stdoutBuffer = "";
    stderrBuffer = "";
  }

  return { streamToLines, reset };
}

module.exports = {
  parseLogLine,
  parseMangoEventLine,
  parseUsageLine,
  parseMetricLine,
  createLogStream,
};
