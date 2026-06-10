# Cisco EOX Manager Frontend

The frontend is a React/Vite GUI for local setup, PID lookup, Auto_Pop job control, GraphQL database browsing, exports, and operational visibility.

## Start in dev mode

```bash
cd Cisco_EOX_Manager/front_end
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The frontend expects the backend at:

```text
http://127.0.0.1:8000
```

Set a different backend URL:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## GUI sections

| Section | Purpose |
|---|---|
| Database overview | Shows DB totals from GraphQL. |
| Setup | One-click SQLite for new users, or PostgreSQL/advanced URL for larger deployments. Cisco API setup is optional and hidden behind an advanced card. |
| Smart PID lookup | Add/remove PID chips and search. The backend chooses DB/API/scraper automatically. |
| Auto_Pop jobs | Start/cancel/monitor controlled background crawls. |
| Database browser | Browse DB data through GraphQL queries. |
| Export | Download CSV/Excel from DB datasets with checkbox-based column selection. |
| Raw Cisco table viewer | View every saved table, row, and affected-product mapping for a PID. |

## Authentication behavior

The frontend does not ask for login or admin tokens by default. The tool is intended for local/internal use. If authentication is required later, enable it on the backend and place the app behind a proper enterprise auth layer.

## Logging

The frontend captures window errors and unhandled promise rejections, then posts them to:

```text
POST /api/logs/frontend
```

Those events are visible through GraphQL `systemEvents`.


## Beginner flow

The frontend avoids asking users whether to use Cisco API or scraping. Users add PID chips, click the search button, and the backend chooses the best available source automatically. The raw Cisco table viewer uses GraphQL to retrieve every table and affected-product row saved in the database.

## Report builder

The report section is designed for common users, not only programmers. The default dataset is `eox_report`. Users select Excel or CSV, choose recommended/core/all columns, or tick individual fields. Dynamic Cisco table columns appear after Auto_Pop or smart lookup stores those columns in the database.

The frontend does not offer JSON file download. Developers can use GraphQL when JSON-shaped data is needed.
