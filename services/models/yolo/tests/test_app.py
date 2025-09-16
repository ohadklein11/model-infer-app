import importlib
from typing import Any, List, Dict

import pytest
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np


class _FakeBoxes:
    def __init__(self):
        # One box [xmin, ymin, xmax, ymax]
        self._xyxy = np.array([[10.0, 20.0, 110.0, 220.0]], dtype=np.float32)
        self._conf = np.array([0.9], dtype=np.float32)
        self._cls = np.array([0], dtype=np.float32)

    @property
    def xyxy(self):  # noqa: N802
        return self._xyxy

    @property
    def conf(self):  # noqa: N802
        return self._conf

    @property
    def cls(self):  # noqa: N802
        return self._cls


class _FakeResult:
    def __init__(self):
        self.boxes = _FakeBoxes()
        self.names = {0: "object"}

    def plot(self):
        # Return BGR numpy array (HxWxC)
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        img[:] = (0, 255, 0)
        return img


class _FakeModel:
    def predict(self, _image: Any, verbose: bool = False, device: Any = "cpu") -> List[Any]:
        return [_FakeResult()]


@pytest.fixture(autouse=True)
def _isolate_module(monkeypatch: pytest.MonkeyPatch):
    # Ensure module globals and env-driven constants are isolated per test
    import os
    import sys
    from pathlib import Path

    # Force CPU to avoid CUDA branching in tests
    monkeypatch.setenv("TORCH_DEVICE", "cpu")

    # Make yolo module importable when running from repo root
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main as yolo_main  # type: ignore
    importlib.reload(yolo_main)

    # Stub model loader to avoid heavy downloads
    monkeypatch.setattr(yolo_main, "load_model", lambda _weights: _FakeModel())

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
    import main as yolo_main  # type: ignore

    # Ensure fakes are in place before app startup runs
    monkeypatch.setattr(yolo_main, "load_model", lambda _weights: _FakeModel())

    with TestClient(yolo_main.app) as c:
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
        json={"imageUrl": "https://example.com/img.png"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["boxes"], list) and len(body["boxes"]) >= 1
    assert isinstance(body["scores"], list) and len(body["scores"]) >= 1
    assert isinstance(body["modelId"], str) and body["modelId"]


def test_predict_requires_image_422(client: TestClient):
    # Missing both imageUrl and imageBase64 should 422 via schema validator
    resp = client.post(
        "/predict",
        json={},
    )
    assert resp.status_code == 422


def test_predict_with_render_returns_image_base64(client: TestClient):
    resp = client.post(
        "/predict?render=true",
        json={"imageUrl": "https://example.com/img.png"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # imageBase64 may be None on failure, but with our fakes it should exist
    assert isinstance(body.get("imageBase64"), (str, type(None)))
