# Architecture

## Components

- `app/main.py`
  - Bootstraps FastAPI app and mounts static UI.
- `app/routes/diagnose.py`
  - Primary inference endpoint (`POST /api/diagnose`).
- `app/routes/health.py`
  - Liveness endpoint (`GET /health`).
- `app/routes/metrics.py`
  - Prometheus metrics endpoint (`GET /metrics`).
- `app/services/`
  - Request validation, retrieval, scoring, and response construction.
- `app/database.py`
  - SQLAlchemy engine/session setup and migration bootstrap.
- `app/static/`
  - Browser-based intake UI.

## Request Flow

1. User submits VIN, OBD code(s), and symptoms from UI or API client.
2. Request is validated and normalized.
3. Retrieval stage fetches relevant diagnostic context.
4. Scoring/ranking stage produces likely causes and confidence ordering.
5. Response builder returns structured diagnostic output and metadata.
6. Session is persisted for traceability and follow-up analysis.

## Deployment Topology

- Compute: Azure App Service hosting FastAPI process.
- Configuration: environment variables through Azure App Settings.
- Data: SQL database via `DATABASE_URL`.
- Monitoring: `/health` for uptime probes, `/metrics` for scrape-based dashboards/alerts.

## Reliability Notes

- Input validation guards malformed VIN/OBD/symptom payloads.
- App-specific exception handling in route and service layers.
- Rate limiting and defensive error mapping reduce noisy failures.
