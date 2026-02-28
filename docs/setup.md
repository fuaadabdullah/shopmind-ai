# Setup

## Prerequisites

- Python 3.11+
- `pip`
- Optional: Docker

## Environment Variables

| Variable | Required | Example | Purpose |
|---|---|---|---|
| `DEFAULT_PROVIDER` | Yes | `gcp` | Selects LLM provider (`gcp` or `siliconeflow`). |
| `GCP_MODEL_URL` | Required when `DEFAULT_PROVIDER=gcp` | `https://.../generate` | GCP model endpoint for generation. |
| `SILICONEFLOW_API_KEY` | Required when `DEFAULT_PROVIDER=siliconeflow` | `sk-...` | SiliconeFlow auth token. |
| `SILICONEFLOW_URL` | Required when `DEFAULT_PROVIDER=siliconeflow` | `https://api.siliconeflow.com/v1/chat` | SiliconeFlow API URL. |
| `DATABASE_URL` | Recommended | `sqlite:///./data/shopmind.db` | Persistence backend (SQLite/Postgres). |
| `ALLOWED_ORIGINS` | Recommended | `https://shopmind-ai.azurewebsites.net` | CORS policy. |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity. |
| `MAX_RETRIEVE_DOCS` | No | `10` | Retrieval count cap. |

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Smoke Checks

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/metrics | head -n 20
```

## Azure Deployment Runbook

1. Create App Service (Linux, Python runtime).
2. Deploy source from GitHub repo `fuaadabdullah/shopmind-ai`.
3. Set startup command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

4. Set required app settings (all secrets server-side only).
5. Verify:

```bash
curl -s https://shopmind-ai.azurewebsites.net/health
```

## Troubleshooting

- Provider errors: verify provider env vars and credentials.
- 500 on diagnose: confirm database connectivity and provider endpoint reachability.
- CORS issues: verify `ALLOWED_ORIGINS` includes frontend origin.
