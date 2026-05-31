from __future__ import annotations

from mango.retry_utils import retry_call


def test_retry_call_retries_until_success():
    state = {"n": 0}

    def _op() -> str:
        state["n"] += 1
        if state["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    out = retry_call(
        _op,
        attempts=3,
        base_delay_s=0.0,
        retry_on=(RuntimeError,),
        label="unit_retry",
    )
    assert out == "ok"
    assert state["n"] == 3


def test_retry_call_retries_on_result_predicate():
    state = {"n": 0}

    def _op() -> int:
        state["n"] += 1
        return 500 if state["n"] < 2 else 200

    out = retry_call(
        _op,
        attempts=3,
        base_delay_s=0.0,
        retry_if_result=lambda code: code >= 500,
        label="unit_result_retry",
    )
    assert out == 200
    assert state["n"] == 2


def test_retry_call_uses_linear_backoff(monkeypatch):
    waits: list[float] = []

    def _sleep(seconds: float) -> None:
        waits.append(seconds)

    state = {"n": 0}

    def _op() -> str:
        state["n"] += 1
        raise RuntimeError("transient")

    monkeypatch.setattr("mango.retry_utils.time.sleep", _sleep)
    try:
        retry_call(
            _op,
            attempts=3,
            base_delay_s=0.2,
            retry_on=(RuntimeError,),
            label="unit_linear_backoff",
        )
    except RuntimeError:
        pass
    assert waits == [0.2, 0.4]
