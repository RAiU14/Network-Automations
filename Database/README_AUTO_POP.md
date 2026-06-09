# Auto_Pop update

The maintained Auto_Pop workflow has moved to the standalone product folder:

```text
Cisco_EOX_Manager/tools/auto_pop_pid_database.py
```

The old files below are now compatibility wrappers:

```text
Database/auto_pop.py
Database/auto_pop_enhanced.py
```

Run from the repository root:

```bash
python Database/auto_pop.py --output Cisco_EOX_Manager/data/presets/eox_pid_seed.json
```

Small test run:

```bash
python Database/auto_pop.py --limit-categories 2
```

Full EOX crawl:

```bash
python Database/auto_pop.py --crawl-eox
```

After the preset JSON is generated, start Cisco EOX Manager and click **Import bundled preset** in the GUI.
