import React, { useState } from 'react';
import axios from 'axios';
import './EOX.css';

const EOX = () => {
    const [pid, setPid] = useState('');
    const [results, setResults] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const API_URL = '/api';

    const checkEox = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            // First check the announcement link (simulation of finding the link)
            const res = await axios.post(`${API_URL}/eox/check/`, { product_link: pid });
            setResults({
                pid: pid,
                status: 'Under Review',
                milestones: res.data.announcement ? [
                    { label: 'Announcement', date: res.data.announcement.title }
                ] : [{ label: 'Status', date: 'No active EOX notices found' }]
            });
        } catch (err) {
            console.error(err);
        }
        setIsLoading(false);
    };

    return (
        <div className="eox-container animate-fade">
            <header className="eox-header">
                <h1>Cisco EOX Scraper</h1>
                <p className="subtitle">Lifecycle analysis and End-of-Life milestone tracking</p>
            </header>

            <div className="eox-grid">
                <section className="search-section glass">
                    <h2>🔍 Quick Check</h2>
                    <form onSubmit={checkEox}>
                        <div className="form-group">
                            <label>Product ID (PID)</label>
                            <input 
                                type="text" 
                                value={pid} 
                                onChange={(e) => setPid(e.target.value)} 
                                placeholder="e.g. C9200L-24T-4G"
                                required
                            />
                        </div>
                        <button type="submit" className="check-btn" disabled={isLoading}>
                            {isLoading ? '📡 Checking...' : '🔎 Check Lifecycle'}
                        </button>
                    </form>
                </section>

                <section className="results-section glass">
                    <h2>📊 Milestone Details</h2>
                    {results ? (
                        <div className="eox-results">
                            <div className="result-hero">
                                <span className="pid-badge">{results.pid}</span>
                                <span className="status-label">{results.status}</span>
                            </div>
                            <div className="milestone-list">
                                {results.milestones.map((m, idx) => (
                                    <div key={idx} className="milestone-item">
                                        <span className="m-label">{m.label}</span>
                                        <span className="m-date">{m.date}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="empty-results">
                            <p>Enter a Cisco PID above to analyze lifecycle milestones.</p>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
};

export default EOX;
