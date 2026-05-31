"""Tests for therapy_support tool."""

from mango.tools import therapy_support


def test_therapy_crisis_banner():
    out = therapy_support.run("I feel suicidal and don't want to live")
    assert "988" in out or "emergency" in out.casefold()
    assert "clinical care" in out.casefold() or "clinician" in out.casefold() or "software" in out.casefold()


def test_therapy_anxiety_focus():
    out = therapy_support.run("my mind keeps racing before meetings", focus="anxiety")
    assert "Grounding" in out or "grounding" in out.casefold()
