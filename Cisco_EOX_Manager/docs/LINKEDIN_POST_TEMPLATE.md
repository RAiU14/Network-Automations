# LinkedIn Post Template

Use careful wording. Do not use Cisco logos or imply endorsement.

## Draft

I have been working on a home-lab tool for Cisco EoX lifecycle lookups.

The idea is simple: many network teams keep spreadsheets or manual notes for end-of-sale and end-of-support planning. I wanted a small self-hosted service that can help build a local lifecycle cache and expose it through an API.

What it does:

- Runs as a FastAPI backend with an optional React dashboard
- Supports SQLite for local testing and PostgreSQL for larger datasets
- Provides REST and GraphQL-style access for other tools
- Supports CSV/XLSX exports for inventory planning
- Includes rate limiting and optional API token protection
- Lets users generate their own local cache instead of relying on a bundled dataset

The frontend is optional. The backend can run as a standalone API service, so other applications can query it directly.

This is an independent home-lab/internal-operations project. It is not affiliated with, endorsed by, or sponsored by Cisco. Cisco product names are used only descriptively. Users should follow applicable vendor terms and use official APIs where available.

I am building this mainly as a learning project around FastAPI, PostgreSQL, Docker, lifecycle data modeling, and network automation.

## Short GitHub description

Self-hosted Cisco EoX lifecycle cache manager and API for home labs and internal inventory planning. Built with FastAPI, SQLite/PostgreSQL, optional React UI, REST/GraphQL access, exports, token auth, and rate limiting. No vendor dataset is bundled; users generate their own local cache.
