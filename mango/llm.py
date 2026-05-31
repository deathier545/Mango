"""Groq and local Ollama chat completions with OpenAI-compatible tool calling."""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
from types import SimpleNamespace
from typing import Any

import httpx
from groq import BadRequestError, Groq

logger = logging.getLogger(__name__)

_TOOL_RETRY_HINT = (
    "\n\n[Required] Invoke tools ONLY through the host native tool/function channel — "
    "never print <function=name {...}> tags or XML. "
    "Tool JSON arguments must match types exactly (integers as JSON numbers, e.g. 5 not \"5\")."
)

_GROQ_TOOL_NATIVE_REMINDER = (
    "\n\n[Groq] Request tools only via the API's native tool_calls field — "
    "never emit pseudo-tags like <function=tool_name {...}>; Groq rejects those with tool_use_failed."
)


def _groq_messages_with_tool_reminder(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = copy.deepcopy(messages)
    for m in out:
        if m.get("role") == "system":
            base = str(m.get("content") or "").rstrip()
            if "native tool_calls" in base.casefold() or "native tool calls" in base.casefold():
                return out
            m["content"] = base + _GROQ_TOOL_NATIVE_REMINDER
            return out
    out.insert(0, {"role": "system", "content": _GROQ_TOOL_NATIVE_REMINDER.strip()})
    return out


def _is_tool_use_failed(exc: BadRequestError) -> bool:
    body = exc.body
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("code") == "tool_use_failed":
            return True
    return False


def _failed_generation_text(exc: BadRequestError) -> str:
    body = exc.body
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            fg = err.get("failed_generation")
            if isinstance(fg, str):
                return fg
    return ""


class GroqLLM:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 90.0) -> None:
        self._client = Groq(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._model_fast = (os.getenv("MANGO_GROQ_MODEL_FAST", "").strip() or None)
        self._model_complex = (os.getenv("MANGO_GROQ_MODEL_COMPLEX", "").strip() or None)

    def _resolve_model(self, route_hint: str | None) -> str:
        if route_hint == "fast" and self._model_fast:
            return self._model_fast
        if route_hint == "complex" and self._model_complex:
            return self._model_complex
        return self._model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        route_hint: str | None = None,
    ) -> Any:
        model = self._resolve_model(route_hint)
        logger.debug(
            "Groq request model=%r route_hint=%r messages=%d tools=%d",
            model,
            route_hint,
            len(messages),
            len(tools),
        )

        def _create(
            msgs: list[dict[str, Any]], temperature: float
        ) -> Any:
            return self._client.chat.completions.create(
                model=model,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=True,
                temperature=temperature,
            )

        groq_messages = _groq_messages_with_tool_reminder(messages)
        try:
            response = _create(groq_messages, 0.25)
        except BadRequestError as exc:
            if not _is_tool_use_failed(exc):
                self._log_http_error(exc)
                raise
            failed_generation = _failed_generation_text(exc)
            if re.search(r"<function\s*(?:=|/)", failed_generation, re.IGNORECASE):
                logger.warning(
                    "Groq tool_use_failed contains salvageable pseudo-tool-call; "
                    "skipping API retry so host recovery can run immediately."
                )
                self._log_http_error(exc, expected_tool_mismatch=True)
                raise
            logger.warning(
                "Groq tool_use_failed (malformed tool syntax) — retrying once with format hint",
            )
            retry_messages = _groq_messages_with_tool_reminder(copy.deepcopy(messages))
            if retry_messages and retry_messages[0].get("role") == "system":
                base = retry_messages[0].get("content") or ""
                retry_messages[0]["content"] = base + _TOOL_RETRY_HINT
            else:
                retry_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": (_GROQ_TOOL_NATIVE_REMINDER.strip() + _TOOL_RETRY_HINT),
                    },
                )
            try:
                response = _create(retry_messages, 0.05)
            except BadRequestError as exc2:
                if _is_tool_use_failed(exc2):
                    logger.warning(
                        "Groq retry still tool_use_failed (pseudo-syntax); "
                        "host may salvage from failed_generation.",
                    )
                    self._log_http_error(exc2, expected_tool_mismatch=True)
                else:
                    logger.error("Groq retry after tool_use_failed failed")
                    self._log_http_error(exc2)
                raise
            except Exception as exc2:
                logger.error("Groq retry after tool_use_failed failed")
                self._log_http_error(exc2)
                raise
        except Exception as exc:
            self._log_http_error(exc)
            raise

        choice = response.choices[0]
        fr = getattr(choice, "finish_reason", None)
        msg = choice.message
        has_tools = bool(getattr(msg, "tool_calls", None))
        logger.debug(
            "Groq response finish_reason=%s content_len=%s tool_calls=%s",
            fr,
            len(msg.content or ""),
            has_tools,
        )
        return response

    def _log_http_error(
        self,
        exc: Exception,
        *,
        expected_tool_mismatch: bool = False,
    ) -> None:
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "response", None)
        extra = ""
        if body is not None and hasattr(body, "text"):
            try:
                extra = (body.text or "")[:800]
            except Exception:
                extra = "(could not read response body)"
        msg = (
            "Groq tool_use_failed (model emitted invalid tool syntax; host will salvage if possible) "
            "type=%s status=%s body_snippet=%r"
            if expected_tool_mismatch
            else "Groq API error type=%s status=%s msg=%s body_snippet=%r"
        )
        if expected_tool_mismatch:
            logger.warning(msg, type(exc).__name__, status, extra)
        else:
            logger.error(
                msg,
                type(exc).__name__,
                status,
                exc,
                extra,
                exc_info=True,
            )


def _nested_namespace(obj: Any) -> Any:
    """Map JSON-compatible dict/list shapes into SimpleNamespace trees."""
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _nested_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_nested_namespace(x) for x in obj]
    return obj


def openai_completion_from_response_body(data: dict[str, Any]) -> Any:
    """Normalize Ollama (OpenAI-compat) JSON into an object like Groq's ChatCompletion."""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"LLM response missing choices: keys={list(data.keys())}")
    kwargs: dict[str, Any] = {"choices": _nested_namespace(choices)}
    if "usage" in data:
        kwargs["usage"] = _nested_namespace(data["usage"])
    if "id" in data:
        kwargs["id"] = data["id"]
    return SimpleNamespace(**kwargs)


class OllamaLLM:
    """Local chat via Ollama's ``/v1/chat/completions`` endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        route_hint: str | None = None,
    ) -> Any:
        url = f"{self._base}/v1/chat/completions"
        for attempt in range(1, 4):
            msgs = messages
            temp = 0.25
            if attempt > 1:
                msgs = copy.deepcopy(messages)
                if msgs and msgs[0].get("role") == "system":
                    base = msgs[0].get("content") or ""
                    msgs[0]["content"] = base + _TOOL_RETRY_HINT
                else:
                    msgs.insert(
                        0,
                        {"role": "system", "content": _TOOL_RETRY_HINT.strip()},
                    )
                temp = 0.05
            body: dict[str, Any] = {
                "model": self._model,
                "messages": msgs,
                "temperature": temp,
                "stream": False,
            }
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"

            logger.debug(
                "Ollama request url=%r model=%r route_hint=%r messages=%d tools=%d attempt=%d",
                url,
                self._model,
                route_hint,
                len(msgs),
                len(tools),
                attempt,
            )

            try:
                resp = httpx.post(url, json=body, timeout=self._timeout)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code if exc.response else 0
                if attempt < 3 and code >= 500:
                    logger.warning("Ollama HTTP %s — retrying (%s/3)", code, attempt)
                    time.sleep(0.2 * attempt)
                    continue
                snippet = ""
                try:
                    snippet = (exc.response.text or "")[:800]
                except Exception:
                    snippet = "(could not read body)"
                logger.error(
                    "Ollama HTTP error status=%s msg=%s body_snippet=%r",
                    code,
                    exc,
                    snippet,
                    exc_info=True,
                )
                raise
            except httpx.RequestError as exc:
                if attempt < 3:
                    logger.warning("Ollama request failed — retrying (%s/3): %s", attempt, exc)
                    time.sleep(0.2 * attempt)
                    continue
                logger.error("Ollama request failed: %s", exc, exc_info=True)
                raise

            try:
                data = resp.json()
            except json.JSONDecodeError as exc:
                if attempt < 3:
                    logger.warning("Ollama non-JSON body — retrying (%s/3): %s", attempt, exc)
                    time.sleep(0.2 * attempt)
                    continue
                logger.error("Ollama non-JSON body: %s", exc, exc_info=True)
                raise

            try:
                completion = openai_completion_response_body_safe(data)
            except Exception as exc:
                if attempt < 3:
                    logger.warning("Ollama bad completion shape — retrying (%s/3): %s", attempt, exc)
                    time.sleep(0.2 * attempt)
                    continue
                raise

            choice = completion.choices[0]
            msg = choice.message
            has_tools = bool(getattr(msg, "tool_calls", None))
            fr = getattr(choice, "finish_reason", None)
            logger.debug(
                "Ollama response finish_reason=%s content_len=%s tool_calls=%s",
                fr,
                len(msg.content or ""),
                has_tools,
            )
            return completion

        raise RuntimeError("Ollama chat retry loop fell through")


def openai_completion_response_body_safe(data: dict[str, Any]) -> Any:
    """Parse completion JSON; raise with snippet if structure is wrong."""
    try:
        return openai_completion_from_response_body(data)
    except Exception as exc:
        raw = json.dumps(data)[:600]
        logger.error("Bad Ollama/OpenAI completion JSON: %s snippet=%r", exc, raw)
        raise


def assistant_message_as_dict(message: Any) -> dict[str, Any]:
    """Serialize assistant ChatCompletionMessage to API dict."""
    d: dict[str, Any] = {"role": message.role}
    if message.content is None:
        d["content"] = ""
    else:
        d["content"] = str(message.content)
    if getattr(message, "tool_calls", None):
        d["tool_calls"] = []
        for tc in message.tool_calls:
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn is not None else ""
            raw_args = getattr(fn, "arguments", None) if fn is not None else None
            if raw_args is None:
                raw_args = "{}"
            elif not isinstance(raw_args, str):
                raw_args = str(raw_args)
            d["tool_calls"].append(
                {
                    "id": getattr(tc, "id", ""),
                    "type": getattr(tc, "type", "function"),
                    "function": {"name": name, "arguments": raw_args or "{}"},
                }
            )
    return d


def parse_tool_arguments(raw: str) -> dict[str, Any]:
    try:
        val = json.loads(raw or "{}")
        if isinstance(val, dict):
            return val
        logger.warning(
            "Tool arguments JSON was not an object: type=%s raw=%r",
            type(val).__name__,
            (raw or "")[:400],
        )
        return {}
    except json.JSONDecodeError as exc:
        logger.warning(
            "Tool arguments JSON decode failed: %s raw=%r",
            exc,
            (raw or "")[:400],
        )
        return {}
