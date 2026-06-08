# Cisco EOX Front End

React user interface for the Cisco EOX FastAPI backend.

The UI supports:

- PID/model lookup through the scraper-compatible `/eox/lookup-pids` endpoint.
- Hardware EOX milestone lookup through the Cisco API-backed `/eox/hardware-milestones` endpoint.
- Software milestone lookup through `/eox/software-milestones`.
- Advanced direct actions for series-link discovery, product-page checks, EOX details extraction, and announcement scraping.

## Development mode

Run the FastAPI backend from the repository root:

```bash
python -m uvicorn EOX_API.main:app --reload
```

In another terminal, run the React app:

```bash
cd front_end
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite development server proxies `/eox`, `/api`, and `/health` requests to `http://127.0.0.1:8000`.

## Production/single-server mode

Build the React app:

```bash
cd front_end
npm install
npm run build
```

Then start FastAPI from the repository root:

```bash
python -m uvicorn EOX_API.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

FastAPI serves `front_end/dist/index.html` and the built assets when the `dist` directory exists.

## Optional API base URL

If the backend is not hosted on the same origin, create `front_end/.env.local`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not place credentials in the React app. Cisco API credentials must stay on the FastAPI backend only.
