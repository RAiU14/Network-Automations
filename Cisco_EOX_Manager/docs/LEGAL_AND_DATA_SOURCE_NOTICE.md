# Legal and Data-Source Notice

Cisco EOX Manager is an independent home-lab and internal-operations tool. It is not affiliated with, endorsed by, sponsored by, or supported by Cisco.

This document is not legal advice. If you plan to use this tool commercially, expose it publicly, or redistribute generated datasets, get legal review from someone qualified in your jurisdiction.

## Project intent

The project is intended for:

```text
internal lifecycle planning
home-lab learning
inventory lookups
local cache generation
API integration for your own tools
```

It is not intended to be marketed as:

```text
an official Cisco product
an official Cisco data source
a Cisco data mirror
a replacement for Cisco Support
an unlimited Cisco scraper
```

## Data-source posture

Recommended source order:

```text
1. Local cache in SQLite/PostgreSQL
2. Cisco official Support EoX API when credentials are configured
3. Optional rate-limited public-page fallback for internal/local cache generation
```

Do not bundle a generated Cisco EOX database in the public repository. Let users generate their own local cache.

## Public release guidance

Safer to publish:

```text
source code
Docker setup
API examples
mock/example rows
screenshots without vendor logos
README documentation
```

Higher risk without review:

```text
large generated vendor datasets
bulk copied pages
vendor logos
claims of official endorsement
language implying the tool is a vendor replacement
```

## Trademark and naming guidance

Use vendor and product names only descriptively. Do not use Cisco logos, Cisco trade dress, or branding in a way that implies sponsorship or endorsement.

Prefer wording like:

```text
Independent home-lab/internal inventory tool for Cisco EoX lifecycle lookups.
Users generate their own local cache. Not affiliated with Cisco. Use official APIs where available.
```

Avoid wording like:

```text
Official Cisco EOX database
Cisco data mirror
Cisco replacement API
Unlimited Cisco scraper
```

## Responsible collection guidance

When using public-page fallback:

```text
keep delay and cooldown enabled
avoid high parallel request counts
identify generated data with source URLs and collection timestamps
cache locally instead of repeatedly refetching the same pages
validate important dates with Cisco or an authorized support channel
stop collection if the site blocks or rejects requests
```

## Suggested repository disclaimer

```text
This project is an independent tool and is not affiliated with, endorsed by, sponsored by, or supported by Cisco. Cisco product names are used only descriptively. This repository does not include a Cisco EOX dataset; users generate their own local cache for internal inventory and lifecycle planning. Users are responsible for complying with vendor terms, API terms, website terms, robots.txt, rate limits, and applicable laws. Prefer Cisco official Support APIs where available.
```

## Data sharing recommendation

Do not publish a generated Cisco EoX database as part of this repository or as a public dataset unless you have reviewed the applicable vendor/API/site terms and have a clear right to redistribute that data.

The safer public model is:

```text
publish code
publish examples using mock rows
let each user generate their own local cache
prefer official Cisco Support EoX API credentials where available
keep public-page fallback optional, rate-limited, and local/internal
```
