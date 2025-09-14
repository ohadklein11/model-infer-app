### Environment variables

The service behavior can be configured via the following environment variables:

- **`REPO_BACKEND`**: Selects the storage backend.
  - **Values**: `memory` (default) | `mongo`
  - **Behavior**:
    - `memory`: In-process, ephemeral storage (data is lost on restart)
    - `mongo`: Uses MongoDB for persistent storage; requires `MONGO_URL`

- **`MONGO_URL`**: MongoDB connection string/URI.
  - **Required when**: `REPO_BACKEND=mongo`
  - **Example**: `mongodb://user:pass@host:27017/jobapi?authSource=admin`

#### Usage examples

- **Local (memory backend, default)**

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8080
```

- **Local (MongoDB backend)**

```bash
export REPO_BACKEND=mongo
export MONGO_URL='mongodb://localhost:27017'
uv run uvicorn main:app --host 0.0.0.0 --port 8080
```

- **Docker**

```bash
docker build -t job-api .
docker run \
  -e REPO_BACKEND=mongo \
  -e MONGO_URL='mongodb://mongo:27017' \
  -p 8080:8080 job-api
```
```
