# Post-Improvement Validation Report (2026-05-29)

## Environment
- OS: Windows 10 (`10.0.26200`)
- Workspace: `c:\Users\Dylan\jarvis`
- Validation mode: automated + CLI-driven smoke/reliability checks
- Notes: direct microphone wake-word/PTT/barge-in still require live user audio interaction in Electron.

## Pass/Fail Checklist

### 1) End-to-End Interaction Smoke
- Typed chat request/response: **PASS**
  - `python -m mango.text_chat_cli` returned `MANGO_TEXT_RESULT` with `"ok": true`.
- Tool-heavy request path (web search): **PASS**
  - Request triggered `web_search`, executed tool, and returned sanitized natural-language response.
- Wake-word turn (`listen -> think -> speak -> listen`): **BLOCKED (manual desktop/audio required)**
- PTT turn (`Alt+W`) short/long requests: **BLOCKED (manual desktop/audio required)**
- Mid-speech interruption (barge-in): **BLOCKED (manual desktop/audio required)**

### 2) Speech Quality and Tuning
- Config application for `edgeVoice`, `edgeRate`, `edgePitch`, `edgeVolume`, `interruptProfile`: **PASS**
  - Verified with env overrides and `build_config_from_env`.
- Electron settings/env wiring in `main.cjs`: **PASS**
  - `MANGO_EDGE_*` + `MANGO_INTERRUPT_PROFILE` mapping present.
- Runtime response tone sanity check (non-robotic refusal): **PASS**
  - Self-evaluation prompt returned natural text (no "as an AI"/hard refusal boilerplate).
- Persistence across restart via settings UI: **BLOCKED (manual Electron interaction required)**

### 3) Tool Formatting Robustness
- `tests/test_tool_recovery.py`: **PASS**
- `tests/test_speaking_reply_loop.py`: **PASS**
- Combined formatting-focused regressions: **PASS (27 passed)**
- No markup leakage observed in CLI tool-heavy smoke path: **PASS**

### 4) UI Responsive and Visual QA
- Frontend type/build stability (`npm run build`): **PASS**
- Frontend lint baseline (`npm run lint`): **PASS**
- Browser-driven viewport sweep on `http://localhost:5180`: **PARTIAL**
  - Tested `1366x700`, `1366x850`, `1920x1040`.
  - Bottom nav controls and tab switching were visible and stable.
  - Main content rendering was not captured reliably in automation screenshots (nav-only frames), so HUD/content overlap checks remain pending manual Electron verification.

### 5) State Correctness and Data Separation
- Typed chat path remains isolated and returns through text CLI safely: **PASS (no voice-log contamination observed in CLI path)**
- Startup progress clear behavior + HUD/event transitions: **BLOCKED (requires running Electron UI and observing transitions)**

### 6) Reliability and Longevity
- Restart-loop reliability (10 cycles): **PASS**
  - 10/10 cycles returned successful `MANGO_TEXT_RESULT`.
- Extended session soak (30 turns): **PASS**
  - 30/30 sequential turns succeeded, no parser/sanitizer failures observed.
- 20–30 minute live voice session: **BLOCKED (manual audio session required)**

### 7) Automated Regression Suite
- Targeted suite:
  - `tests/test_tool_recovery.py`
  - `tests/test_speaking_reply_loop.py`
  - `tests/test_turn_engine_integration.py`
  - `tests/test_therapy_support.py`
  - Result: **PASS (31 passed)**
- Full suite `python -m pytest -q`: **PASS**
  - `160 passed, 1 skipped`

## Issue Log

### 1) Browser automation visual limitation (web mode)
- Severity: **P2**
- Area: UI QA capture path
- Repro:
  1. Run Vite app (`npm run dev:web`)
  2. Execute browser automation screenshots across multiple viewports
  3. Observe frames that consistently render bottom nav but miss most main content visuals
- Expected:
  - Full viewport screenshots of main content (HUD/chat/log panels) for overlap/clipping checks.
- Actual:
  - Only navigation region is reliably captured by automation; visual content checks are incomplete.
- Likely owner files (for follow-up execution context):
  - `mango-app/src/App.tsx`
  - `mango-app/src/components/MangoHud.tsx`
  - `mango-app/src/App.css`
  - (Execution context) Electron runtime display path

### 2) Manual audio/Electron interaction coverage gap
- Severity: **P2**
- Area: QA execution coverage
- Repro:
  - Requires physical mic + live Electron window:
    - wake-word turn
    - PTT turn
    - mid-speech interruption
    - settings persistence across restart from UI
- Expected:
  - Complete end-to-end validation of voice/listen/speak transitions and persisted settings in desktop app.
- Actual:
  - Not fully automatable from shell/browser harness.
- Likely owner files:
  - `mango-app/src/App.tsx`
  - `mango-app/electron/main.cjs`
  - `mango/voice_loop.py`

## Prioritized Fix Backlog

### Backend (priority order)
1. **P2** Add/expand explicit regression assertions for no-markup leakage on additional malformed variants in text/voice finalization paths.

### UI (priority order)
1. **P2** Execute manual visual QA sweep in Electron (short, laptop, maximized) to verify main content overlap/clipping.
2. **P2** Run mic-enabled smoke pass for wake/PTT/barge-in and confirm settings persistence post-restart.

## Exit Criteria Status
- No tool-markup leakage in user-visible replies: **PASS (automated + CLI evidence)**
- No critical UI clipping/overlap in common window sizes: **PARTIAL (nav/tab checks pass; main content overlap pending Electron manual run)**
- Speech controls persist and apply after restart: **PARTIAL (config apply verified; UI persistence restart confirmation pending manual)**
- Voice/chat state separation verified: **PARTIAL (automated text path verified; live voice+chat desktop interaction pending manual)**
- Full test suite run completed and triaged: **PASS (completed with triage)**
