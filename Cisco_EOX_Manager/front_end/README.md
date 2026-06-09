# Cisco EOX Manager Frontend

React/Vite frontend for Cisco EOX Manager.

## Run in development

```bash
cd Cisco_EOX_Manager/front_end
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies `/api`, `/health`, and `/graphql` to the FastAPI backend.

## Setup wizard

The GUI includes:

- Database setup/test/initialize.
- Bundled preset import.
- Cisco API key/token setup.
- PID catalog browser.
- EOX cache browser.
- Cache-first EOX lookup.
- Controlled PID auto-populate workflow.
