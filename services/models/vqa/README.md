### Visual Question Answering (VQA) service

Answer natural-language questions about an input image using a Hugging Face VQA model served via FastAPI.

### Environment variables

The service behavior can be configured via the following environment variables:

- **`MODEL_ID`**: Hugging Face model identifier to load.
  - **Default**: `dandelin/vilt-b32-finetuned-vqa`

- **`TORCH_DEVICE`**: Selects inference device.
  - **Values**: `cpu` (default) | `cuda`
  - **Behavior**:
    - `cpu`: Runs on CPU
    - `cuda`: Uses GPU if available; falls back to CPU with a warning if CUDA is unavailable

- **`MAX_INPUT_TOKENS`**: Maximum allowed tokenized length of the `question`.
  - **Default**: `2048`
  - **Behavior**: If the tokenized question length exceeds this limit, returns `422` (Unprocessable Entity)

- **`REQUEST_TIMEOUT_SECONDS`** (alias: **`REQUEST_TIMEOUT`**): Timeout for the entire `POST /predict` request.
  - **Default**: `10`
  - **Behavior**: If end-to-end processing exceeds the timeout, returns `504` (Gateway Timeout)

### API

- **Health**: `GET /health`
  - Response: `{ "status": "ok", "modelReady": true|false }`

- **Predict**: `POST /predict`
  - Request (one of `imageBase64` or `imageUrl` is required):
    - `imageBase64` (string, optional): Base64-encoded image
    - `imageUrl` (string, optional): URL of the image
    - `question` (string, required): non-empty question. Note: string length is capped at 512 chars; token-length is also validated by `MAX_INPUT_TOKENS`.
  - Response:
    - `answer` (string): predicted answer
    - `score` (number): model confidence score
    - `modelId` (string): identifier of the loaded model

- **Metrics**: `GET /metrics`
  - JSON object with basic counters and latency stats, e.g. `totalRequests`, `successful`, `errors`, `avgLatencyMs`, `uptimeSeconds`.

### Usage examples

- **Local (defaults)**

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8092
```

- **Local (custom model, GPU if available, stricter limits)**

```bash
export MODEL_ID=dandelin/vilt-b32-finetuned-vqa
export TORCH_DEVICE=cuda           # falls back to CPU if CUDA is unavailable
export MAX_INPUT_TOKENS=512
export REQUEST_TIMEOUT_SECONDS=10
uv run uvicorn main:app --host 0.0.0.0 --port 8092
```

- **Docker** (run from `services/models/vqa/`)

```bash
docker build -t model-vqa-serve .
docker run \
  -e MODEL_ID=dandelin/vilt-b32-finetuned-vqa \
  -e TORCH_DEVICE=cpu \
  -e MAX_INPUT_TOKENS=2048 \
  -e REQUEST_TIMEOUT_SECONDS=10 \
  -p 8092:8092 model-vqa-serve
```

### Example requests

- **With image URL**

```bash
curl -s -X POST 'http://localhost:8092/predict' \
  -H 'Content-Type: application/json' \
  -d '{
        "imageUrl": "https://example.com/cat.jpg",
        "question": "What animal is shown?"
      }'
```

- **With base64 image**

```bash
BASE64_IMG=$(base64 -w 0 ./cat.jpg)
curl -s -X POST 'http://localhost:8092/predict' \
  -H 'Content-Type: application/json' \
  -d "{\n  \"imageBase64\": \"$BASE64_IMG\",\n  \"question\": \"What animal is shown?\"\n}"
```

### Notes

- On startup, the service warms up the model so `modelReady` becomes `true` shortly after launch.
- When `TORCH_DEVICE=cuda` is set but CUDA is unavailable, the service logs a warning and runs on CPU.
