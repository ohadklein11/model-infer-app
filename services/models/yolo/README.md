### YOLO object detection service

Serve Ultralytics YOLO11 object detection via FastAPI. Loads pretrained detection weights (e.g., `yolo11n.pt`) and returns bounding boxes and class labels.

Reference weights: see `Ultralytics/YOLO11` on Hugging Face for `yolo11n.pt`, `yolo11s.pt`, etc. [Link](https://huggingface.co/Ultralytics/YOLO11/tree/main)

### Environment variables

Configure the service with the following variables:

- `MODEL_WEIGHTS`: YOLO11 pretrained detection weights file name or path.
  - Default: `yolo11n.pt`
  - Note: detection-only; `-seg.pt` and `-pose.pt` are rejected.
  - See Also: https://docs.ultralytics.com/tasks/detect/

- `TORCH_DEVICE`: Inference device.
  - Values: `cpu` (default) | `cuda`
  - Behavior: `cuda` uses GPU if available; otherwise falls back to CPU with a warning.

- `REQUEST_TIMEOUT_SECONDS` (alias: `REQUEST_TIMEOUT`): Timeout for the entire `POST /predict` request.
  - Default: `10`
  - Behavior: if exceeded, returns `504` (Gateway Timeout).

### API

- Health: `GET /health`
  - Response: `{ "status": "ok", "modelReady": true|false }`

- Predict: `POST /predict`
  - Query params:
    - `render` (boolean, optional): if `true`, returns `imageBase64` with drawn boxes.
  - Request body (one of `imageBase64` or `imageUrl` is required):
    - `imageBase64` (string): Base64-encoded image
    - `imageUrl` (string): URL of the image
  - Response:
    - `boxes` (array): list of `{ label, box: { xmin, xmax, ymin, ymax } }`
    - `scores` (array): detection confidences (float)
    - `modelId` (string): identifier of the loaded weights
    - `imageBase64` (string|null): PNG with boxes when `render=true`; otherwise `null`

- Metrics: `GET /metrics`
  - Basic counters and latency stats: `totalRequests`, `successful`, `errors`, `avgLatencyMs`, `uptimeSeconds`.

### Usage examples

- Local (defaults)

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8093
```

- Local (custom weights, GPU if available)

```bash
export MODEL_WEIGHTS=yolo11s.pt
export TORCH_DEVICE=cuda           # falls back to CPU if CUDA is unavailable
export REQUEST_TIMEOUT_SECONDS=10
uv run uvicorn main:app --host 0.0.0.0 --port 8093
```

- Docker (run from `services/models/yolo/`)

```bash
docker build -t model-yolo-serve .
docker run \
  -e MODEL_WEIGHTS=yolo11n.pt \
  -e TORCH_DEVICE=cpu \
  -e REQUEST_TIMEOUT_SECONDS=10 \
  -p 8093:8093 model-yolo-serve
```

### Example requests

- With image URL

```bash
curl -s -X POST 'http://localhost:8093/predict' \
  -H 'Content-Type: application/json' \
  -d '{
        "imageUrl": "https://ultralytics.com/images/bus.jpg"
      }'
```

- With base64 image and rendering

```bash
# 1x1 transparent PNG
BASE64_IMG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottQAAAABJRU5ErkJggg=='
curl -s -X POST 'http://localhost:8093/predict?render=true' \
  -H 'Content-Type: application/json' \
  -d "{\n  \"imageBase64\": \"$BASE64_IMG\"\n}"
```

### Notes

- On startup, the service warms up the model to set `modelReady=true` shortly after launch.
- The `render=true` option uses Ultralytics result plotting and returns a base64 PNG for quick visual inspection.
