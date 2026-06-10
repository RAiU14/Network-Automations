# Cisco EOX Manager Tests

Run from the product folder:

```bash
cd Cisco_EOX_Manager
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements-dev.txt
pytest -q
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Current coverage:

```text
PID normalization
Full Cisco EOX table parser
Announcement-table to PID mapping
Runtime DB config
Seed persistence
GraphQL schema shape
Admin token hashing and verification
Auto_Pop command construction
CSV export generation
```

Some tests skip automatically when optional dependencies are not installed in the execution environment.
