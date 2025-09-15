import time
import importlib
from typing import List, Dict, Any

import pytest
from fastapi.testclient import TestClient


class _FakeModel:
    def to(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeTokenizer:
    def encode(self, text: str, add_special_tokens: bool = True, truncation: bool = False) -> List[int]:
        # Simple tokenization by spaces; adequate for tests enforcing max token length
        num_tokens = len(text.split())
        return [0] * num_tokens


class _FakePipeline:
    def __init__(self, response_label: str = "positive", response_score: float = 0.99, sleep_seconds: float = 0.0):
        self._label = response_label
        self._score = response_score
        self._sleep = sleep_seconds

    def __call__(self, text: str) -> List[Dict[str, Any]]:
        if self._sleep > 0:
            time.sleep(self._sleep)
        # Heuristic to flip label for clearly negative phrasing
        label = self._label
        if any(neg in text.lower() for neg in ["hate", "terrible", "bad"]):
            label = "negative"
        return [{"label": label.upper(), "score": self._score}]


@pytest.fixture(autouse=True)
def _isolate_module(monkeypatch: pytest.MonkeyPatch):
    # Ensure module globals and env-driven constants are isolated per test
    import os
    import sys
    from pathlib import Path
    # Make sure we default to CPU to avoid CUDA branching noise in tests
    monkeypatch.setenv("TORCH_DEVICE", "cpu")
    # Import module fresh each test to pick up env and clean globals
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main as distil_main  # type: ignore
    importlib.reload(distil_main)

    # Stub model/tokenizer loader to avoid heavy downloads
    monkeypatch.setattr(distil_main, "load_model", lambda _model_id: (_FakeModel(), _FakeTokenizer()))

    # Stub transformers.pipeline to light-weight fake
    import transformers  # type: ignore
    monkeypatch.setattr(transformers, "pipeline", lambda *_args, **_kwargs: _FakePipeline())

    yield


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import main as distil_main  # type: ignore
    import transformers  # type: ignore
    # Ensure fakes are in place before app startup runs
    monkeypatch.setattr(distil_main, "load_model", lambda _model_id: (_FakeModel(), _FakeTokenizer()))
    monkeypatch.setattr(transformers, "pipeline", lambda *_args, **_kwargs: _FakePipeline())
    # Use a small default limit configurable per test if needed
    monkeypatch.setattr(distil_main, "MAX_INPUT_TOKENS", 8)
    with TestClient(distil_main.app) as c:
        yield c


def test_health_ready(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["modelReady"] is True


def test_predict_valid_positive(client: TestClient):
    resp = client.post("/predict", json={"text": "I love this library!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] in {"positive", "negative"}
    assert isinstance(body["score"], float)
    assert isinstance(body["modelId"], str) and body["modelId"]


def test_predict_empty_422(client: TestClient):
    resp = client.post("/predict", json={"text": "   "})
    assert resp.status_code == 422


def test_predict_too_long_422(monkeypatch: pytest.MonkeyPatch, client: TestClient):
    import main as distil_main  # type: ignore
    # Tighten limit to 5 tokens
    monkeypatch.setattr(distil_main, "MAX_INPUT_TOKENS", 5)
    # 6 tokens input → should exceed
    resp = client.post("/predict", json={"text": "one two three four five six"})
    assert resp.status_code == 422


def test_predict_timeout_504(monkeypatch: pytest.MonkeyPatch):
    # Recreate app with a slow pipeline to trigger timeout
    import main as distil_main  # type: ignore
    import transformers  # type: ignore

    # Set very short timeout
    monkeypatch.setattr(distil_main, "REQUEST_TIMEOUT_SECONDS", 0.01)

    # Make pipeline sleep longer than timeout
    slow_pipeline = _FakePipeline(sleep_seconds=0.05)
    monkeypatch.setattr(transformers, "pipeline", lambda *_args, **_kwargs: slow_pipeline)

    # Recreate TestClient so startup uses slow pipeline
    with TestClient(distil_main.app) as c:
        resp = c.post("/predict", json={"text": "I love timeouts"})
        assert resp.status_code == 504


def test_metrics_counts_and_avg_latency(client: TestClient):
    # Warmup call to ensure model is ready and metrics middleware installed
    resp = client.get("/health")
    assert resp.status_code == 200

    # Perform multiple predictions with varying latencies (fake pipeline is fast)
    n = 3
    for i in range(n):
        r = client.post("/predict", json={"text": f"hello {i}"})
        assert r.status_code == 200

    # Fetch metrics
    m = client.get("/metrics")
    assert m.status_code == 200
    data = m.json()
    # totalRequests should be at least the number of requests we made here
    assert data["totalRequests"] >= n + 1  # +1 for /health
    assert data["successful"] >= n + 1
    assert data["errors"] >= 0
    assert isinstance(data["avgLatencyMs"], (int, float))
    assert data["avgLatencyMs"] >= 0.0
    assert isinstance(data["uptimeSeconds"], (int, float))


def test_request_id_header_present(client: TestClient):
    r = client.post("/predict", json={"text": "hello"})
    assert r.status_code == 200
    # Middleware should add x-request-id
    assert "x-request-id" in r.headers
