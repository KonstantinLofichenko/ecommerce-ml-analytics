"""Small file-attempt state machine exercised by isolated benchmark recovery tests."""

from dataclasses import dataclass
from uuid import uuid4


@dataclass
class Attempt:
    expected_sha256: str
    identity: str = ""
    state: str = "new"

    def __post_init__(self):
        self.identity = self.identity or str(uuid4())

    def execute(self, observed_sha256, send):
        if self.state != "new":
            raise RuntimeError("Attempt cannot be replayed; start a fresh isolated attempt")
        if observed_sha256 != self.expected_sha256:
            self.state = "rejected"
            raise ValueError("Source checksum mismatch before insert")
        self.state = "uncertain"
        send()  # Any exception leaves this attempt uncertain. Never blindly retry it.
        self.state = "acknowledged"

    def validate(self, exact_match):
        if self.state != "acknowledged" or not exact_match:
            raise ValueError("Unacknowledged or unreconciled attempt")
        self.state = "validated"


def publication_ready(attempts, required):
    return set(attempts) == set(required) and all(
        attempt.state == "validated" for attempt in attempts.values()
    )
