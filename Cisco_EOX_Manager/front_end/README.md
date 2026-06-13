# Cisco EOX Manager Frontend

React/Vite GUI for Cisco EOX Manager.

## Run in Docker

```bash
cd Cisco_EOX_Manager
docker compose up --build
```

Open:

```text
http://127.0.0.1:5173
```

## Backend URL

The frontend auto-detects the backend as:

```text
http://same-host-as-browser:8000
```

Keep this empty for remote server use:

```yaml
VITE_API_BASE_URL: ""
```

Set an explicit backend only when needed:

```env
VITE_API_BASE_URL=http://SERVER-IP:8000
```

## GUI sections

```text
Guide                  explains the tiles/buttons/options
Pick a database         SQLite or PostgreSQL setup
Local DB snapshot       DB counts from REST
Search Cisco EOX        smart PID lookup
Auto_Pop                controlled DB population
Cisco API setup         optional, not required
Cisco table viewer      raw evidence through REST
Database browser        GraphQL-based developer view
Reports                 CSV/XLSX exports with checkboxes
```

The normal user flow uses REST and does not require GraphQL. The GraphQL button remains available for developer testing.
