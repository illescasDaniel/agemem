"""Jev by default; explicit local QSIV, with physical eight-question batching."""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

from jevmem.decider import Answer, ChoiceQ, DeciderUnavailable, NoulQ


class Disabled:
    calls = 0
    input_tokens = 0

    def ask(self, state, questions):
        raise DeciderUnavailable("Hosted decisions disabled in offline mode")


class HostedJev:
    """Uses the Jev SDK, without loading or modifying global jev-mem settings."""
    def __init__(self, max_calls=32, max_input_tokens=80000, local_url=None, model=None):
        self.calls = self.input_tokens = 0
        self.max_calls, self.max_input_tokens = max_calls, max_input_tokens
        self.client = None
        self.local_url, self.model = local_url, model
        if local_url:
            from urllib.parse import urlparse
            if urlparse(local_url).hostname not in ("localhost", "127.0.0.1", "::1"):
                raise ValueError("Local decision endpoints must use a loopback host")

    def ask(self, state, questions):
        if not questions:
            return {}
        estimate = len(json.dumps(state).encode()) + sum(len(q.instructions.encode()) + 128
                                                        for q in questions.values()) + 2048
        if self.calls >= self.max_calls or self.input_tokens + estimate > self.max_input_tokens:
            raise DeciderUnavailable("Decision budget exhausted")
        from typesafe_sdk import Choice, Noul, TypeSafeClient, TypeSafeError
        from typesafe_sdk._core.retry import RetryPolicy
        if self.client is None:
            key = "unused-local" if self.local_url else os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
            if not key:
                raise DeciderUnavailable("Set TYPESAFE_API_KEY or JEV_API_KEY for hosted Jev")
            self.client = TypeSafeClient(api_key=key, base_url=self.local_url,
                                         retry=RetryPolicy(max_retries=0), timeout=60 if self.local_url else 15)
        qs = {key: Noul(instructions=q.instructions) if isinstance(q, NoulQ)
              else Choice(instructions=q.instructions, criteria=q.criteria) for key, q in questions.items()}
        self.calls += 1  # Count attempts, including failures; no unbounded retries.
        try:
            result = self.client.system_one(state=state, questions=qs, model=self.model,
                                           timeout=60 if self.local_url else 15)
        except TypeSafeError as exc:
            raise DeciderUnavailable("Jev request failed; provider details omitted") from exc
        self.input_tokens += result.usage.input_tokens
        answers = {}
        for key, answer in result.answers.items():
            if answer.type == "noul":
                answers[key] = Answer(p=answer.noul)
            elif answer.type == "choice":
                answers[key] = Answer(choice=answer.choice, probs=dict(answer.probabilities), confidence=answer.confidence)
        if set(answers) != set(questions):
            raise DeciderUnavailable("Jev returned incomplete typed answers")
        return answers


class QSIVDecider:
    """Translate jev-mem questions, preserving state and keys across <=8-question calls.

    Local engine injection is for contract tests; actual weight benchmarks must
    use load(). No text generation or hosted fallback is performed here.
    """
    def __init__(self, decide, runtime="external", max_calls=128):
        self.decide, self.runtime, self.max_calls = decide, runtime, max_calls
        self.calls = self.logical_calls = 0
        self.input_tokens = None  # Native decide() does not expose token usage; unknown is not zero.
        self.latency_s = 0.0

    @classmethod
    def load(cls, directory, runtime="fp8"):
        root = Path(directory).expanduser().resolve()
        if runtime not in ("reference", "fp8"):
            raise ValueError("QSIV runtime must be reference or fp8")
        # Inference is local-only: downloads/setup are an explicit separate operation.
        for name in ("calibration.json", "config.json", "tokenizer"):
            if not (root / name).exists():
                raise DeciderUnavailable(f"Missing QSIV local artifact: {name}")
        try:
            if runtime == "reference":
                from qsiv.reference import ReferenceService
                service = ReferenceService(str(root / "model.safetensors"), str(root / "calibration.json"),
                                           tokenizer_dir=str(root / "tokenizer"))
            else:
                from qsiv.runtime.service import QSIVService
                service = QSIVService(str(root / "qsiv_fp8.safetensors"), str(root / "calibration.json"),
                                      tokenizer_dir=str(root / "tokenizer"), plan_memory_gb=1)
        except (ImportError, OSError, RuntimeError) as exc:
            raise DeciderUnavailable(f"QSIV local runtime unavailable ({type(exc).__name__})") from exc
        return cls(service.decide, runtime)

    def ask(self, state, questions):
        if not questions:
            return {}
        self.logical_calls += 1
        pairs = list(questions.items())
        out = {}
        for start in range(0, len(pairs), 8):
            if self.calls >= self.max_calls:
                raise DeciderUnavailable("QSIV physical-call budget exhausted")
            batch = pairs[start:start + 8]
            typed = []
            for _, q in batch:
                if isinstance(q, NoulQ):
                    typed.append({"type": "noul", "text": q.instructions})
                elif isinstance(q, ChoiceQ):
                    labels = list(q.criteria)
                    typed.append({"type": "choice", "text": q.instructions,
                                  "options": [f"{k}: {q.criteria[k]}" for k in labels]})
                else:
                    raise DeciderUnavailable("Unsupported typed question")
            self.calls += 1
            t = time.perf_counter()
            try:
                result = self.decide({"state": state, "questions": typed})
                if len(result) != len(batch):
                    raise ValueError("Missing QSIV answers")
                for (key, q), answer in zip(batch, result):
                    if isinstance(q, NoulQ):
                        p = float(answer["p_true"])
                        if not math.isfinite(p) or not 0 <= p <= 1:
                            raise ValueError("Invalid probability")
                        out[key] = Answer(p=p, confidence=float(answer.get("confidence", abs(2 * p - 1))))
                    else:
                        labels = list(q.criteria)
                        probabilities = [float(p) for p in answer["probs"]]
                        if len(probabilities) != len(labels) or any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
                            raise ValueError("Invalid choice probabilities")
                        if not math.isclose(sum(probabilities), 1, abs_tol=1e-4):
                            raise ValueError("Unnormalized choices")
                        selected = int(answer["choice"])
                        if not 0 <= selected < len(labels):
                            raise ValueError("Invalid selected option")
                        out[key] = Answer(choice=labels[selected], probs=dict(zip(labels, probabilities)),
                                          confidence=answer.get("confidence"))
            except Exception as exc:
                raise DeciderUnavailable(f"QSIV decision failed ({type(exc).__name__})") from exc
            finally:
                self.latency_s += time.perf_counter() - t
        return out


class CascadingDecider:
    """Ask local first; only uncertain questions go to Jev. Confidence is not correctness."""
    def __init__(self, local, remote, min_confidence=0.9):
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence must be in [0,1]")
        self.local, self.remote, self.min_confidence = local, remote, min_confidence
        self.kept_questions = self.fallback_questions = 0

    @property
    def calls(self):
        return self.local.calls + self.remote.calls

    @property
    def input_tokens(self):
        return self.remote.input_tokens

    def ask(self, state, questions):
        answers = self.local.ask(state, questions)
        uncertain = {}
        for key, q in questions.items():
            answer = answers[key]
            confidence = answer.confidence
            if confidence is None and isinstance(q, NoulQ):
                confidence = abs(2 * answer.p - 1)
            if confidence is None or not math.isfinite(confidence) or confidence < self.min_confidence:
                uncertain[key] = q
        self.fallback_questions += len(uncertain)
        self.kept_questions += len(questions) - len(uncertain)
        if uncertain:
            answers.update(self.remote.ask(state, uncertain))
        return answers
