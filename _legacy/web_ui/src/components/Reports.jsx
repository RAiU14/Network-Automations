import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Reports.css';

const Reports = () => {
    const [ticket, setTicket] = useState('');
    const [technology, setTechnology] = useState('Switches');
    const [file, setFile] = useState(null);
    const [status, setStatus] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const API_URL = '/api';

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) return;

        setIsUploading(true);
        const formData = new FormData();
        formData.append('ticket', ticket);
        formData.append('technology', technology);
        formData.append('file', file);

        try {
            const res = await axios.post(`${API_URL}/reports/`, formData);
            setStatus({ status: 'processing', message: 'Upload successful. Processing logs...' });
        } catch (err) {
            console.error(err);
            setStatus({ status: 'failed', message: 'Upload failed. Check server logs.' });
        }
        setIsUploading(false);
    };

    return (
        <div className="reports-container animate-fade">
            <header className="reports-header">
                <h1>Reporting Pipeline</h1>
                <p className="subtitle">Analyze bulk network logs and generate audit reports</p>
            </header>

            <div className="reports-grid">
                <section className="upload-section glass">
                    <h2>📁 Submit New Task</h2>
                    <form onSubmit={handleUpload}>
                        <div className="form-group">
                            <label>Ticket Number (e.g., SVR12345)</label>
                            <input 
                                type="text" 
                                value={ticket} 
                                onChange={(e) => setTicket(e.target.value)} 
                                placeholder="SVR..."
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Technology</label>
                            <select value={technology} onChange={(e) => setTechnology(e.target.value)}>
                                <option>Wireless</option>
                                <option>Switches</option>
                                <option>Security</option>
                                <option>Others</option>
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Log Archive (.zip)</label>
                            <input 
                                type="file" 
                                accept=".zip" 
                                onChange={(e) => setFile(e.target.files[0])}
                                required 
                            />
                        </div>
                        <button type="submit" className="upload-btn" disabled={isUploading}>
                            {isUploading ? '🚀 Uploading...' : '📤 Start Analysis'}
                        </button>
                    </form>
                </section>

                <section className="status-section glass">
                    <h2>📋 Active Pipelines</h2>
                    {status ? (
                        <div className={`status-card ${status.status}`}>
                            <div className="status-header">
                                <span className="ticket-id">{ticket}</span>
                                <span className="status-badge">{status.status}</span>
                            </div>
                            <p>{status.message}</p>
                            {status.status === 'completed' && (
                                <button className="download-btn">📥 Download Report</button>
                            )}
                        </div>
                    ) : (
                        <div className="empty-status">
                            <p>No active processing tasks. Upload logs to begin.</p>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
};

export default Reports;
