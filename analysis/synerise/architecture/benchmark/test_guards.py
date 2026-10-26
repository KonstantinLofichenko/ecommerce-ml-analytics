"""No server required: verify recovery decisions before any writer is invoked."""

import runpy
from pathlib import Path

import pytest

API = runpy.run_path(str(Path(__file__).with_name("guards.py")))
Attempt = API["Attempt"]
ready = API["publication_ready"]


def test_checksum_mismatch_never_calls_writer():
    attempt = Attempt("expected")
    sent = []
    with pytest.raises(ValueError):
        attempt.execute("changed", lambda: sent.append(1))
    assert sent == [] and attempt.state == "rejected"


def test_lost_ack_cannot_replay_or_validate():
    attempt = Attempt("hash")
    sent = []

    def lost():
        sent.append(1)
        raise ConnectionError("Committed insert, discarded acknowledgement")

    with pytest.raises(ConnectionError):
        attempt.execute("hash", lost)
    with pytest.raises(RuntimeError):
        attempt.execute("hash", lambda: sent.append(1))
    with pytest.raises(ValueError):
        attempt.validate(True)
    assert sent == [1] and attempt.state == "uncertain"
    fresh = Attempt("hash")
    assert fresh.identity != attempt.identity


def test_repeat_and_incomplete_publication_rejected():
    attempt = Attempt("hash")
    attempt.execute("hash", lambda: None)
    with pytest.raises(RuntimeError):
        attempt.execute("hash", lambda: pytest.fail("must not insert twice"))
    with pytest.raises(ValueError):
        attempt.validate(False)
    attempt.validate(True)
    assert not ready({"buy": attempt}, ("buy", "page"))
    assert ready({"buy": attempt}, ("buy",))
