import { useEffect, useMemo, useState } from 'react';
import { apiRequest, downloadExport, getExportOptions, graphqlRequest, logFrontendEvent, parsePids } from './api.js';

const samplePids = ['AIR-CT5520-K9', 'C9300-24T'];
const datasets = ['eox_report', 'products', 'affected_products', 'announcements', 'pid_catalog', 'checkpoints', 'system_events'];

const graphQueries = {
  overview: `query Overview { databaseOverview { totalProducts totalCatalogEntries totalAnnouncements totalAnnouncementTables totalAffectedProducts totalSeedRuns totalCheckpoints totalSystemEvents totalAutopopJobs totalExportJobs } }`,
  eox_report: `query Products($search: String, $limit: Int!) { products(search: $search, limit: $limit) { pid technology status productName series endOfSaleDate endOfSwMaintenance endOfSecuritySupport lastDateOfSupport eoxAnnouncementUrl updatedAt } }`,
  products: `query Products($search: String, $limit: Int!) { products(search: $search, limit: $limit) { pid normalizedPid technology status source productName series endOfSaleDate lastDateOfSupport eoxAnnouncementUrl updatedAt } }`,
  affected_products: `query Affected($search: String, $limit: Int!) { affectedProducts(search: $search, limit: $limit) { id pid normalizedPid technology productDescription announcementId productId tableIndex rowIndex source updatedAt payload rawResponse } }`,
  announcements: `query Announcements($search: String, $limit: Int!) { announcements(search: $search, limit: $limit) { id announcementName title technology series announcementUrl productBulletinUrl source updatedAt } }`,
  pid_catalog: `query Catalog($search: String, $limit: Int!) { pidCatalog(search: $search, limit: $limit) { pid normalizedPid technology categoryName productName productUrl isEox source updatedAt } }`,
  checkpoints: `query Checkpoints($limit: Int!) { autoPopCheckpoints(limit: $limit) { id scope scopeKey status lastStartedAt lastCompletedAt lastSuccessAt nextAllowedAt runCount skipCount catalogRecords eoxRecords announcementsSeen lastError updatedAt } }`,
  system_events: `query Events($limit: Int!) { systemEvents(limit: $limit) { id level eventType source message payload createdAt } }`,
  jobs: `query Jobs($limit: Int!) { autoPopJobs(limit: $limit) { id status processId returnCode logFile lastError createdAt startedAt finishedAt parameters stats } }`,
  productEvidence: `query ProductEvidence($pid: String!) { productEvidence(pid: $pid) { product { pid normalizedPid technology status source productName series endOfSaleDate lastDateOfSupport endOfSwMaintenance endOfSecuritySupport endOfRoutineFailureAnalysis eoxAnnouncementUrl productBulletinUrl updatedAt payload rawResponse } affectedProducts { id pid normalizedPid technology productDescription announcementId productId tableIndex rowIndex source updatedAt payload rawResponse } announcements { id announcementName title technology series announcementUrl productBulletinUrl source updatedAt } tables { id announcementId tableIndex heading caption headers rows rawTable updatedAt } } }`
};

function nvl(value) {
  if (value === null || value === undefined || value === '') return 'N/A';
  return value;
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return 'N/A';
  if (typeof value === 'object') return JSON.stringify(value).slice(0, 180);
  return String(value);
}

function StatusPill({ ok, text }) {
  return <span className={`pill ${ok ? 'ok' : 'warn'}`}>{text}</span>;
}

function useAppStatus() {
  const [setup, setSetup] = useState(null);
  const [stats, setStats] = useState(null);

  async function refreshSetup() {
    try {
      const data = await apiRequest('/api/setup/status');
      setSetup(data);
    } catch (error) {
      setSetup({ database_ready: false, database_error: error.message, cisco_credentials_configured: false });
    }
  }

  async function refreshStats() {
    try {
      const data = await graphqlRequest(graphQueries.overview);
      setStats(data?.data?.databaseOverview || null);
    } catch (_error) {
      setStats(null);
    }
  }

  return { setup, stats, refreshSetup, refreshStats };
}

function DatabaseSetupCard({ setup, refreshSetup, refreshStats, notify, setError, setLoading }) {
  const [databaseType, setDatabaseType] = useState('sqlite');
  const [host, setHost] = useState('postgres');
  const [port, setPort] = useState(5432);
  const [database, setDatabase] = useState('eox_cache');
  const [username, setUsername] = useState('eox_user');
  const [password, setPassword] = useState('eox_password');
  const [sqlitePath, setSqlitePath] = useState('eox_dev.db');
  const [databaseUrl, setDatabaseUrl] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  function payload(testOnly) {
    const base = { initialize_after_save: !testOnly, write_env_file: true, test_only: testOnly };
    if (databaseType === 'sqlite') return { ...base, database_type: 'sqlite', sqlite_path: sqlitePath || null };
    if (databaseType === 'url') return { ...base, database_type: 'url', database_url: databaseUrl };
    return { ...base, database_type: 'postgresql', host, port: Number(port), database, username, password };
  }

  async function configure(testOnly = false) {
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/api/setup/database/configure', { method: 'POST', body: JSON.stringify(payload(testOnly)) });
      notify(data.message || 'Database updated');
      await refreshSetup();
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function startWithSqlite() {
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/api/setup/database/use-sqlite', { method: 'POST', body: JSON.stringify({}) });
      notify(data.message || 'SQLite local database is ready');
      setDatabaseType('sqlite');
      await refreshSetup();
      await refreshStats();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel setup-card">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Step 1</p>
          <h2>Pick a database</h2>
          <p className="muted">New users can start with SQLite in one click. PostgreSQL is available when you want a larger shared setup.</p>
        </div>
        <StatusPill ok={Boolean(setup?.database_ready)} text={setup?.database_ready ? 'Ready' : 'Needs setup'} />
      </div>
      <div className="button-row starter-actions"><button type="button" onClick={startWithSqlite}>Start with local SQLite</button><span className="hint">No PostgreSQL required.</span></div>
      <div className="choice-grid">
        <button className={databaseType === 'sqlite' ? 'choice active' : 'choice'} type="button" onClick={() => setDatabaseType('sqlite')}>
          <strong>SQLite</strong><span>Best for first-time local testing</span>
        </button>
        <button className={databaseType === 'postgresql' ? 'choice active' : 'choice'} type="button" onClick={() => setDatabaseType('postgresql')}>
          <strong>PostgreSQL</strong><span>Best for Docker and scaling</span>
        </button>
        <button className={databaseType === 'url' ? 'choice active' : 'choice'} type="button" onClick={() => setDatabaseType('url')}>
          <strong>Advanced URL</strong><span>Use your own SQLAlchemy URL</span>
        </button>
      </div>
      <div className="form-grid compact">
        {databaseType === 'sqlite' && <label>SQLite file<input value={sqlitePath} onChange={(event) => setSqlitePath(event.target.value)} /></label>}
        {databaseType === 'postgresql' && (
          <div className="mini-columns">
            <label>Host<input value={host} onChange={(event) => setHost(event.target.value)} /></label>
            <label>Port<input type="number" value={port} onChange={(event) => setPort(event.target.value)} /></label>
            <label>Database<input value={database} onChange={(event) => setDatabase(event.target.value)} /></label>
            <label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
            <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          </div>
        )}
        {databaseType === 'url' && <label>Database URL<input value={databaseUrl} onChange={(event) => setDatabaseUrl(event.target.value)} placeholder="sqlite:///./data/eox_dev.db" /></label>}
        <div className="button-row">
          <button type="button" onClick={() => configure(false)}>Save and initialize</button>
          <button className="secondary" type="button" onClick={() => configure(true)}>Test only</button>
        </div>
      </div>
      <button className="text-button" type="button" onClick={() => setShowAdvanced(!showAdvanced)}>{showAdvanced ? 'Hide' : 'Show'} current database details</button>
      {showAdvanced && <pre className="code-block">{setup?.database_url_hint || 'No database configured yet'}</pre>}
      {setup?.database_error && <div className="notice error small">{setup.database_error}</div>}
    </section>
  );
}

function OptionalApiCard({ setup, refreshSetup, notify, setError, setLoading }) {
  const [open, setOpen] = useState(false);
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [accessToken, setAccessToken] = useState('');

  async function save(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = await apiRequest('/api/setup/cisco', { method: 'POST', body: JSON.stringify({ client_id: clientId || null, client_secret: clientSecret || null, access_token: accessToken || null, test_connection: false }) });
      notify(data.message || 'Cisco API values saved');
      setClientSecret('');
      setAccessToken('');
      await refreshSetup();
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel slim-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">Optional</p><h2>Cisco API setup</h2><p className="muted">Leave this empty for now. The lookup engine will use it automatically later only when credentials exist.</p></div>
        <StatusPill ok={Boolean(setup?.cisco_credentials_configured)} text={setup?.cisco_credentials_configured ? 'Saved' : 'Not needed'} />
      </div>
      <button className="secondary" type="button" onClick={() => setOpen(!open)}>{open ? 'Hide API setup' : 'Add API keys later'}</button>
      {open && (
        <form className="form-grid compact advanced-box" onSubmit={save}>
          <label>Client ID<input value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder={setup?.client_id_hint || 'Client ID'} /></label>
          <label>Client secret<input type="password" value={clientSecret} onChange={(event) => setClientSecret(event.target.value)} /></label>
          <label>Access token<input type="password" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} /></label>
          <button type="submit">Save API values</button>
        </form>
      )}
    </section>
  );
}

function PidManager({ pids, setPids }) {
  const [value, setValue] = useState('');
  const [paste, setPaste] = useState('');

  function add(items) {
    const parsed = Array.isArray(items) ? items : parsePids(items);
    if (!parsed.length) return;
    setPids((current) => Array.from(new Set([...current, ...parsed])));
    setValue('');
    setPaste('');
  }

  function remove(pid) {
    setPids((current) => current.filter((item) => item !== pid));
  }

  function keyDown(event) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      add(value);
    }
  }

  return (
    <div className="pid-manager">
      <div className="add-row">
        <input value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={keyDown} placeholder="Type PID, then Enter. Example: C9300-24T" />
        <button type="button" onClick={() => add(value)}>Add</button>
      </div>
      <textarea rows="3" value={paste} onChange={(event) => setPaste(event.target.value)} placeholder="Or paste multiple PIDs separated by comma, space, or new line" />
      <div className="button-row"><button className="secondary" type="button" onClick={() => add(paste)}>Add pasted PIDs</button><button className="secondary" type="button" onClick={() => setPids(samplePids)}>Use sample</button><button className="secondary" type="button" onClick={() => setPids([])}>Clear all</button></div>
      <div className="chips">
        {pids.map((pid) => <button className="chip" type="button" key={pid} onClick={() => remove(pid)}>{pid}<span>×</span></button>)}
        {!pids.length && <span className="hint">No PIDs added yet.</span>}
      </div>
    </div>
  );
}

function SearchPanel({ refreshStats, notify, setError, setLoading, setEvidencePid }) {
  const [pids, setPids] = useState(samplePids);
  const [results, setResults] = useState([]);
  const [refresh, setRefresh] = useState(false);

  async function lookup() {
    setError('');
    if (!pids.length) {
      setError('Add at least one Cisco PID.');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest('/api/eox/lookup', { method: 'POST', body: JSON.stringify({ pids, refresh, auto_learn: true }) });
      setResults(data.results || []);
      notify(`Lookup finished: ${data.summary?.total || 0} result(s)`);
      await refreshStats();
      if (data.results?.[0]?.pid) setEvidencePid(data.results[0].pid);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel wide-panel focus-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">Main workflow</p><h2>Search Cisco EOX by PID</h2><p className="muted">No method selection needed. The app checks DB first, uses Cisco API only if already configured, then falls back to web scraping and saves what it learns.</p></div>
        <StatusPill ok={true} text="Smart lookup" />
      </div>
      <PidManager pids={pids} setPids={setPids} />
      <div className="button-row main-actions">
        <button type="button" onClick={lookup}>Search and save missing data</button>
        <label className="checkbox-row"><input type="checkbox" checked={refresh} onChange={(event) => setRefresh(event.target.checked)} />Refresh existing DB rows</label>
      </div>
      <ResultCards results={results} onEvidence={setEvidencePid} />
    </section>
  );
}

function ResultCards({ results, onEvidence }) {
  if (!results?.length) return <div className="empty compact-empty">Search results will appear here.</div>;
  return (
    <div className="result-grid">
      {results.map((item) => {
        const product = item.product || {};
        return (
          <article className="result-card" key={item.pid}>
            <div className="card-top"><h3>{item.pid}</h3><StatusPill ok={Boolean(item.found)} text={item.status || 'unknown'} /></div>
            <div className="detail-list">
              <span>Source</span><strong>{nvl(item.source_used)}</strong>
              <span>Product</span><strong>{nvl(product.product_name || item.catalog_entry?.product_name)}</strong>
              <span>End of Sale</span><strong>{nvl(product.end_of_sale_date)}</strong>
              <span>Last Support</span><strong>{nvl(product.last_date_of_support)}</strong>
            </div>
            {item.message && <p className="hint">{item.message}</p>}
            <button className="secondary" type="button" onClick={() => onEvidence(item.pid)}>View raw Cisco tables</button>
          </article>
        );
      })}
    </div>
  );
}

function AutoPopPanel({ setup, refreshStats, notify, setError }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [options, setOptions] = useState({ limit_categories: 1, limit_series_eox: 10, limit_announcements: 2, parse_workers: 2, delay: 1, category_break: 10, force_refresh: false });

  async function refreshJobs() {
    try {
      const data = await graphqlRequest(graphQueries.jobs, { limit: 20 });
      setJobs(data?.data?.autoPopJobs || []);
    } catch (error) {
      setError(error.message);
    }
  }

  async function startJob(full = false) {
    setError('');
    if (!setup?.database_ready) {
      setError('Set up the database first. For easiest setup, click Start with local SQLite.');
      return;
    }
    const payload = full ? { parse_workers: 2, delay: 1, category_break: 15, force_refresh: false } : options;
    try {
      const data = await apiRequest('/api/autopop/jobs', { method: 'POST', body: JSON.stringify(payload) });
      notify(`Auto_Pop job #${data.id} started`);
      await refreshJobs();
      await refreshStats();
    } catch (error) {
      setError(error.message);
    }
  }

  async function cancelJob(id) {
    setError('');
    try {
      await apiRequest(`/api/autopop/jobs/${id}/cancel`, { method: 'POST' });
      notify(`Auto_Pop job #${id} cancel requested`);
      await refreshJobs();
    } catch (error) {
      setError(error.message);
    }
  }

  useEffect(() => { refreshJobs(); }, []);

  function setOption(key, value) {
    setOptions((current) => ({ ...current, [key]: value }));
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <div><p className="eyebrow">Build local DB</p><h2>Auto_Pop</h2><p className="muted">Uses the database you configured above. It stores results directly in DB, sleeps between categories, and skips recently refreshed categories.</p></div>
        <button className="secondary" type="button" onClick={refreshJobs}>Refresh</button>
      </div>
      <div className="button-row">
        <button type="button" disabled={!setup?.database_ready} onClick={() => startJob(false)}>Start safe Auto_Pop</button>
        <button className="secondary" type="button" onClick={() => setShowAdvanced(!showAdvanced)}>{showAdvanced ? 'Hide options' : 'Advanced options'}</button>
      </div>
      {showAdvanced && (
        <div className="advanced-box form-grid compact auto-grid">
          <label>Categories<input type="number" min="1" value={options.limit_categories} onChange={(event) => setOption('limit_categories', Number(event.target.value))} /></label>
          <label>Series per category<input type="number" min="1" value={options.limit_series_eox} onChange={(event) => setOption('limit_series_eox', Number(event.target.value))} /></label>
          <label>Announcements<input type="number" min="1" value={options.limit_announcements} onChange={(event) => setOption('limit_announcements', Number(event.target.value))} /></label>
          <label>Parser workers<input type="number" min="1" max="8" value={options.parse_workers} onChange={(event) => setOption('parse_workers', Number(event.target.value))} /></label>
          <label>Delay seconds<input type="number" min="0" step="0.5" value={options.delay} onChange={(event) => setOption('delay', Number(event.target.value))} /></label>
          <label>Category break<input type="number" min="0" value={options.category_break} onChange={(event) => setOption('category_break', Number(event.target.value))} /></label>
          <label className="checkbox-row"><input type="checkbox" checked={options.force_refresh} onChange={(event) => setOption('force_refresh', event.target.checked)} />Force refresh despite cooldown</label>
        </div>
      )}
      <SimpleTable rows={jobs} columns={['id', 'status', 'processId', 'returnCode', 'createdAt', 'startedAt', 'finishedAt', 'lastError']} actions={(row) => ['running', 'queued'].includes(row.status) ? <button className="secondary small-button" type="button" onClick={() => cancelJob(row.id)}>Cancel</button> : null} />
    </section>
  );
}

function EvidencePanel({ pid, setPid, setError }) {
  const [input, setInput] = useState(pid || '');
  const [evidence, setEvidence] = useState(null);
  const [activeTable, setActiveTable] = useState(0);

  useEffect(() => {
    if (pid) {
      setInput(pid);
      loadEvidence(pid);
    }
  }, [pid]);

  async function loadEvidence(target = input) {
    if (!target) return;
    setError('');
    try {
      const data = await graphqlRequest(graphQueries.productEvidence, { pid: target });
      setEvidence(data?.data?.productEvidence || null);
      setActiveTable(0);
    } catch (error) {
      setError(error.message);
    }
  }

  const product = evidence?.product || null;
  const tables = evidence?.tables || [];

  return (
    <section className="panel wide-panel evidence-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">Raw evidence</p><h2>Cisco table viewer</h2><p className="muted">Shows the exact scraped Cisco rows and every table saved for the announcement. Empty fields appear as N/A.</p></div>
        <a className="link-button secondary-link" href="/graphql" target="_blank" rel="noreferrer">GraphQL</a>
      </div>
      <form className="search-row" onSubmit={(event) => { event.preventDefault(); setPid(input); loadEvidence(input); }}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Enter PID to inspect raw tables" />
        <button type="submit">Load evidence</button>
      </form>
      {!evidence && <div className="empty compact-empty">Select a result or enter a PID to view raw Cisco evidence.</div>}
      {evidence && (
        <div className="evidence-grid">
          <div className="summary-card">
            <h3>{product?.pid || input}</h3>
            <div className="detail-list">
              <span>Status</span><strong>{nvl(product?.status)}</strong>
              <span>Product</span><strong>{nvl(product?.productName)}</strong>
              <span>Series</span><strong>{nvl(product?.series)}</strong>
              <span>End of Sale</span><strong>{nvl(product?.endOfSaleDate)}</strong>
              <span>SW Maintenance</span><strong>{nvl(product?.endOfSwMaintenance)}</strong>
              <span>Security Support</span><strong>{nvl(product?.endOfSecuritySupport)}</strong>
              <span>Last Support</span><strong>{nvl(product?.lastDateOfSupport)}</strong>
            </div>
          </div>
          <div className="summary-card">
            <h3>Announcement</h3>
            {(evidence.announcements || []).slice(0, 3).map((announcement) => (
              <div className="announcement-block" key={announcement.id}>
                <strong>{nvl(announcement.announcementName || announcement.title)}</strong>
                <p>{nvl(announcement.technology)} · {nvl(announcement.series)}</p>
                {announcement.announcementUrl && <a href={announcement.announcementUrl} target="_blank" rel="noreferrer">Open Cisco page</a>}
              </div>
            ))}
            {!evidence.announcements?.length && <p className="hint">No announcement row linked yet.</p>}
          </div>
        </div>
      )}
      {evidence?.affectedProducts?.length > 0 && (
        <div className="raw-section">
          <h3>Affected product rows</h3>
          <SimpleTable rows={evidence.affectedProducts.map((item) => ({ pid: item.pid, description: item.productDescription, table: item.tableIndex, row: item.rowIndex, source: item.source, ...extractColumnPreview(item.payload) }))} />
        </div>
      )}
      {tables.length > 0 && (
        <div className="raw-section">
          <div className="table-tabs">
            {tables.map((table, index) => <button className={index === activeTable ? 'active-tab' : 'secondary'} type="button" key={table.id} onClick={() => setActiveTable(index)}>Table {table.tableIndex}</button>)}
          </div>
          <RawCiscoTable table={tables[activeTable]} />
        </div>
      )}
    </section>
  );
}

function extractColumnPreview(payload) {
  const columns = payload?.columns || payload?.affected_product_row?.columns || payload || {};
  const output = {};
  Object.entries(columns || {}).slice(0, 6).forEach(([key, value]) => { output[key] = value; });
  return output;
}

function RawCiscoTable({ table }) {
  if (!table) return null;
  const headers = Array.isArray(table.headers) && table.headers.length ? table.headers : inferHeaders(table.rows || []);
  const rows = Array.isArray(table.rows) ? table.rows : [];
  return (
    <div className="raw-table-card">
      <div className="raw-table-heading">
        <div><h3>{table.heading || table.caption || `Cisco table ${table.tableIndex}`}</h3><p className="hint">Announcement ID {table.announcementId} · {rows.length} row(s)</p></div>
      </div>
      <div className="table-wrap raw-table-wrap">
        <table>
          <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
          <tbody>
            {rows.map((row, index) => {
              const columns = row.columns || row;
              return <tr key={row.row_index || index}>{headers.map((header) => <td key={header}>{formatValue(columns?.[header])}</td>)}</tr>;
            })}
            {!rows.length && <tr><td colSpan={Math.max(headers.length, 1)} className="empty-cell">No rows saved for this table.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function inferHeaders(rows) {
  const headers = new Set();
  rows.forEach((row) => Object.keys(row?.columns || row || {}).forEach((key) => headers.add(key)));
  return Array.from(headers).slice(0, 40);
}

function DatabaseExplorer({ setError, setEvidencePid }) {
  const [dataset, setDataset] = useState('products');
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(25);
  const [rows, setRows] = useState([]);

  async function run(event) {
    event?.preventDefault();
    setError('');
    try {
      const variables = ['checkpoints', 'system_events'].includes(dataset) ? { limit: Number(limit) } : { search: search || null, limit: Number(limit) };
      const data = await graphqlRequest(graphQueries[dataset], variables);
      const key = Object.keys(data.data || {})[0];
      setRows(data?.data?.[key] || []);
    } catch (error) {
      setError(error.message);
    }
  }

  useEffect(() => { run(); }, [dataset]);

  const columns = useMemo(() => rows.length ? Object.keys(rows[0]).filter((key) => !['payload', 'rawResponse'].includes(key)).slice(0, 10) : [], [rows]);

  return (
    <section className="panel wide-panel">
      <div className="panel-heading"><div><p className="eyebrow">Database</p><h2>Browse saved records</h2><p className="muted">This view uses GraphQL. Missing fields are displayed as N/A.</p></div></div>
      <form className="search-row" onSubmit={run}>
        <select value={dataset} onChange={(event) => setDataset(event.target.value)}>{datasets.map((item) => <option value={item} key={item}>{item.replaceAll('_', ' ')}</option>)}</select>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search PID, announcement, status, technology" />
        <input className="short-input" type="number" min="1" max="500" value={limit} onChange={(event) => setLimit(event.target.value)} />
        <button type="submit">Search DB</button>
      </form>
      <SimpleTable rows={rows} columns={columns} actions={(row) => row.pid ? <button className="secondary small-button" type="button" onClick={() => setEvidencePid(row.pid)}>Evidence</button> : null} />
    </section>
  );
}

function ExportPanel({ notify, setError }) {
  const [dataset, setDataset] = useState('eox_report');
  const [format, setFormat] = useState('xlsx');
  const [search, setSearch] = useState('');
  const [fields, setFields] = useState([]);
  const [selectedFields, setSelectedFields] = useState([]);
  const [includeAll, setIncludeAll] = useState(false);

  async function loadOptions(targetDataset = dataset, targetSearch = search) {
    setError('');
    try {
      const data = await getExportOptions(targetDataset, targetSearch);
      const available = data.fields || [];
      setFields(available);
      setSelectedFields(data.default_fields || available.filter((item) => item.default).map((item) => item.key));
    } catch (error) {
      setError(error.message);
      setFields([]);
      setSelectedFields([]);
    }
  }

  useEffect(() => { loadOptions(dataset, search); }, [dataset]);

  function toggleField(key) {
    setSelectedFields((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  function selectDefaults() {
    setIncludeAll(false);
    setSelectedFields(fields.filter((item) => item.default).map((item) => item.key));
  }

  function selectCore() {
    setIncludeAll(false);
    setSelectedFields(fields.filter((item) => ['Core', 'Lifecycle', 'Replacement', 'Source'].includes(item.group)).map((item) => item.key));
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    try {
      const chosen = includeAll ? [] : selectedFields;
      if (!includeAll && !chosen.length) {
        setError('Select at least one column or choose All available columns.');
        return;
      }
      await downloadExport(dataset, format, search, 10000, chosen, includeAll);
      notify(`Downloaded ${dataset.replaceAll('_', ' ')} as ${format.toUpperCase()}`);
    } catch (error) {
      setError(error.message);
    }
  }

  const grouped = fields.reduce((acc, field) => {
    const group = field.group || 'Other';
    acc[group] = acc[group] || [];
    acc[group].push(field);
    return acc;
  }, {});

  return (
    <section className="panel wide-panel export-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Reports</p>
          <h2>Download CSV / Excel</h2>
          <p className="muted">Choose only the columns people need. Cisco table columns appear here automatically after Auto_Pop stores them in the DB.</p>
        </div>
      </div>
      <form className="export-form" onSubmit={submit}>
        <div className="search-row">
          <select value={dataset} onChange={(event) => setDataset(event.target.value)}>{datasets.filter((item) => !['checkpoints', 'system_events'].includes(item)).map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select>
          <select value={format} onChange={(event) => setFormat(event.target.value)}><option value="xlsx">Excel</option><option value="csv">CSV</option></select>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Optional PID/status/technology filter" />
          <button className="secondary" type="button" onClick={() => loadOptions(dataset, search)}>Refresh columns</button>
          <button type="submit">Download</button>
        </div>
        <div className="button-row field-actions">
          <label className="checkbox-row"><input type="checkbox" checked={includeAll} onChange={(event) => setIncludeAll(event.target.checked)} />All available columns</label>
          <button className="secondary small-button" type="button" onClick={selectDefaults}>Recommended</button>
          <button className="secondary small-button" type="button" onClick={selectCore}>Core + lifecycle</button>
          <span className="hint">Selected: {includeAll ? 'all' : selectedFields.length}</span>
        </div>
        {!includeAll && (
          <div className="field-groups">
            {Object.entries(grouped).map(([group, items]) => (
              <div className="field-group" key={group}>
                <h4>{group}</h4>
                <div className="field-checkboxes">
                  {items.map((field) => (
                    <label className="checkbox-row field-check" key={field.key}>
                      <input type="checkbox" checked={selectedFields.includes(field.key)} onChange={() => toggleField(field.key)} />
                      <span>{field.label || field.key}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {!fields.length && <p className="hint">No columns detected yet. Run Auto_Pop or search and save a PID first.</p>}
          </div>
        )}
      </form>
    </section>
  );
}

function StatsPanel({ stats, refreshStats }) {
  const metrics = [
    ['Products', stats?.totalProducts ?? 0],
    ['Announcements', stats?.totalAnnouncements ?? 0],
    ['Cisco tables', stats?.totalAnnouncementTables ?? 0],
    ['Affected rows', stats?.totalAffectedProducts ?? 0],
    ['PID catalog', stats?.totalCatalogEntries ?? 0],
    ['Auto_Pop jobs', stats?.totalAutopopJobs ?? 0]
  ];
  return (
    <section className="panel stats-panel">
      <div className="panel-heading"><div><p className="eyebrow">Snapshot</p><h2>Local DB</h2></div><button className="secondary" type="button" onClick={refreshStats}>Refresh</button></div>
      <div className="metric-grid">{metrics.map(([name, value]) => <div className="metric" key={name}><span>{name}</span><strong>{value}</strong></div>)}</div>
    </section>
  );
}

function MessageBar({ error, message, loading, clear }) {
  if (!error && !message && !loading) return null;
  return (
    <section className="message-bar">
      {loading && <span className="notice">Working...</span>}
      {message && <span className="notice success">{message}</span>}
      {error && <span className="notice error">{error}</span>}
      <button className="secondary small-button" type="button" onClick={clear}>Clear</button>
    </section>
  );
}

function SimpleTable({ rows, columns, actions }) {
  const cols = columns?.length ? columns : rows?.length ? Object.keys(rows[0]).slice(0, 8) : [];
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map((column) => <th key={column}>{column}</th>)}{actions && <th>Action</th>}</tr></thead>
        <tbody>
          {(rows || []).map((row, index) => <tr key={row.id || `${row.pid || row.scopeKey || 'row'}-${index}`}>{cols.map((column) => <td key={column}>{formatValue(row[column])}</td>)}{actions && <td>{actions(row)}</td>}</tr>)}
          {(!rows || !rows.length) && <tr><td colSpan={Math.max(cols.length + (actions ? 1 : 0), 1)} className="empty-cell">No rows loaded.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const { setup, stats, refreshSetup, refreshStats } = useAppStatus();
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [evidencePid, setEvidencePid] = useState('');

  function notify(text) {
    setMessage(text);
    setTimeout(() => setMessage(''), 4500);
  }

  useEffect(() => {
    refreshSetup();
    refreshStats();
    const onError = (event) => logFrontendEvent('error', 'frontend_window_error', event.message || 'Window error', { filename: event.filename, lineno: event.lineno });
    const onUnhandled = (event) => logFrontendEvent('error', 'frontend_unhandled_rejection', String(event.reason || 'Unhandled promise rejection'));
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onUnhandled);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onUnhandled);
    };
  }, []);

  return (
    <main>
      <header className="hero">
        <div><p className="eyebrow">Free Cisco lifecycle tool</p><h1>Cisco EOX Manager</h1><p>Search PIDs, save missing EOX data automatically, browse raw Cisco tables, and export reports from your local database.</p></div>
        <div className="hero-actions"><a href="/docs" target="_blank" rel="noreferrer">API docs</a><a href="/graphql" target="_blank" rel="noreferrer">GraphQL</a></div>
      </header>
      <MessageBar error={error} message={message} loading={loading} clear={() => { setError(''); setMessage(''); }} />
      <section className="grid two-columns"><DatabaseSetupCard setup={setup} refreshSetup={refreshSetup} refreshStats={refreshStats} notify={notify} setError={setError} setLoading={setLoading} /><StatsPanel stats={stats} refreshStats={refreshStats} /></section>
      <SearchPanel refreshStats={refreshStats} notify={notify} setError={setError} setLoading={setLoading} setEvidencePid={setEvidencePid} />
      <section className="grid two-columns"><AutoPopPanel setup={setup} refreshStats={refreshStats} notify={notify} setError={setError} /><OptionalApiCard setup={setup} refreshSetup={refreshSetup} notify={notify} setError={setError} setLoading={setLoading} /></section>
      <EvidencePanel pid={evidencePid} setPid={setEvidencePid} setError={setError} />
      <DatabaseExplorer setError={setError} setEvidencePid={setEvidencePid} />
      <ExportPanel notify={notify} setError={setError} />
    </main>
  );
}
