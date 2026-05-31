# Competitive Matrix (Source-Backed)

This matrix tracks comparable systems and tags each one for features relevant to Mango evolution.

Tags:
- `turn`: turn-taking and interruption handling
- `tool`: tool calling/orchestration
- `phone`: telephony and call routing
- `memory`: durable memory/personalization
- `safety`: guardrails, privacy boundaries, approvals

## Matrix

| System | Category | Tags | Notes |
|---|---|---|---|
| Home Assistant Assist | Open-source assistant | turn, tool, safety | Local-first wake/STT pipelines, smart-home action orchestration, strong self-hosted posture. |
| OpenVoiceOS | Open-source assistant | turn, tool, safety | Plugin-based wake/listener stack and satellite deployment model. |
| Rhasspy | Open-source assistant | turn, tool, safety | Grammar-driven local offline commands and home-automation integrations. |
| Leon | Open-source assistant | turn, tool, safety | Local/offline wake + skill architecture for private personal assistant workflows. |
| ChatGPT Voice / Realtime | Consumer/API assistant | turn, tool, memory | Realtime speech, interruption support, function calling, MCP-style extensibility. |
| Alexa+ | Consumer assistant | turn, tool, memory | Multi-step action orchestration, routines, preference memory, broad service integration. |
| Gemini for Home | Consumer assistant | turn, tool, memory | Natural smart-home control, complex command interpretation, conversational continuity. |
| Siri / Apple Intelligence | Consumer assistant | turn, tool, safety | On-device + private-cloud model, strong privacy boundaries, shortcuts integration. |
| Microsoft Copilot Voice | Consumer/work assistant | turn, tool, memory | Action/plugin orchestration and business workflow integration via connectors. |
| Pipecat | Voice-agent framework | turn, tool | Streaming architecture, smart turn detection, interruption strategy controls. |
| LiveKit Agents | Voice-agent framework | turn, tool | Adaptive interruption handling, low-latency voice agent runtime patterns. |
| Vapi | Voice-agent platform | turn, tool, phone, memory | Call routing/handoff, context-preserving transfer, telephony-focused tool layer. |
| Retell AI | Voice-agent platform | turn, tool, phone | Production call control (transfer/DTMF), interruption settings, telephony orchestration. |
| ElevenLabs Agents | Voice-agent platform | turn, tool, phone, memory | Strong conversational voice quality with workflow/tool integrations and multi-channel paths. |
| Bland | Voice-agent platform | turn, tool, phone, memory | Pathway-based call orchestration, persona routing, human handoff patterns. |
| Hume EVI | Voice-agent platform | turn, memory | Prosody-aware turn timing and response style adaptation for more natural dialog. |
| NVIDIA Riva | Speech platform | turn, safety | Realtime ASR endpointing and production-grade speech pipeline tuning patterns. |
| Open Interpreter | Agent/tool system | tool, safety | Local desktop execution and approval-gated computer control primitives. |
| LangGraph | Agent framework | tool, memory, safety | Durable stateful orchestration with human-in-the-loop patterns for complex tasks. |
| CrewAI | Agent framework | tool, memory | Role-based multi-agent delegation with explicit task decomposition patterns. |

## High-Value Idea Extraction (What Mango Should Copy)

1. Adaptive interruption policy profiles (LiveKit + Pipecat pattern).
2. Explicit planner/executor state for multi-step tool tasks (Alexa+/Copilot + LangGraph pattern).
3. Context-preserving specialist handoffs between tool domains (Vapi/Bland squads pattern).
4. Warm transfer + voicemail strategy primitives for phone flows (Vapi/Retell pattern).
5. Memory tiering with user controls and clear privacy boundaries (Apple + Alexa memory boundary pattern).
6. Satellite/deployment profiles for edge vs host processing (OpenVoiceOS/Home Assistant pattern).
7. Approval + risk-aware tool policy with safer logs for high-risk actions (Open Interpreter + enterprise agent patterns).

## Source Links

- Home Assistant Assist: https://www.home-assistant.io/voice_control/
- Home Assistant wake words: https://home-assistant.io/voice_control/about_wake_word
- OpenVoiceOS tech docs: https://openvoiceos.github.io/ovos-technical-manual/312-wake_word_plugins/
- Rhasspy repo: https://github.com/rhasspy/rhasspy/
- Leon repo/docs: https://github.com/leon-ai/leon/ and https://docs.getleon.ai/
- OpenAI Realtime/voice: https://openai.com/index/introducing-gpt-realtime/
- Alexa+ features: https://www.aboutamazon.com/news/devices/new-alexa-top-features
- Gemini for Home: https://blog.google/products-and-platforms/devices/google-nest/gemini-for-home-launch/
- Apple Intelligence: https://www.apple.com/newsroom/2025/06/apple-intelligence-gets-even-more-powerful-with-new-capabilities-across-apple-devices/
- Copilot voice/actions: https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/overview-business-applications
- Pipecat docs: https://docs.pipecat.ai/pipecat/learn/speech-input
- LiveKit interruption handling: https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling.md
- Vapi docs: https://docs.vapi.ai/
- Retell orchestration: https://docs.retellai.com/general/orchestration_overview
- ElevenLabs agents: https://elevenlabs.io/docs/eleven-agents/overview
- Bland docs: https://docs.bland.ai/
- Hume EVI docs: https://dev.hume.ai/docs/speech-to-speech-evi/overview
- NVIDIA Riva docs: https://docs.nvidia.com/deeplearning/riva/user-guide/docs/
- Open Interpreter docs: https://docs.openinterpreter.com/
- LangGraph repo: https://github.com/langchain-ai/langgraph/
- CrewAI ecosystem references: https://github.com/crewAIInc/crewAI
