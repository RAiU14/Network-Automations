import { useEffect, useMemo, useState } from 'react';
import { apiRequest, downloadJson, parsePids } from './api.js';

const samplePids = 'AIR-CT5520-K9\nAIR-CT5508-25-K9\nC9300-24T';

function StatusPill({ ok, text }) {
  return <span className={`pill ${ok ? 'ok' : 'warn'}`}>{text}</span>;
}

function ResultPanel({ result, error, loading, onClear }) {
  return (
    <section className="panel output-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Output</p>
          <h2>Response</h2>
        </div>
        <div className="button-row">
          <button className="secondary" type="button" onClick={onClear} disabled={!result && !error}>Clear</button>
          <button className="secondary" type="button" onClick={() => downloadJson('eox-result.json', result)} disabled={!result}>Download JSON</button>
        </div>
      </div>
      {loading && <div className="notice">Working...</div>}
      {error && <div className="notice error">{error}</div>}
      {!loading && !error && !result && <div className="empty">Run setup, import a preset, lookup a PID, or browse the database to see output here.</div>}
      {result && <pre className="json-output">{JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}

function SetupWizard({ status, refreshStatus, refreshStats, setResult, setError, setLoading }) {
  return (
    <section className="panel setup-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">First run</p>
          <h2>Setup wizard</h2>
          <p className="muted">For Docker users, the default PostgreSQL database is already wired. Use this page to initialize tables, import the bundled PID preset, and save Cisco API keys.</p>
        </div>
        <button className="secondary" type="button" onClick={refreshStatus}>Refresh</button>
      </div>

      <div className="status-grid setup-status-grid">
        <div>
          <span className="label">Database</span>
          <StatusPill ok={Boolean(status?.database_ready)} text={status?.database_ready ? 'Ready' : 'Not ready'} />
          <p className="hint mono">{status?.database_url_hint || 'Not configured'}</p>
        </div>
        <div>
          <span className="label">Cisco API</span>
          <StatusPill ok={Boolean(status?.cisco_credentials_configured)} text={status?.cisco_credentials_configured ? 'Configured' : 'Optional'} />
          <p className="hint">Keys are saved encrypted in PostgreSQL.</p>
        </div>
        <div>
          <span className="label">Bundled preset</span>
          <StatusPill ok={Boolean(status?.preset_available)} text={status?.preset_available ? 'Available' : 'Waiting for file'} />
          <p className="hint mono">{status?.preset_path || 'data/presets/eox_pid_seed.json'}</p>
        </div>
      </div>

      {status?.database_error && <div className="notice error small">{status.database_error}</div>}

      <div className="grid three-columns nested-grid">
        <DatabaseSetupCard refreshStatus={refreshStatus} refreshStats={refreshStats} setResult={setResult} setError={setError} setLoading={setLoading} />
        <PresetSetupCard refreshStatus={refreshStatus} refreshStats={refreshStats} setResult={setResult} setError={setError} setLoading={setLoading} />
        <CiscoSetupCard status={status} refreshStatus={refreshStatus} setResult={setResult} setError={setError} setLoading={setLoading} />
      </div>
    </section>
  );
}

function DatabaseSetupCard({ refreshStatus, refreshStats, setResult, setError, setLoading }) {
  const [mode, setMode] = useState('simple');
  const [host, setHost] = useState('db');
  const [port, setPort] = useState(5432);
  const [database, setDatabase] = useState('eox_cache');
  const [username, setUsername] = useState('eox_user');
  const [password, setPassword] = useState('eox_password');
  const [databaseUrl, setDatabaseUrl] = useState('');
  const [writeEnvFile, setWriteEnvFile] = useState(true);

  async function submit(testOnly = false) {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const payload = mode === 'url'
        ? { database_url: databaseUrl, initialize_after_save: !testOnly, write_env_file: writeEnvFile, test_only: testOnly }
        : { host, port: Number(port), database, username, password, initialize_after_save: !testOnly, write_env_file: writeEnvFile, test_only: testOnly };
      const data = await apiRequest('/api/setup/database/configure', { method: 'POST', body: JSON.stringify(payload) });
      setResult(data);
      await refreshStatus();
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function initializeOnly() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await apiRequest('/api/setup/database/initialize', { method: 'POST' });
      setResult(data);
      await refreshStatus();
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="sub-card">
      <h3>1. Database setup</h3>
      <p className="muted">Use the default Docker values, or point the app to an external PostgreSQL database.</p>
      <div className="segmented">
        <button className={mode === 'simple' ? '' : 'secondary'} type="button" onClick={() => setMode('simple')}>Simple</button>
        <button className={mode === 'url' ? '' : 'secondary'} type="button" onClick={() => setMode('url')}>URL</button>
      </div>
      {mode === 'simple' ? (
        <div className="form-grid compact">
          <label>Host<input value={host} onChange={(event) => setHost(event.target.value)} /></label>
          <label>Port<input type="number" value={port} onChange={(event) => setPort(event.target.value)} /></label>
          <label>Database<input value={database} onChange={(event) => setDatabase(event.target.value)} /></label>
          <label>User<input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        </div>
      ) : (
        <label>Database URL<input value={databaseUrl} onChange={(event) => setDatabaseUrl(event.target.value)} placeholder="postgresql+psycopg://user:pass@host:5432/eox_cache" /></label>
      )}
      <label className="checkbox-row">
        <input type="checkbox" checked={writeEnvFile} onChange={(event) => setWriteEnvFile(event.target.checked)} />
        Also write data/.env.local for local reference
      </label>
      <div className="button-row">
        <button type="button" onClick={() => submit(true)}>Test DB</button>
        <button type="button" onClick={() => submit(false)}>Save and initialize</button>
        <button className="secondary" type="button" onClick={initializeOnly}>Initialize current DB</button>
      </div>
    </div>
  );
}

function PresetSetupCard({ refreshStatus, refreshStats, setResult, setError, setLoading }) {
  const [overwrite, setOverwrite] = useState(false);
  const [discoverLimit, setDiscoverLimit] = useState(2);
  const [crawlModels, setCrawlModels] = useState(false);
  const [seriesLimit, setSeriesLimit] = useState(20);

  async function importPreset() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await apiRequest('/api/eox/import-preset', { method: 'POST', body: JSON.stringify({ overwrite }) });
      setResult(data);
      await refreshStatus();
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function discoverCatalog() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await apiRequest('/api/eox/discover-catalog', {
        method: 'POST',
        body: JSON.stringify({
          limit_categories: Number(discoverLimit),
          include_eox_links: true,
          save_to_database: true,
          crawl_models: crawlModels,
          limit_series: crawlModels ? Number(seriesLimit) : null
        })
      });
      setResult(data);
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="sub-card">
      <h3>2. PID preset</h3>
      <p className="muted">Import data/presets/eox_pid_seed.json. Replace that file with the Auto_Pop output when you generate the full preset.</p>
      <label className="checkbox-row">
        <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
        Overwrite existing rows
      </label>
      <div className="button-row">
        <button type="button" onClick={importPreset}>Import bundled preset</button>
      </div>
      <hr />
      <p className="muted">Optional online discovery. Keep the limit small during testing. Model crawling opens each series page and adds entries from Cisco's Select Model list.</p>
      <label>Category limit<input type="number" min="1" max="100" value={discoverLimit} onChange={(event) => setDiscoverLimit(event.target.value)} /></label>
      <label className="checkbox-row">
        <input type="checkbox" checked={crawlModels} onChange={(event) => setCrawlModels(event.target.checked)} />
        Also crawl model names from series pages
      </label>
      {crawlModels && <label>Series page limit<input type="number" min="1" max="10000" value={seriesLimit} onChange={(event) => setSeriesLimit(event.target.value)} /></label>}
      <button type="button" onClick={discoverCatalog}>Discover PID catalog online</button>
    </div>
  );
}

function CiscoSetupCard({ status, refreshStatus, setResult, setError, setLoading }) {
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [testConnection, setTestConnection] = useState(false);

  async function saveCiscoSetup(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const payload = {
        client_id: clientId || null,
        client_secret: clientSecret || null,
        access_token: accessToken || null,
        test_connection: testConnection
      };
      const data = await apiRequest('/api/setup/cisco', { method: 'POST', body: JSON.stringify(payload) });
      setResult(data);
      setClientSecret('');
      setAccessToken('');
      await refreshStatus();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="sub-card">
      <h3>3. Cisco API keys</h3>
      <p className="muted">Optional. If skipped, the app still uses the local database first and scraper fallback for misses.</p>
      <form className="form-grid compact" onSubmit={saveCiscoSetup}>
        <label>Cisco client ID<input value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder={status?.client_id_hint || 'Client ID'} /></label>
        <label>Cisco client secret<input type="password" value={clientSecret} onChange={(event) => setClientSecret(event.target.value)} placeholder="Client secret" /></label>
        <label>Existing access token<input type="password" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} placeholder="Optional token" /></label>
        <label className="checkbox-row">
          <input type="checkbox" checked={testConnection} onChange={(event) => setTestConnection(event.target.checked)} />
          Test token request after saving
        </label>
        <button type="submit">Save API setup</button>
      </form>
    </div>
  );
}

function LookupPanel({ setResult, setError, setLoading, refreshStats }) {
  const [pids, setPids] = useState(samplePids);
  const [technology, setTechnology] = useState('Routing and Switching');
  const [refresh, setRefresh] = useState(false);
  const [preferApi, setPreferApi] = useState(false);
  const [autoLearn, setAutoLearn] = useState(true);
  const parsedPids = useMemo(() => parsePids(pids), [pids]);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    if (!parsedPids.length) {
      setError('Enter at least one Cisco PID.');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest('/api/eox/lookup', {
        method: 'POST',
        body: JSON.stringify({ pids: parsedPids, technology, refresh, prefer_api: preferApi, auto_learn: autoLearn })
      });
      setResult(data);
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Cache first</p>
      <h2>EOX lookup</h2>
      <p className="muted">Searches PostgreSQL first. Missing PIDs can be learned from Cisco API or scraper and then cached.</p>
      <form className="form-grid" onSubmit={submit}>
        <label>Product IDs / models<textarea rows="8" value={pids} onChange={(event) => setPids(event.target.value)} /></label>
        <label>Technology<input value={technology} onChange={(event) => setTechnology(event.target.value)} /></label>
        <label className="checkbox-row"><input type="checkbox" checked={preferApi} onChange={(event) => setPreferApi(event.target.checked)} />Prefer Cisco API for cache misses</label>
        <label className="checkbox-row"><input type="checkbox" checked={autoLearn} onChange={(event) => setAutoLearn(event.target.checked)} />Auto-learn and save missing results</label>
        <label className="checkbox-row"><input type="checkbox" checked={refresh} onChange={(event) => setRefresh(event.target.checked)} />Refresh even if cached</label>
        <div className="button-row"><button type="submit">Lookup EOX</button><span className="hint">{parsedPids.length} PID{parsedPids.length === 1 ? '' : 's'} detected</span></div>
      </form>
    </section>
  );
}

function AutoPopulatePanel({ setResult, setError, setLoading, refreshStats }) {
  const [pids, setPids] = useState(samplePids);
  const [technology, setTechnology] = useState('Routing and Switching');
  const [refreshExisting, setRefreshExisting] = useState(false);
  const [preferApi, setPreferApi] = useState(false);
  const parsedPids = useMemo(() => parsePids(pids), [pids]);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    if (!parsedPids.length) {
      setError('Enter at least one Cisco PID to populate.');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest('/api/eox/auto-populate', {
        method: 'POST',
        body: JSON.stringify({ pids: parsedPids, technology, refresh_existing: refreshExisting, prefer_api: preferApi })
      });
      setResult(data);
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Learning mode</p>
      <h2>Populate known PIDs</h2>
      <p className="muted">Paste a controlled list of PIDs. The app checks local data first, then learns missing rows and stores them.</p>
      <form className="form-grid" onSubmit={submit}>
        <label>Product IDs / models<textarea rows="8" value={pids} onChange={(event) => setPids(event.target.value)} /></label>
        <label>Technology<input value={technology} onChange={(event) => setTechnology(event.target.value)} /></label>
        <label className="checkbox-row"><input type="checkbox" checked={preferApi} onChange={(event) => setPreferApi(event.target.checked)} />Prefer Cisco API before scraping</label>
        <label className="checkbox-row"><input type="checkbox" checked={refreshExisting} onChange={(event) => setRefreshExisting(event.target.checked)} />Refresh existing cached entries</label>
        <div className="button-row"><button type="submit">Populate selected PIDs</button><span className="hint">{parsedPids.length} PID{parsedPids.length === 1 ? '' : 's'} detected</span></div>
      </form>
    </section>
  );
}

function StatsPanel({ stats, refreshStats }) {
  return (
    <section className="panel stats-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">PostgreSQL</p>
          <h2>Database stats</h2>
        </div>
        <button className="secondary" type="button" onClick={refreshStats}>Refresh</button>
      </div>
      <div className="metric-grid">
        <div className="metric"><span>EOX records</span><strong>{stats?.total_products ?? 0}</strong></div>
        <div className="metric"><span>PID catalog</span><strong>{stats?.total_pid_catalog ?? 0}</strong></div>
        <div className="metric"><span>Recent lookups</span><strong>{stats?.recent_lookups ?? 0}</strong></div>
      </div>
      <div className="mini-columns">
        <div><h3>EOX status</h3><pre>{JSON.stringify(stats?.by_status || {}, null, 2)}</pre></div>
        <div><h3>EOX source</h3><pre>{JSON.stringify(stats?.by_source || {}, null, 2)}</pre></div>
        <div><h3>Catalog source</h3><pre>{JSON.stringify(stats?.by_catalog_source || {}, null, 2)}</pre></div>
      </div>
    </section>
  );
}

function DataBrowser({ setResult, setError, setLoading }) {
  const [tab, setTab] = useState('catalog');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState(null);

  async function search(event) {
    event?.preventDefault();
    setLoading(true);
    setError('');
    try {
      const endpoint = tab === 'catalog' ? '/api/eox/pid-catalog' : '/api/eox/cache';
      const suffix = query ? `?q=${encodeURIComponent(query)}` : '';
      const data = await apiRequest(`${endpoint}${suffix}`);
      setItems(data);
      setResult(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel wide-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Local database</p>
          <h2>Browse PID catalog and EOX cache</h2>
        </div>
        <div className="segmented">
          <button className={tab === 'catalog' ? '' : 'secondary'} type="button" onClick={() => { setTab('catalog'); setItems(null); }}>PID catalog</button>
          <button className={tab === 'eox' ? '' : 'secondary'} type="button" onClick={() => { setTab('eox'); setItems(null); }}>EOX cache</button>
        </div>
      </div>
      <form className="search-row" onSubmit={search}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={tab === 'catalog' ? 'Search PID, series, technology, category' : 'Search PID, technology, status'} />
        <button type="submit">Search</button>
      </form>
      {tab === 'catalog' ? <CatalogTable items={items?.items || []} /> : <EoxTable items={items?.items || []} />}
    </section>
  );
}

function CatalogTable({ items }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>PID / series</th><th>Technology</th><th>Category</th><th>EOX?</th><th>Source</th></tr></thead>
        <tbody>
          {items.map((item) => <tr key={`${item.normalized_pid}-${item.technology}`}><td>{item.pid}</td><td>{item.technology || '-'}</td><td>{item.category_name || '-'}</td><td>{item.is_eox ? 'Yes' : 'No'}</td><td>{item.source}</td></tr>)}
          {!items.length && <tr><td colSpan="5" className="empty-cell">No PID catalog rows loaded yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function EoxTable({ items }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>PID</th><th>Status</th><th>Source</th><th>End-of-sale</th><th>Last support</th></tr></thead>
        <tbody>
          {items.map((item) => <tr key={item.normalized_pid}><td>{item.pid}</td><td>{item.status}</td><td>{item.source}</td><td>{item.end_of_sale_date || '-'}</td><td>{item.last_date_of_support || '-'}</td></tr>)}
          {!items.length && <tr><td colSpan="5" className="empty-cell">No EOX cache rows loaded yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function refreshStatus() {
    try {
      const data = await apiRequest('/api/setup/status');
      setStatus(data);
    } catch (error) {
      setStatus({ database_ready: false, cisco_credentials_configured: false, database_error: error.message });
    }
  }

  async function refreshStats() {
    try {
      const data = await apiRequest('/api/eox/stats');
      setStats(data);
    } catch (error) {
      setStats(null);
    }
  }

  useEffect(() => {
    refreshStatus();
    refreshStats();
  }, []);

  return (
    <main>
      <header className="hero">
        <div>
          <p className="eyebrow">Standalone product</p>
          <h1>Cisco EOX Manager</h1>
          <p>Local PostgreSQL PID database first, bundled preset import, Cisco API setup from the GUI, scraper fallback, auto-learning, and GraphQL-ready access.</p>
        </div>
        <div className="hero-actions"><a href="/docs" target="_blank" rel="noreferrer">Open API docs</a><a href="/graphql" target="_blank" rel="noreferrer">Open GraphQL</a></div>
      </header>

      <SetupWizard status={status} refreshStatus={refreshStatus} refreshStats={refreshStats} setResult={setResult} setError={setError} setLoading={setLoading} />

      <section className="grid two-columns">
        <StatsPanel stats={stats} refreshStats={refreshStats} />
        <LookupPanel setResult={setResult} setError={setError} setLoading={setLoading} refreshStats={refreshStats} />
      </section>

      <section className="grid two-columns">
        <AutoPopulatePanel setResult={setResult} setError={setError} setLoading={setLoading} refreshStats={refreshStats} />
        <section className="panel">
          <p className="eyebrow">Auto_Pop workflow</p>
          <h2>Preset generation</h2>
          <p className="muted">Run the fixed Auto_Pop utility locally to create a full seed file, then place it here:</p>
          <pre className="code-block">Cisco_EOX_Manager/data/presets/eox_pid_seed.json</pre>
          <pre className="code-block">python tools/auto_pop_pid_database.py --output data/presets/eox_pid_seed.json</pre>
          <p className="muted">After replacing the file, use the setup wizard button: Import bundled preset.</p>
        </section>
      </section>

      <DataBrowser setResult={setResult} setError={setError} setLoading={setLoading} />

      <ResultPanel result={result} error={error} loading={loading} onClear={() => { setResult(null); setError(''); }} />
    </main>
  );
}
