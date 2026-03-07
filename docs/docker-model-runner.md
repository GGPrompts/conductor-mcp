# Docker Model Runner

Run AI models locally via Docker Desktop with GPU support.

## Setup

### Prerequisites

1. **Docker Desktop** with Model Runner feature
2. **NVIDIA GPU** (optional but recommended)
3. **Enable settings** in Docker Desktop:
   - Settings → AI → Enable Docker Model Runner
   - Settings → AI → Enable localhost TCP support (required for API access)

### Verify GPU Access

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

## Commands

### Discovery

```bash
# List available models (pulled locally)
docker model list

# Check runner status
docker model status

# View model details
docker model inspect <model-name>
```

### Install Backends

Docker Model Runner supports multiple inference backends:

```bash
# Install llama.cpp (CPU, default)
docker model install-runner

# Install vLLM with CUDA (GPU, required for some models)
docker model install-runner --backend vllm --gpu cuda

# Start/restart runner
docker model start-runner
docker model restart-runner

# Check status
docker model status
```

### Pull Models

Browse models in Docker Desktop UI or pull via CLI:

```bash
# Pull from Docker Hub model catalog
docker model pull <model-name>

# Examples
docker model pull ai/llama3.2
docker model pull ai/qwen2.5-coder
docker model pull qwen3-embedding-vllm
```

### Run Models

```bash
# Interactive chat
docker model run <model-name>

# Single prompt
docker model run <model-name> "Your prompt here"

# Detached (API server mode)
docker model run -d <model-name>
```

## API Access

With localhost TCP support enabled, models expose an OpenAI-compatible API.

**Default port**: `12434`

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `http://localhost:12434/v1/chat/completions` | Chat completions |
| `http://localhost:12434/v1/embeddings` | Text embeddings |
| `http://localhost:12434/api/tags` | List loaded models (Ollama-compatible) |

### Test Embeddings

```bash
curl http://localhost:12434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-embedding-vllm",
    "input": "Your text to embed here"
  }'
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.023, -0.041, 0.087, ...],
      "index": 0
    }
  ],
  "model": "qwen3-embedding-vllm",
  "usage": {"prompt_tokens": 5, "total_tokens": 5}
}
```

### Test Chat

```bash
curl http://localhost:12434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ai/llama3.2",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Python Integration

### Using requests

```python
import requests

def get_embedding(text: str, model: str = "qwen3-embedding-vllm") -> list[float]:
    response = requests.post(
        "http://localhost:12434/v1/embeddings",
        json={"model": model, "input": text}
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]

# Usage
embedding = get_embedding("homeless veteran housing assistance")
print(f"Vector dimension: {len(embedding)}")
```

### Using OpenAI SDK (compatible)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:12434/v1",
    api_key="not-needed"  # Local models don't need auth
)

# Embeddings
response = client.embeddings.create(
    model="qwen3-embedding-vllm",
    input="Your text here"
)
embedding = response.data[0].embedding

# Chat
response = client.chat.completions.create(
    model="ai/llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

## Model Types

| Type | Purpose | Example Models |
|------|---------|----------------|
| **Chat/Instruct** | Conversation, code generation | ai/llama3.2, ai/qwen2.5-coder |
| **Embedding** | Text → vector for search | qwen3-embedding-vllm, nomic-embed-text |
| **Vision** | Image understanding | ai/llava |

## Troubleshooting

### "Docker Model Runner is not running"

```bash
# Start the runner
docker model start-runner

# Or install if first time
docker model install-runner
```

### Model needs vLLM backend

Some models (like `*-vllm`) require vLLM backend:

```bash
docker model install-runner --backend vllm --gpu cuda
```

### Can't connect to localhost:12434

1. Enable "localhost TCP support" in Docker Desktop → Settings → AI
2. Restart Docker Desktop if needed

### Check logs

```bash
docker model logs
```

## Resource Usage

- **CPU models**: ~8-16GB RAM depending on model size
- **GPU models**: VRAM usage ≈ model size (e.g., 8GB model needs ~8GB VRAM)
- **RTX 3070** (8GB VRAM): Can run most 7B models, some quantized larger models

## Useful Models for Development

| Model | Size | Use Case |
|-------|------|----------|
| `ai/smollm2:360M` | ~400MB | Fast testing, CI/CD |
| `ai/llama3.2` | ~4GB | General chat |
| `ai/qwen2.5-coder` | ~4GB | Code generation |
| `qwen3-embedding-vllm` | ~8GB | High-quality embeddings |
| `nomic-embed-text` | ~300MB | Fast embeddings |

## References

- [Docker Model Runner Docs](https://docs.docker.com/ai/model-runner/)
- [API Reference](https://docs.docker.com/ai/model-runner/api-reference/)
- [Configuration Options](https://docs.docker.com/ai/model-runner/configuration/)
