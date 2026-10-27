"""Jev by default; explicit local QSIV, with physical eight-question batching."""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

from agemem.notes.decider import Answer, ChoiceQ, DeciderUnavailable, NoulQ


def _lock_qsiv_model():
    """Reserve the local user's QSIV GPU slot until the model process exits."""
    import fcntl

    # A fixed location makes independently launched agents coordinate, even if
    # they use different project directories, model paths, or TMPDIR values.
    directory = Path('/tmp') / f'agemem-qsiv-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        raise DeciderUnavailable('Unsafe QSIV lock directory')
    fd = os.open(directory / 'model.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise DeciderUnavailable('Another QSIV model is already running; stop it before starting another',
                                 {'stage': 'qsiv_startup', 'cause': 'model_in_use'}) from None
    except BaseException:
        os.close(fd)
        raise
    return fd


class Disabled:
    calls = 0
    input_tokens = 0

    def ask(self, state, questions):
        raise DeciderUnavailable("Hosted decisions disabled in offline mode", {"stage": "hosted", "cause": "offline"})


class HostedJev:
    """Uses the Jev SDK, without loading or modifying global jev-mem settings."""
    def __init__(self, max_calls=32, max_input_tokens=80000, local_url=None, model=None, api_key=None):
        self.calls = self.input_tokens = 0
        self.max_calls, self.max_input_tokens = max_calls, max_input_tokens
        self.client = None
        self.local_url, self.model, self.api_key = local_url, model, api_key
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
            raise DeciderUnavailable("Decision budget exhausted", {"stage": "hosted", "cause": "budget_exhausted"})
        from typesafe_sdk import Choice, Noul, TypeSafeClient, TypeSafeError
        from typesafe_sdk._core.retry import RetryPolicy
        if self.client is None:
            key = "unused-local" if self.local_url else self.api_key or os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
            if not key:
                raise DeciderUnavailable("Set TYPESAFE_API_KEY or JEV_API_KEY for hosted Jev", {"stage": "hosted", "cause": "missing_credentials"})
            self.client = TypeSafeClient(api_key=key, base_url=self.local_url,
                                         retry=RetryPolicy(max_retries=0), timeout=60 if self.local_url else 15)
        qs = {key: Noul(instructions=q.instructions) if isinstance(q, NoulQ)
              else Choice(instructions=q.instructions, criteria=q.criteria) for key, q in questions.items()}
        self.calls += 1  # Count attempts, including failures; no unbounded retries.
        try:
            result = self.client.system_one(state=state, questions=qs, model=self.model,
                                           timeout=60 if self.local_url else 15)
        except TypeSafeError as exc:
            name = type(exc).__name__
            categories = {"TypeSafeAuthenticationError": "authentication", "TypeSafePermissionDeniedError": "permission", "TypeSafeRateLimitError": "rate_limit", "TypeSafeAPITimeoutError": "timeout", "TypeSafeAPIConnectionError": "connection", "TypeSafeInternalServerError": "server_error", "TypeSafeBadRequestError": "bad_request"}
            diagnostic = {"stage": "hosted", "cause": categories.get(name, "provider_error")}
            status = getattr(exc, "status", None)
            if type(status) is int and 100 <= status <= 599:
                diagnostic["http_status"] = status
            raise DeciderUnavailable("Jev request failed", diagnostic) from exc
        self.input_tokens += result.usage.input_tokens
        answers = {}
        for key, answer in result.answers.items():
            if answer.type == "noul":
                answers[key] = Answer(p=answer.noul)
            elif answer.type == "choice":
                answers[key] = Answer(choice=answer.choice, probs=dict(answer.probabilities), confidence=answer.confidence)
        if set(answers) != set(questions):
            raise DeciderUnavailable("Jev returned incomplete typed answers", {"stage": "hosted", "cause": "invalid_response"})
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
    def load(cls, directory, runtime="fp8", python=None, *, _native=False):
        if not _native:
            worker = QSIVWorker(python or sys.executable, directory, runtime)
            result = cls(worker.decide, runtime)
            result.worker = worker
            return result
        root = Path(directory).expanduser().resolve()
        if runtime not in ("reference", "fp8"):
            raise ValueError("QSIV runtime must be reference or fp8")
        # Inference is local-only: downloads/setup are an explicit separate operation.
        for name in ("calibration.json", "config.json", "tokenizer"):
            if not (root / name).exists():
                raise DeciderUnavailable(f"Missing QSIV local artifact: {name}")
        lock_fd = _lock_qsiv_model()
        try:
            import torch
            if not torch.cuda.is_available():
                raise DeciderUnavailable("QSIV requires a compatible NVIDIA GPU; select Jev on this machine")
            minimum = (8, 9) if runtime == "fp8" else (8, 0)
            if torch.cuda.get_device_capability() < minimum:
                raise DeciderUnavailable("GPU does not meet this QSIV runtime's requirements; select Jev")
            if runtime == "reference":
                from qsiv.reference import ReferenceService
                service = ReferenceService(str(root / "model.safetensors"), str(root / "calibration.json"),
                                           tokenizer_dir=str(root / "tokenizer"))
            else:
                from qsiv.runtime.service import QSIVService
                service = QSIVService(str(root / "qsiv_fp8.safetensors"), str(root / "calibration.json"),
                                      tokenizer_dir=str(root / "tokenizer"), plan_memory_gb=1)
        except (ImportError, OSError, RuntimeError) as exc:
            os.close(lock_fd)
            raise DeciderUnavailable(f"QSIV GPU runtime unavailable; run agemem doctor or select Jev ({type(exc).__name__})") from exc
        except BaseException:
            os.close(lock_fd)
            raise
        result = cls(service.decide, runtime)
        # Deliberately retain the descriptor for the process lifetime: CUDA may
        # keep allocations after the Python service object is collected.
        return result

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
                diagnostic = getattr(exc, "diagnostic", None) or {"stage": "qsiv", "cause": "inference_failed", "error_type": type(exc).__name__}
                raise DeciderUnavailable(f"QSIV decision failed ({type(exc).__name__})", diagnostic) from exc
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
        try:
            answers = self.local.ask(state, questions)
        except DeciderUnavailable as exc:
            diagnostic = dict(exc.diagnostic or {"stage": "qsiv", "cause": "inference_failed"})
            diagnostic["stage"] = "qsiv"
            raise DeciderUnavailable("Cascade local decision failed", diagnostic) from exc
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
            try:
                answers.update(self.remote.ask(state, uncertain))
            except DeciderUnavailable as exc:
                diagnostic = dict(exc.diagnostic or {"cause": "provider_unavailable"})
                diagnostic["stage"] = "jev_fallback"
                raise DeciderUnavailable("Cascade hosted fallback failed", diagnostic) from exc
        return answers


class _LegacyQSIVWorker:
    """Keep one native model resident in an explicitly configured Python runtime."""
    def __init__(self, python, directory, runtime, timeout=120):
        import subprocess
        import atexit
        self.timeout = timeout
        # Do not forward hosted credentials into the local inference subprocess.
        env = {k: v for k, v in os.environ.items()
               if not any(word in k.upper() for word in ("API_KEY", "TOKEN", "SECRET"))}
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        try:
            self.process = subprocess.Popen(
                [str(Path(python).expanduser()), "-m", "agemem.qsiv_worker",
                 str(Path(directory).expanduser()), runtime],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                text=True, env=env, bufsize=1)
            response = self._read()
            if response.get("ready") is not True:
                raise DeciderUnavailable(response.get("error", "Local QSIV startup failed; run agemem doctor"), response.get("diagnostic"))
        except DeciderUnavailable:
            self.close()
            raise
        except Exception:
            self.close()
            raise DeciderUnavailable("QSIV requires a working compatible NVIDIA GPU runtime; run agemem doctor or select Jev") from None
        atexit.register(self.close)

    def _read(self):
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(self.timeout):
                self.close()
                raise DeciderUnavailable("Local QSIV worker timed out")
            line = self.process.stdout.readline()
        if not line:
            raise DeciderUnavailable("Local QSIV worker stopped")
        return json.loads(line)

    def decide(self, request):
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            response = self._read()
            if "answers" not in response:
                raise ValueError("Worker error")
            return response["answers"]
        except Exception:
            self.close()
            raise DeciderUnavailable("Local QSIV worker failed; run agemem doctor") from None

    def close(self):
        import atexit
        atexit.unregister(self.close)
        process = getattr(self, "process", None)
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except Exception:
                    process.kill()
                    process.wait()
            for pipe in (process.stdin, process.stdout):
                if pipe:
                    pipe.close()

# The public worker uses a shared local service; the old pipe worker remains
# private for compatibility with existing transport tests and non-POSIX hosts.
from .qsiv_shared import QSIVWorker, fcntl as _fcntl
if _fcntl is None:
    QSIVWorker = _LegacyQSIVWorker
