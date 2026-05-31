# Interruption Profiles (Strict / Normal / Fast)

Profiles are resolved by `mango.interruption_policy.resolve_profile()` and applied in both turn and wake paths.

## Profiles

| Profile | min_barge_hold_ms | wake_wait_seconds | wake_silence_multiplier | Intended behavior |
|---|---:|---:|---:|---|
| `strict` | 220 | 3.2 | 1.2 | Reduces accidental interruptions and false wake turn starts in noisy rooms. |
| `normal` | 90 | 2.5 | 1.0 | Balanced default for typical desktop/headset use. |
| `fast` | 20 | 1.8 | 0.85 | Fastest response/interruptions, higher chance of accidental barge-in. |

## Module Mapping

- Turn interruption behavior:
  - `mango/main.py` uses profile `min_barge_hold_ms` inside `_barge()` to require sustained key press before interrupting TTS.
- Wake utterance capture behavior:
  - `mango/wake_capture.py` uses profile `wake_wait_seconds` and `wake_silence_multiplier` to tune speech wait and end-of-utterance behavior.
- Config surface:
  - `mango/config.py` loads `MANGO_INTERRUPT_PROFILE` and stores the resolved profile name.
  - `.env.example` documents `MANGO_INTERRUPT_PROFILE`.
