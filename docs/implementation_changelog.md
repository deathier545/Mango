# Mango Plan Implementation Changelog

This changelog summarizes work completed from the competitive deep-research plan.

## 1) Competitive research deliverables

- Added source-backed matrix: `docs/competitor_matrix.md`
  - 20 comparable systems across assistants/frameworks/platforms.
  - Tagged features: turn-taking, tooling, telephony, memory, safety.
  - Prioritized “copy/adopt” ideas list.

## 2) Turn-taking and interruption quality

- Added interruption profiles (`strict`/`normal`/`fast`): `mango/interruption_policy.py`
- Mapped and documented profile behavior: `docs/interruption_profiles.md`
- Wired profile usage into:
  - barge-in behavior in `mango/main.py`
  - wake capture timing in `mango/wake_capture.py`
  - config/env surface in `mango/config.py` and `.env.example`

## 3) Planner/executor structured loop

- Added explicit step-state model: `mango/planner_executor.py`
- Integrated into `_speaking_reply` in `mango/main.py`
  - Tracks tool step status (`completed`, `failed`, `needs_confirmation`)
  - Emits compact step traces on loop-limit fallback

## 4) Handoff contracts and service boundaries

- Added specialist handoff contracts: `mango/handoff_contracts.py`
- Added router service: `mango/integration_services.py`
- Enforced contract validation in `mango/tool_registry.py`

## 5) Telephony upgrades

- Extended `phone_call` tool:
  - `voicemail_policy`: `leave_message|brief|hangup`
  - `transfer_to` warm-transfer target (E.164 validation)
- Updated TwiML generation and runtime validation in `mango/tools/phone_call.py`

## 6) Memory personalization tiers

- Added memory tiers in config:
  - `session`, `day`, `profile`
- Implemented in `mango/config.py`
- Documented in `.env.example` and `README.md`

## 7) Observability and safety instrumentation

- Added lightweight metrics core: `mango/metrics.py`
  - correlation IDs
  - optional JSONL sink (`MANGO_METRICS_JSONL`)
- Added central timeout constants: `mango/timeouts.py`
- Added per-tool risk metadata + metrics in `mango/tool_registry.py`
- Added wake trigger/reject metrics in `mango/wake_listener.py`
- Added rotating file logs in `mango/logging_setup.py`

## 8) Spotify decomposition and adapters

- Extracted Spotify modules:
  - URI/app handoff: `mango/spotify_uri_launcher.py`
  - track/URI resolution: `mango/spotify_track_resolver.py`
  - playback routing: `mango/spotify_playback_router.py`
- Added integration adapters and protocols in `mango/integration_services.py`
- Simplified orchestrator flow in `mango/tools/spotify_play.py`

## 9) Testing and quality gates

- Added/expanded tests for new capabilities:
  - `tests/test_interruption_policy.py`
  - `tests/test_replay_interrupt_cases.py`
  - `tests/test_wake_replay_cases.py`
  - `tests/test_planner_executor.py`
  - `tests/test_handoff_contracts.py`
  - `tests/test_phone_call.py`
  - `tests/test_turn_engine_integration.py`
- Added toolchain config:
  - `ruff.toml`
  - `mypy.ini`
  - `.pre-commit-config.yaml`
- Added reproducible dependency set: `requirements-pinned.txt`

## 10) Current validation snapshot

- Test suite: `82 passed, 1 skipped`
- Lint diagnostics on changed files: clean
