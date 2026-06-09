# Cisco EOX Manager Backend

FastAPI backend for the standalone Cisco EOX Manager product.

## Run manually

```bash
cd Cisco_EOX_Manager/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Set PostgreSQL with either `EOX_DATABASE_URL` or through the GUI database setup endpoint.

## Important endpoints

- `GET /api/setup/status`
- `POST /api/setup/database/configure`
- `POST /api/setup/database/initialize`
- `POST /api/setup/cisco`
- `GET /api/eox/preset`
- `POST /api/eox/import-preset`
- `GET /api/eox/pid-catalog`
- `GET /api/eox/cache`
- `POST /api/eox/lookup`
- `POST /api/eox/auto-populate`
- `POST /api/eox/discover-catalog`
- `GET /graphql`
