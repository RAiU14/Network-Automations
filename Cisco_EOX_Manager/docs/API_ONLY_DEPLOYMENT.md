# API-Only Deployment Guide

The React frontend is optional. The reusable product is the FastAPI backend.

## When to use API-only mode

Use API-only mode when:

```text
you already have another application or dashboard
you want to call Cisco EOX Manager from scripts
you want to save CPU/RAM by not running React/Vite
you want this tool to behave like a small internal lifecycle API
```

## Architecture

```text
Your app or script
   ↓ HTTP REST/GraphQL
Cisco EOX Manager API
   ↓ SQLAlchemy
SQLite or PostgreSQL
```

## Run API with PostgreSQL

```bash
docker compose up -d postgres api
```

Open API docs:

```text
http://SERVER-IP:8000/docs
```

## Run API with SQLite only

```bash
docker compose up -d api
```

SQLite database path on the host:

```text
Cisco_EOX_Manager/data/eox_dev.db
```

## Common REST calls

Health:

```bash
curl http://SERVER-IP:8000/health
```

Stats:

```bash
curl http://SERVER-IP:8000/api/eox/stats
```

Lookup:

```bash
curl -s -X POST http://SERVER-IP:8000/api/eox/lookup \
  -H "Content-Type: application/json" \
  -d '{"pids":["AIR-CT5520-K9"],"refresh":false,"auto_learn":false}'
```

Evidence:

```bash
curl http://SERVER-IP:8000/api/eox/evidence/AIR-CT5520-K9
```

Start Auto_Pop job:

```bash
curl -s -X POST http://SERVER-IP:8000/api/autopop/jobs \
  -H "Content-Type: application/json" \
  -d '{"limit_categories":1,"limit_series_eox":25,"limit_announcements":5,"parse_workers":2,"delay":5,"category_break":60,"allow_empty":true}'
```

## Python integration example

```python
import requests

base_url = "http://EOX-SERVER:8000"
token = "YOUR_TOKEN_IF_ENABLED"

headers = {"Content-Type": "application/json"}
if token:
    headers["Authorization"] = f"Bearer {token}"

response = requests.post(
    f"{base_url}/api/eox/lookup",
    headers=headers,
    json={"pids": ["AIR-CT5520-K9"], "refresh": False, "auto_learn": False},
    timeout=30,
)
response.raise_for_status()
print(response.json())
```

## Security recommendation

For API-only mode, enable token protection if anything other than your own local machine can reach the service.

```text
Enable token auth
Keep rate limiting enabled
Restrict CORS if you use a browser frontend
Use HTTPS through a reverse proxy for non-local access
Do not expose PostgreSQL directly to the internet
```

## v18 API-only and worker deployment

Run backend without frontend:

```bash
docker compose -f docker-compose.yml -f docker-compose.api-only.yml up -d --build
```

Run backend plus dedicated Auto_Pop worker:

```bash
EOX_AUTOPOP_EXECUTION_MODE=external docker compose -f docker-compose.yml -f docker-compose.api-only.yml --profile worker up -d --build
```

In worker mode, the API only queues Auto_Pop jobs. The worker container processes queued jobs from the database. This is the recommended mode when several people or scripts will use the API while long Auto_Pop jobs are running.

Useful API endpoints:

```text
GET  /api/system/capabilities
GET  /api/system/database-health
GET  /api/autopop/jobs/{id}/log
POST /api/autopop/jobs/{id}/pause
POST /api/autopop/jobs/{id}/resume
POST /api/autopop/jobs/{id}/cancel
POST /api/system/backups
GET  /api/system/backups
```

Read-only integrations should use a read token. Admin automation should use an admin token.
