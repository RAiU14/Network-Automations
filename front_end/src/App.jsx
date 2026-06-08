import { useMemo, useState } from 'react';
import { apiRequest, downloadJson, parsePids } from './api.js';

const initialPidInput = 'C9300-24T\nISR4331/K9';
const initialSoftwareInput = JSON.stringify(
  {
    'C9300-24T': ['17.9.4'],
    'ISR4331/K9': '17.6.5'
  },
  null,
  2
);

function ResultPanel({ title, result, error, loading, onClear }) {
  return (
    <section className="panel result-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Output</p>
          <h2>{title}</h2>
        </div>
        <div className="button-row">
          <button className="secondary" type="button" onClick={onClear} disabled={!result && !error}>
            Clear
          </button>
          <button
            className="secondary"
            type="button"
            onClick={() => downloadJson('cisco-eox-result.json', result)}
            disabled={!result}
          >
            Download JSON
          </button>
        </div>
      </div>

      {loading && <div className="status loading">Running lookup...</div>}
      {error && <div className="status error">{error}</div>}
      {!loading && !error && !result && (
        <div className="empty-state">
          Run a lookup to see the response from the EOX backend here.
        </div>
      )}
      {result && <pre className="json-output">{JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}

function PidLookupCard({ setResult, setError, setLoading }) {
  const [pids, setPids] = useState(initialPidInput);
  const [technology, setTechnology] = useState('Routing and Switching');
  const [useCache, setUseCache] = useState(true);

  const parsedPids = useMemo(() => parsePids(pids), [pids]);

  async function handleSubmit(event) {
    event.preventDefault();
    setResult(null);
    setError('');

    if (parsedPids.length === 0) {
      setError('Enter at least one Cisco PID or model number.');
      return;
    }

    setLoading(true);
    try {
      const data = await apiRequest('/eox/lookup-pids', {
        method: 'POST',
        body: JSON.stringify({
          pids: parsedPids,
          technology,
          use_cache: useCache
        })
      });
      setResult(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Scraper workflow</p>
      <h2>Lookup EOX by PID</h2>
      <p className="muted">
        Uses the scraper-compatible backend. Cache mode checks local data first; online mode attempts Cisco page scraping.
      </p>

      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Product IDs / models
          <textarea
            rows="7"
            value={pids}
            onChange={(event) => setPids(event.target.value)}
            placeholder="C9300-24T, ISR4331/K9"
          />
        </label>

        <label>
          Technology/category
          <input value={technology} onChange={(event) => setTechnology(event.target.value)} />
        </label>

        <label className="checkbox-row">
          <input type="checkbox" checked={useCache} onChange={(event) => setUseCache(event.target.checked)} />
          Use local EOX cache when available
        </label>

        <div className="button-row">
          <button type="submit">Run PID lookup</button>
          <span className="hint">{parsedPids.length} PID{parsedPids.length === 1 ? '' : 's'} detected</span>
        </div>
      </form>
    </section>
  );
}

function HardwareApiCard({ setResult, setError, setLoading }) {
  const [pids, setPids] = useState(initialPidInput);
  const parsedPids = useMemo(() => parsePids(pids), [pids]);

  async function handleSubmit(event) {
    event.preventDefault();
    setResult(null);
    setError('');

    if (parsedPids.length === 0) {
      setError('Enter at least one Cisco PID or model number.');
      return;
    }

    setLoading(true);
    try {
      const data = await apiRequest('/eox/hardware-milestones', {
        method: 'POST',
        body: JSON.stringify({ pids: parsedPids })
      });
      setResult(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Cisco API workflow</p>
      <h2>Hardware EOX milestones</h2>
      <p className="muted">
        Requires Cisco API credentials configured on the backend. Useful when official API access is available.
      </p>

      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Product IDs / models
          <textarea rows="7" value={pids} onChange={(event) => setPids(event.target.value)} />
        </label>

        <div className="button-row">
          <button type="submit">Fetch hardware milestones</button>
          <span className="hint">{parsedPids.length} PID{parsedPids.length === 1 ? '' : 's'} detected</span>
        </div>
      </form>
    </section>
  );
}

function SoftwareApiCard({ setResult, setError, setLoading }) {
  const [deviceVersions, setDeviceVersions] = useState(initialSoftwareInput);

  async function handleSubmit(event) {
    event.preventDefault();
    setResult(null);
    setError('');

    let parsed;
    try {
      parsed = JSON.parse(deviceVersions);
    } catch (error) {
      setError(`Invalid JSON: ${error.message}`);
      return;
    }

    setLoading(true);
    try {
      const data = await apiRequest('/eox/software-milestones', {
        method: 'POST',
        body: JSON.stringify({ device_versions: parsed })
      });
      setResult(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <p className="eyebrow">Cisco API workflow</p>
      <h2>Software milestones</h2>
      <p className="muted">
        Submit a JSON mapping of PID/model to one or more software versions.
      </p>

      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Device versions JSON
          <textarea
            className="code-input"
            rows="9"
            value={deviceVersions}
            onChange={(event) => setDeviceVersions(event.target.value)}
          />
        </label>

        <button type="submit">Fetch software milestones</button>
      </form>
    </section>
  );
}

function AdvancedToolsCard({ setResult, setError, setLoading }) {
  const [pid, setPid] = useState('C9300-24T');
  const [technology, setTechnology] = useState('Routing and Switching');
  const [productLink, setProductLink] = useState('');
  const [redirectLink, setRedirectLink] = useState('');
  const [announcementLink, setAnnouncementLink] = useState('');

  async function runRequest(path, payload) {
    setResult(null);
    setError('');
    setLoading(true);
    try {
      const data = await apiRequest(path, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setResult(data);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel wide-panel">
      <p className="eyebrow">Advanced scraper tools</p>
      <h2>Direct EOX actions</h2>
      <p className="muted">
        Use these when you already have a Cisco product page, redirect page, or EOX announcement URL.
      </p>

      <div className="advanced-grid">
        <form
          className="mini-form"
          onSubmit={(event) => {
            event.preventDefault();
            runRequest('/eox/find-series-link', { pid, technology });
          }}
        >
          <h3>Find series link</h3>
          <label>
            PID/model
            <input value={pid} onChange={(event) => setPid(event.target.value)} />
          </label>
          <label>
            Technology
            <input value={technology} onChange={(event) => setTechnology(event.target.value)} />
          </label>
          <button type="submit">Find link</button>
        </form>

        <form
          className="mini-form"
          onSubmit={(event) => {
            event.preventDefault();
            runRequest('/eox/check-product', { product_link: productLink });
          }}
        >
          <h3>Check product page</h3>
          <label>
            Product page link
            <input
              value={productLink}
              onChange={(event) => setProductLink(event.target.value)}
              placeholder="/c/en/us/support/... or https://www.cisco.com/..."
            />
          </label>
          <button type="submit" disabled={!productLink.trim()}>
            Check product
          </button>
        </form>

        <form
          className="mini-form"
          onSubmit={(event) => {
            event.preventDefault();
            runRequest('/eox/details', { redirect_link: redirectLink });
          }}
        >
          <h3>Extract announcement URLs</h3>
          <label>
            Redirect/details link
            <input
              value={redirectLink}
              onChange={(event) => setRedirectLink(event.target.value)}
              placeholder="Cisco EOX details/redirect link"
            />
          </label>
          <button type="submit" disabled={!redirectLink.trim()}>
            Extract URLs
          </button>
        </form>

        <form
          className="mini-form"
          onSubmit={(event) => {
            event.preventDefault();
            runRequest('/eox/scrape', { announcement_link: announcementLink });
          }}
        >
          <h3>Scrape announcement</h3>
          <label>
            Announcement link
            <input
              value={announcementLink}
              onChange={(event) => setAnnouncementLink(event.target.value)}
              placeholder="Cisco EOX announcement URL"
            />
          </label>
          <button type="submit" disabled={!announcementLink.trim()}>
            Scrape details
          </button>
        </form>
      </div>
    </section>
  );
}

export default function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const sharedProps = { setResult, setError, setLoading };

  return (
    <main>
      <header className="hero">
        <div>
          <p className="eyebrow">Cisco Automations</p>
          <h1>EOX lookup console</h1>
          <p>
            Search Cisco End-of-Life details through the scraper workflow or the optional Cisco API-backed endpoints.
          </p>
        </div>
        <div className="hero-card">
          <strong>Backend</strong>
          <span>FastAPI: <code>/eox</code></span>
          <span>Docs: <code>/docs</code></span>
        </div>
      </header>

      <div className="layout">
        <div className="cards-grid">
          <PidLookupCard {...sharedProps} />
          <HardwareApiCard {...sharedProps} />
          <SoftwareApiCard {...sharedProps} />
          <AdvancedToolsCard {...sharedProps} />
        </div>

        <ResultPanel
          title="Backend response"
          result={result}
          error={error}
          loading={loading}
          onClear={() => {
            setResult(null);
            setError('');
          }}
        />
      </div>
    </main>
  );
}
