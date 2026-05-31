from mango.always_listen_gate import (
    DEFAULT_PREFIX_ONLY_MISHEARS,
    letters_only_lower,
    transcript_starts_with_any_prefix,
    transcript_starts_with_prefix,
)


def test_letters_only_strips_punct() -> None:
    assert letters_only_lower("Hey, Mango!") == "heymango"


def test_transcript_starts_with_prefix_punctuation() -> None:
    assert transcript_starts_with_prefix("Hey, mango what's the weather", "hey mango")
    assert transcript_starts_with_prefix("HEYMANGO", "hey mango")
    assert not transcript_starts_with_prefix("Oh hey mango", "hey mango")
    assert not transcript_starts_with_prefix("mango hey", "hey mango")


def test_empty_prefix_always_true() -> None:
    assert transcript_starts_with_prefix("anything", "")
    assert transcript_starts_with_prefix("x", "   ")


def test_transcript_starts_with_any_prefix() -> None:
    prefs = DEFAULT_PREFIX_ONLY_MISHEARS
    assert transcript_starts_with_any_prefix("Hey, mingo what's up", prefs)
    assert transcript_starts_with_any_prefix("Mango, lights on", prefs)
    assert transcript_starts_with_any_prefix("Hey main go what's up", prefs)
    assert transcript_starts_with_any_prefix("Hay mango there", prefs)
    assert transcript_starts_with_any_prefix("Hi mango do this", prefs)
    assert transcript_starts_with_any_prefix("Yo mango test", prefs)
    assert transcript_starts_with_any_prefix("Hey Margo what's up", prefs)
    assert transcript_starts_with_any_prefix("Main go what's up", prefs)
    assert transcript_starts_with_any_prefix("Mingo turn on the light", prefs)
    assert transcript_starts_with_any_prefix("May go ahead", prefs)
    assert not transcript_starts_with_any_prefix("Oh hey mango", prefs)
    assert transcript_starts_with_any_prefix("anything", ())
