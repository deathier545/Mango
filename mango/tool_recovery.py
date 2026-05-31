"""Recover when Groq returns tool_use_failed for legacy `<function=name{...}>` pseudo-syntax."""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import TYPE_CHECKING, Any

from mango.tool_definitions import all_builtin_tool_names

if TYPE_CHECKING:
    from mango.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

_VALID_TOOLS = all_builtin_tool_names()
# Public alias for callers that salvage pseudo-syntax from model text.
KNOWN_TOOL_NAMES: frozenset[str] = _VALID_TOOLS


def _failed_generation_from_exc(exc: BaseException) -> str | None:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            fg = err.get("failed_generation")
            if isinstance(fg, str) and fg.strip():
                return fg.strip()
    return None


def _parse_json_object_at(rest: str, open_idx: int) -> dict[str, Any] | None:
    """Extract one balanced `{ ... }` object starting at open_idx; respects string escapes."""
    if open_idx >= len(rest) or rest[open_idx] != "{":
        return None
    depth = 0
    in_str = False
    esc = False
    quote: str | None = None
    i = open_idx
    while i < len(rest):
        ch = rest[i]
        if in_str and quote is not None:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
                quote = None
        else:
            if ch in "\"'":
                in_str = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blob = rest[open_idx : i + 1]
                    try:
                        val = json.loads(blob)
                    except json.JSONDecodeError:
                        return None
                    return val if isinstance(val, dict) else None
        i += 1
    return None


_PSEUDO_TOOL_START = re.compile(r"<function\s*(?:=|/)", re.IGNORECASE)
_XML_TOOL_TAG = re.compile(r"<\s*([a-zA-Z_][a-zA-Z0-9_]*)\b([^>]*)/?>", re.IGNORECASE)
_XML_TOOL_PAIRED_TAG = re.compile(
    r"<\s*([a-zA-Z_][a-zA-Z0-9_]*)\b([^>]*)>\s*([\s\S]*?)\s*</\s*\1\s*>",
    re.IGNORECASE,
)
_FUNCTION_WRAP_RE = re.compile(
    r"<\s*function\s*>\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*</\s*function\s*>",
    re.IGNORECASE,
)
_XML_ATTR_RE = re.compile(
    r"""([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>/]+))""",
    re.IGNORECASE,
)


def _coerce_attr_value(value: str) -> Any:
    raw = (value or "").strip()
    if not raw:
        return ""
    low = raw.casefold()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none"):
        return None
    if re.fullmatch(r"[+-]?\d+", raw):
        try:
            return int(raw)
        except Exception:
            return raw
    if re.fullmatch(r"[+-]?\d+\.\d+", raw):
        try:
            return float(raw)
        except Exception:
            return raw
    return raw


def _json_dict_if_any(text: str) -> dict[str, Any] | None:
    blob = (text or "").strip()
    if not blob or not blob.startswith("{"):
        return None
    try:
        obj = json.loads(blob)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _xml_attrs_as_args(attrs_blob: str) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for am in _XML_ATTR_RE.finditer(attrs_blob or ""):
        key = (am.group(1) or "").strip()
        val = am.group(2) or am.group(3) or am.group(4) or ""
        if key:
            args[key] = _coerce_attr_value(val)
    for json_key in ("arguments", "args", "input"):
        payload = args.get(json_key)
        if isinstance(payload, str):
            parsed = _json_dict_if_any(payload)
            if parsed:
                args.pop(json_key, None)
                args = {**parsed, **args}
                break
    return args


def _extract_xml_pseudo_tool_call(raw: str) -> tuple[str, dict[str, Any]] | None:
    wrapped = _FUNCTION_WRAP_RE.search(raw or "")
    if wrapped:
        name = (wrapped.group(1) or "").strip()
        after = (raw or "")[wrapped.end() :]
        brace = after.find("{")
        if brace < 0:
            return name, {}
        args = _parse_json_object_at(after, brace)
        if args is None:
            return None
        return name, args

    paired = _XML_TOOL_PAIRED_TAG.search(raw or "")
    if paired:
        name = (paired.group(1) or "").strip()
        attrs_blob = paired.group(2) or ""
        body = (paired.group(3) or "").strip()
        args = _xml_attrs_as_args(attrs_blob)
        body_args = _json_dict_if_any(body)
        if body_args:
            args = {**body_args, **args}
        if name.casefold() == "function":
            alias = str(args.pop("name", "") or args.pop("tool", "") or "").strip()
            if not alias:
                alias = body if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", body or "") else ""
            if not alias:
                return None
            name = alias
        return name, args

    m = _XML_TOOL_TAG.search(raw or "")
    if not m:
        return None
    name = (m.group(1) or "").strip()
    if not name:
        return None
    args = _xml_attrs_as_args(m.group(2) or "")
    if name.casefold() == "function":
        alias = str(args.pop("name", "") or args.pop("tool", "") or "").strip()
        if not alias:
            return None
        name = alias
    return name, args


def strip_pseudo_tool_markup_for_speech(text: str) -> str:
    """Remove legacy ``<function=...>`` / ``<function/...>`` tails so TTS never reads them aloud."""
    if not text:
        return text.strip()
    low = text.casefold()
    if "<" not in low:
        return text.strip()
    m = _PSEUDO_TOOL_START.search(text)
    if m:
        return text[: m.start()].strip()
    mfun = re.search(r"<\s*function\b", text, flags=re.IGNORECASE)
    if mfun:
        return text[: mfun.start()].strip()
    m2 = _XML_TOOL_TAG.search(text)
    if m2:
        return text[: m2.start()].strip()
    m3 = re.search(r"<\s*[a-zA-Z_][a-zA-Z0-9_]*(?:\s|>|/)", text)
    if m3:
        return text[: m3.start()].strip()
    return text.strip()


def split_assistant_content_and_pseudo_tool(
    content: str,
) -> tuple[str, tuple[str, dict[str, Any]] | None]:
    """If the model put a pseudo tool tag in plain text, return (spoken_prefix, (name, args)).

    ``spoken_prefix`` is the part before ``<function=`` (may be empty). If no parseable
    pseudo-call, returns ``(content.strip(), None)``.
    """
    raw = (content or "").strip()
    if not raw:
        return ("", None)
    m = _PSEUDO_TOOL_START.search(raw)
    if not m:
        m_xml = _XML_TOOL_TAG.search(raw)
        if not m_xml:
            return (raw, None)
        prefix = raw[: m_xml.start()].strip()
        parsed_xml = _extract_xml_pseudo_tool_call(raw[m_xml.start() :])
        if parsed_xml is None:
            return (strip_pseudo_tool_markup_for_speech(raw), None)
        return (prefix, parsed_xml)
    prefix = raw[: m.start()].strip()
    tail = raw[m.start() :]
    parsed = _extract_pseudo_tool_call(tail)
    if parsed is None:
        return (strip_pseudo_tool_markup_for_speech(raw), None)
    return (prefix, parsed)


def _extract_pseudo_tool_call(failed_generation: str) -> tuple[str, dict[str, Any]] | None:
    """Parse ``<function=name{...}>``, ``<function/name {...}</function>``, etc."""
    raw = re.sub(r"</function>\s*$", "", failed_generation.strip(), flags=re.IGNORECASE)
    xml = _extract_xml_pseudo_tool_call(raw)
    if xml is not None:
        return xml

    m_eq = re.search(r"<function\s*=\s*", raw, flags=re.IGNORECASE)
    m_slash = re.search(r"<function\s*/\s*", raw, flags=re.IGNORECASE)
    if not m_eq and not m_slash:
        return None

    use_slash = m_slash is not None and (m_eq is None or m_slash.start() <= m_eq.start())
    m = m_slash if use_slash else m_eq
    assert m is not None

    tail = raw[m.end() :]
    brace = tail.find("{")
    if brace < 0:
        return None
    name = tail[:brace].strip()
    if not name or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        return None
    args = _parse_json_object_at(tail, brace)
    if args is None:
        return None
    return name, args


def recover_from_groq_tool_use_failed(
    exc: BaseException,
    messages: list[dict[str, Any]],
    registry: ToolRegistry,
) -> bool:
    """Parse ``failed_generation`` pseudo-tags, run the tool locally, append valid messages.

    Caller should invoke ``llm.chat`` again after this returns True.
    """
    fg = _failed_generation_from_exc(exc)
    if not fg:
        return False

    parsed = _extract_pseudo_tool_call(fg)
    if not parsed:
        logger.debug(
            "tool_recovery: could not parse pseudo tool-call from failed_generation=%r",
            fg[:400],
        )
        return False

    name, args = parsed
    if name not in _VALID_TOOLS:
        logger.warning("tool_recovery: unknown salvaged tool %r", name)
        return False
    logger.warning(
        "Groq rejected pseudo tool syntax (%r); salvaging local run of %r args=%s",
        fg[:120],
        name,
        args,
    )

    call_id = f"salv_{uuid.uuid4().hex[:18]}"
    messages.append(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args),
                    },
                }
            ],
        }
    )

    try:
        result = registry.execute(name, args, conversation_messages=messages)
    except Exception:
        logger.exception("tool_recovery: salvaged tool %r execution failed", name)
        messages.pop()
        return False

    messages.append(
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": result,
        }
    )
    return True
