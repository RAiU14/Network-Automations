# Auto_Pop compatibility wrapper

The maintained Auto_Pop engine lives here:

```text
Cisco_EOX_Manager/tools/auto_pop_pid_database.py
```

The old files remain for convenience:

```text
Database/auto_pop.py
Database/auto_pop_enhanced.py
```

They simply forward arguments to the maintained Cisco EOX Manager tool.

Run from the repository root:

```bash
python Database/auto_pop.py --limit-categories 1 --limit-series-eox 10 --limit-announcements 2
```

SQLite dev run:

```bash
python Database/auto_pop.py --sqlite --limit-categories 1
```

The tool now saves directly to the configured database. It does not create or import JSON seed files.
