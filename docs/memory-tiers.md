# Memory tiers

Mango stores conversation history in RAM during a run. **Cross-restart memory** is opt-in and stored as plaintext JSON under `%USERPROFILE%\.mango\memory\` (unless you override `MANGO_MEMORY_DIR`).

## Pick one

| Tier | Env | Best for |
|------|-----|----------|
| **session** (default) | `MANGO_MEMORY_TIER=session` | Privacy-first: nothing survives restart |
| **day** | `MANGO_MEMORY_TIER=day` | Same-day continuity; rolling merge ~1 day |
| **profile** | `MANGO_MEMORY_TIER=profile` | Long-running assistant; merges ~14 days of daily snapshots |

`MANGO_MEMORY_TIER` overrides the older `MANGO_PERSISTENT_MEMORY=1` switch. Use only one style.

## Related knobs

- `MANGO_MAX_CONVERSATION_MESSAGES` — rolling cap in the active session (default 36)
- `MANGO_MEMORY_MAX_MESSAGES` — floor when persistent memory is on (default 120)
- `MANGO_MEMORY_DAILY_SNAPSHOTS=1` — UTC daily files under `memory/days/`
- `MANGO_MEMORY_MERGE_DAYS` — how far back to merge on startup (profile default 14)

## Recommendation

Start with **session**. Turn on **day** if you want “remember what we said earlier today” after restarts. Use **profile** only if you accept plaintext history on disk and want Mango to stay consistent across weeks.
