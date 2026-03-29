import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './AuditLogs.css';

const AuditLogs = () => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const API_URL = 'http://localhost:8000/api';

    useEffect(() => {
        fetchLogs();
    }, []);

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_URL}/logs?limit=50`);
            setLogs(res.data);
        } catch (err) {
            console.error(err);
        }
        setLoading(false);
    };

    return (
        <div className="logs-container animate-fade">
            <header className="logs-header">
                <h1>Audit Logs</h1>
                <p className="subtitle">Accounting & Traceability Engine</p>
                <button className="refresh-btn" onClick={fetchLogs}>🔄 Refresh Logs</button>
            </header>

            <div className="logs-table-wrapper glass">
                <table className="logs-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Type</th>
                            <th>Message</th>
                        </tr>
                    </thead>
                    <tbody>
                        {logs.map((log) => (
                            <tr key={log.id}>
                                <td className="log-time">{new Date(log.timestamp).toLocaleString()}</td>
                                <td>
                                    <span className={`log-badge ${log.event_type.toLowerCase()}`}>
                                        {log.event_type}
                                    </span>
                                </td>
                                <td className="log-msg">{log.message}</td>
                            </tr>
                        ))}
                        {logs.length === 0 && !loading && (
                            <tr><td colSpan="3" style={{textAlign: 'center', padding: '2rem'}}>No logs found.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default AuditLogs;
