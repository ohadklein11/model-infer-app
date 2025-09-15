import time
import importlib
from typing import List, Dict, Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image


class _FakeModel:
    def to(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _FakeTokenizer:
    def encode(self, text: str, add_special_tokens: bool = True, truncation: bool = False) -> List[int]:
        # Simple tokenization by spaces; adequate for tests enforcing max token length
        num_tokens = len(text.split())
        return [0] * num_tokens


class _FakeProcessor:
    def __init__(self):
        self.tokenizer = _FakeTokenizer()
        # Image processor is not used by the fake pipeline; keep a simple placeholder
        self.image_processor = object()


class _FakePipeline:
    def __init__(self, answer: str = "cat", score: float = 0.95, sleep_seconds: float = 0.0):
        self._answer = answer
        self._score = score
        self._sleep = sleep_seconds

    def __call__(self, *, image: Any, question: str) -> List[Dict[str, Any]]:  # type: ignore[override]
        if self._sleep > 0:
            time.sleep(self._sleep)
        # Return a fixed answer; sufficient to validate response schema and flow
        return [{"answer": self._answer, "score": self._score}]


@pytest.fixture(autouse=True)
def _isolate_module(monkeypatch: pytest.MonkeyPatch):
    # Ensure module globals and env-driven constants are isolated per test
    import os
    import sys
    from pathlib import Path

    # Force CPU to avoid CUDA branching in tests
    monkeypatch.setenv("TORCH_DEVICE", "cpu")

    # Make vqa module importable when running from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main as vqa_main  # type: ignore
    importlib.reload(vqa_main)

    # Stub model loader to avoid heavy downloads
    monkeypatch.setattr(vqa_main, "load_model", lambda _model_id: (_FakeModel(), _FakeTokenizer()))

    # Stub transformers AutoProcessor and pipeline to light-weight fakes
    import transformers  # type: ignore
    monkeypatch.setattr(transformers, "AutoProcessor", type("_AP", (), {"from_pretrained": staticmethod(lambda *_a, **_k: _FakeProcessor())}))
    monkeypatch.setattr(transformers, "pipeline", lambda *_args, **_kwargs: _FakePipeline())

    # Stub shared image utilities to avoid network and image processing
    import shared  # type: ignore

    def _fake_download_image_to_pil(_url: str, *_args: Any, **_kwargs: Any) -> Image.Image:
        return Image.new("RGB", (320, 240), color=(128, 128, 128))

    def _fake_decode_base64_image_to_pil(_b64: str) -> Image.Image:
        return Image.new("RGB", (320, 240), color=(128, 128, 128))

    def _fake_prepare_image_min_size_rgb(img: Image.Image) -> Image.Image:
        return img

    monkeypatch.setattr(shared, "download_image_to_pil", _fake_download_image_to_pil)
    monkeypatch.setattr(shared, "decode_base64_image_to_pil", _fake_decode_base64_image_to_pil)
    monkeypatch.setattr(shared, "prepare_image_min_size_rgb", _fake_prepare_image_min_size_rgb)

    yield


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import main as vqa_main  # type: ignore
    import transformers  # type: ignore
    import shared  # type: ignore

    # Ensure fakes are in place before app startup runs
    monkeypatch.setattr(vqa_main, "load_model", lambda _model_id: (_FakeModel(), _FakeTokenizer()))
    monkeypatch.setattr(transformers, "AutoProcessor", type("_AP", (), {"from_pretrained": staticmethod(lambda *_a, **_k: _FakeProcessor())}))
    monkeypatch.setattr(transformers, "pipeline", lambda *_args, **_kwargs: _FakePipeline())

    def _fake_download_image_to_pil(_url: str, *_args: Any, **_kwargs: Any) -> Image.Image:
        return Image.new("RGB", (320, 240), color=(128, 128, 128))

    def _fake_decode_base64_image_to_pil(_b64: str) -> Image.Image:
        return Image.new("RGB", (320, 240), color=(128, 128, 128))

    def _fake_prepare_image_min_size_rgb(img: Image.Image) -> Image.Image:
        return img

    monkeypatch.setattr(shared, "download_image_to_pil", _fake_download_image_to_pil)
    monkeypatch.setattr(shared, "decode_base64_image_to_pil", _fake_decode_base64_image_to_pil)
    monkeypatch.setattr(shared, "prepare_image_min_size_rgb", _fake_prepare_image_min_size_rgb)

    # Use a small default token limit, configurable per test if needed
    monkeypatch.setattr(vqa_main, "MAX_INPUT_TOKENS", 8)

    with TestClient(vqa_main.app) as c:
        yield c


def test_health_ready(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["modelReady"] is True


def test_predict_valid_with_image_url(client: TestClient):
    resp = client.post(
        "/predict",
        json={"imageUrl": "https://example.com/img.png", "question": "What is shown?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["answer"], str) and body["answer"]
    assert isinstance(body["score"], float)
    assert isinstance(body["modelId"], str) and body["modelId"]


def test_predict_empty_question_422(client: TestClient):
    resp = client.post(
        "/predict",
        json={"imageUrl": "https://example.com/img.png", "question": "   "},
    )
    assert resp.status_code == 422


def test_predict_requires_image_422(client: TestClient):
    # Missing both imageUrl and imageBase64 should 422 via schema validator
    resp = client.post(
        "/predict",
        json={"question": "Is there a cat?"},
    )
    assert resp.status_code == 422


def test_predict_too_long_422(monkeypatch: pytest.MonkeyPatch, client: TestClient):
    import main as vqa_main  # type: ignore
    # Tighten limit to 5 tokens
    monkeypatch.setattr(vqa_main, "MAX_INPUT_TOKENS", 5)
    # 6 tokens input → should exceed
    resp = client.post(
        "/predict",
        json={
            "imageUrl": "https://example.com/img.png",
            "question": "one two three four five six",
        },
    )
    assert resp.status_code == 422


def test_predict_timeout_504(monkeypatch: pytest.MonkeyPatch):
    # Recreate app with a slow pipeline to trigger timeout
    import main as vqa_main  # type: ignore
    import transformers  # type: ignore
    import shared  # type: ignore

    # Set very short timeout
    monkeypatch.setattr(vqa_main, "REQUEST_TIMEOUT_SECONDS", 0.01)

    # Make pipeline sleep longer than timeout
    slow_pipeline = _FakePipeline(sleep_seconds=0.05)
    monkeypatch.setattr(transformers, "AutoProcessor", type("_AP", (), {"from_pretrained": staticmethod(lambda *_a, **_k: _FakeProcessor())}))
    monkeypatch.setattr(transformers, "pipeline", lambda *_args, **_kwargs: slow_pipeline)

    # Ensure shared functions are stubbed to avoid external calls
    def _fake_download_image_to_pil(_url: str, *_args: Any, **_kwargs: Any) -> Image.Image:
        return Image.new("RGB", (320, 240), color=(128, 128, 128))

    def _fake_prepare_image_min_size_rgb(img: Image.Image) -> Image.Image:
        return img

    monkeypatch.setattr(shared, "download_image_to_pil", _fake_download_image_to_pil)
    monkeypatch.setattr(shared, "prepare_image_min_size_rgb", _fake_prepare_image_min_size_rgb)

    # Recreate TestClient so startup uses slow pipeline
    with TestClient(vqa_main.app) as c:
        resp = c.post(
            "/predict",
            json={"imageUrl": "https://example.com/img.png", "question": "What is this?"},
        )
        assert resp.status_code == 504


def test_metrics_counts_and_avg_latency(client: TestClient):
    # Warmup call to ensure model is ready and metrics middleware installed
    resp = client.get("/health")
    assert resp.status_code == 200

    # Perform multiple predictions with varying latencies (fake pipeline is fast)
    n = 3
    for i in range(n):
        r = client.post(
            "/predict",
            json={"imageUrl": "https://example.com/img.png", "question": f"hello {i}"},
        )
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
    r = client.post(
        "/predict",
        json={"imageUrl": "https://example.com/img.png", "question": "hello"},
    )
    assert r.status_code == 200
    # Middleware should add x-request-id
    assert "x-request-id" in r.headers
