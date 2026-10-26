# Adapted from jev-mem 0.4.0; MIT, copyright 2026 Daniel Illescas Romero.
# Full notice: LICENSE.jevmem in this package.
"""Decision backends. A Decider answers a batch of typed questions over one state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol


@dataclass(frozen=True)
class NoulQ:
    instructions: str


@dataclass(frozen=True)
class ChoiceQ:
    instructions: str
    criteria: dict[str, str]


Question = NoulQ | ChoiceQ


@dataclass
class Answer:
    p: float = 0.0                       # Noul probability
    choice: str | None = None            # Choice selection
    probs: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None


class DeciderUnavailable(Exception):
    """Jev could not be reached or returned something unusable. Callers degrade."""


class Decider(Protocol):
    calls: int

    def ask(self, state: dict, questions: dict[str, Question]) -> dict[str, Answer]: ...


class FakeDecider:
    """Deterministic decider for tests. `rule(state, key, question) -> float | Answer`."""

    def __init__(self, rule: Callable[[dict, str, Question], float | Answer] | None = None):
        self.rule = rule or (lambda s, k, q: 0.0)
        self.calls = 0
        self.log: list[tuple[dict, dict[str, Question]]] = []
        self.down = False

    def ask(self, state: dict, questions: dict[str, Question]) -> dict[str, Answer]:
        if self.down:
            raise DeciderUnavailable("fake outage")
        self.calls += 1
        self.log.append((state, questions))
        out = {}
        for k, q in questions.items():
            v = self.rule(state, k, q)
            out[k] = v if isinstance(v, Answer) else Answer(p=float(v))
        return out
