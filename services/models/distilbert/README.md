### Environment variables

The service behavior can be configured via the following environment variables:

- **`MODEL_ID`**: Hugging Face model identifier to load.
  - **Default**: `distilbert-base-uncased-finetuned-sst-2-english`

- **`TORCH_DEVICE`**: Selects inference device.
  - **Values**: `cpu` (default) | `cuda`
  - **Behavior**:
    - `cpu`: Runs on CPU
    - `cuda`: Uses GPU if available; falls back to CPU with a warning if CUDA is unavailable

- **`MAX_INPUT_TOKENS`**: Maximum allowed tokenized input length.
  - **Default**: `512`
  - **Behavior**: Requests with tokenized length > max return `422` (Unprocessable Entity)

- **`REQUEST_TIMEOUT_SECONDS`** (alias: **`REQUEST_TIMEOUT`**): Timeout for the entire `POST /predict` request.
  - **Default**: `10`
  - **Behavior**: If end-to-end processing exceeds the timeout, returns `504` (Gateway Timeout)

### Usage examples

- **Local (defaults)**

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8091
```

- **Local (custom model, GPU if available, stricter limits)**

```bash
export MODEL_ID=distilbert-base-uncased-finetuned-sst-2-english
export TORCH_DEVICE=cuda           # falls back to CPU if CUDA is unavailable
export MAX_INPUT_TOKENS=256
export REQUEST_TIMEOUT_SECONDS=5
uv run uvicorn main:app --host 0.0.0.0 --port 8091
```

- **Docker**

```bash
docker build -t model-distilbert-serve .
docker run \
  -e MODEL_ID=distilbert-base-uncased-finetuned-sst-2-english \
  -e TORCH_DEVICE=cpu \
  -e MAX_INPUT_TOKENS=512 \
  -e REQUEST_TIMEOUT_SECONDS=10 \
  -p 8091:8091 model-distilbert-serve
```
