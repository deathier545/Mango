from __future__ import annotations

from mango.config import Config
from mango.tool_registry import ToolRegistry


def _messages(text: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": text}]


def test_registry_powershell_requires_confirmation_by_default():
    cfg = Config()
    reg = ToolRegistry(cfg)
    out = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("run shell"),
    )
    assert out.startswith("HOST_PENDING_POWERSHELL")


def test_registry_powershell_runs_when_confirmation_disabled():
    cfg = Config(require_powershell_confirmation=False, require_tool_confirmation=False)
    reg = ToolRegistry(cfg)
    out = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("run shell"),
    )
    assert not out.startswith("HOST_PENDING_POWERSHELL")


def test_registry_bad_args_have_structured_error_code():
    cfg = Config()
    reg = ToolRegistry(cfg)
    out = reg.execute("open_app", {}, conversation_messages=_messages("open app"))
    assert out.startswith("ERR_TOOL_BAD_ARGS:open_app:")


def test_registry_powershell_confirm_accepts_confirm_word():
    cfg = Config()
    reg = ToolRegistry(cfg)
    first = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("run shell"),
    )
    assert first.startswith("HOST_PENDING_POWERSHELL")
    reg.try_arm_powershell_from_user("i approve shell")
    second = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("i approve shell"),
    )
    assert not second.startswith("HOST_PENDING_POWERSHELL")


def test_registry_powershell_confirm_rejects_followup_key_mismatch():
    cfg = Config()
    reg = ToolRegistry(cfg)
    first = reg.execute(
        "run_powershell",
        {"command_key": "list_processes"},
        conversation_messages=_messages("list processes"),
    )
    assert first.startswith("HOST_PENDING_POWERSHELL")
    reg.try_arm_powershell_from_user("i approve shell")
    second = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("i approve shell"),
    )
    assert second.startswith("HOST_PENDING_POWERSHELL")
    assert "different command" in second


def test_registry_powershell_generic_confirm_does_not_arm_shell_gate():
    cfg = Config()
    reg = ToolRegistry(cfg)
    first = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("run shell"),
    )
    assert first.startswith("HOST_PENDING_POWERSHELL")
    reg.try_arm_powershell_from_user("confirm")
    second = reg.execute(
        "run_powershell",
        {"command_key": "env_username"},
        conversation_messages=_messages("confirm"),
    )
    assert second.startswith("HOST_PENDING_POWERSHELL")


def test_registry_has_pending_confirmation_reflects_gate_state():
    cfg = Config()
    reg = ToolRegistry(cfg)
    assert reg.has_pending_confirmation() is False
    first = reg.execute(
        "run_powershell",
        {"command_key": "list_processes"},
        conversation_messages=_messages("run shell"),
    )
    assert first.startswith("HOST_PENDING_POWERSHELL")
    assert reg.has_pending_confirmation() is True
    reg.try_arm_powershell_from_user("i approve shell")
    _ = reg.execute(
        "run_powershell",
        {"command_key": "list_processes"},
        conversation_messages=_messages("i approve shell"),
    )
    assert reg.has_pending_confirmation() is False


def test_saved_contact_phone_requires_explicit_contact_intent_by_default():
    cfg = Config()
    reg = ToolRegistry(cfg)
    blocked = reg.execute(
        "saved_contact_phone",
        {"contact": "ariana"},
        conversation_messages=_messages("tell me about ariana"),
    )
    assert blocked.startswith("Host blocked contact info read")


def test_saved_contact_phone_runs_when_contact_intent_disabled():
    cfg = Config(contact_info_require_intent=False)
    reg = ToolRegistry(cfg)
    out = reg.execute(
        "saved_contact_phone",
        {"contact": "ariana"},
        conversation_messages=_messages("tell me about ariana"),
    )
    assert not out.startswith("Host blocked contact info read")


def test_saved_contact_phone_does_not_treat_call_word_as_contact_read_intent():
    cfg = Config()
    reg = ToolRegistry(cfg)
    blocked = reg.execute(
        "saved_contact_phone",
        {"contact": "ariana"},
        conversation_messages=_messages("call ariana"),
    )
    assert blocked.startswith("Host blocked contact info read")
