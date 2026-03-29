import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler,
} from 'chart.js';
import './Dashboard.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const Dashboard = ({ deviceId, onBack, theme }) => {
    const [metrics, setMetrics] = useState({ timestamps: [], sysUpTime: [], in_traffic: [], out_traffic: [] });
    const [device, setDevice] = useState(null);
    const [loading, setLoading] = useState(true);
    const [polling, setPolling] = useState(false);
    const API_URL = 'http://localhost:8000/api';

    useEffect(() => {
        fetchDevice();
        fetchMetrics();
        const interval = setInterval(fetchMetrics, 30000); // 30s refresh
        return () => clearInterval(interval);
    }, [deviceId]);

    const fetchDevice = async () => {
        try {
            const res = await axios.get(`${API_URL}/devices`);
            const d = res.data.find(x => x.id === deviceId);
            setDevice(d);
        } catch (err) { console.error(err); }
    };

    const fetchMetrics = async () => {
        try {
            const res = await axios.get(`${API_URL}/devices/${deviceId}/metrics?limit=50`);
            setMetrics(res.data);
        } catch (err) {
            console.error(err);
        }
        setLoading(false);
    };

    const onForcePoll = async () => {
        setPolling(true);
        try {
            await axios.post(`${API_URL}/devices/${deviceId}/poll`);
            await fetchDevice();
            await fetchMetrics();
            alert('Manual health check and inventory complete.');
        } catch (err) {
            console.error(err);
        }
        setPolling(false);
    };

    const isLight = theme === 'light';
    const textColor = isLight ? '#4a4a4a' : '#bfbfbf';
    const gridColor = isLight ? 'rgba(0,0,0,0.06)' : 'rgba(255,255,255,0.08)';

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top', labels: { color: textColor, font: { weight: '600' } } },
            tooltip: { 
                mode: 'index', 
                intersect: false, 
                backgroundColor: isLight ? 'rgba(255,255,255,0.95)' : 'rgba(20,20,30,0.95)',
                titleColor: '#3b82f6',
                bodyColor: isLight ? '#1a1a1a' : '#ffffff',
                borderWidth: 1,
                borderColor: isLight ? '#e0e0e0' : 'rgba(255,255,255,0.1)',
            },
        },
        scales: {
            x: { 
                grid: { display: false }, 
                ticks: { color: textColor, maxTicksLimit: 8, font: { weight: '500' } } 
            },
            y: { 
                grid: { color: gridColor }, 
                ticks: { color: textColor, font: { weight: '500' } } 
            }
        },
        interaction: { mode: 'nearest', axis: 'x', intersect: false }
    };

    const mainChartData = {
        labels: metrics.timestamps.slice().reverse(),
        datasets: [
            {
                label: 'Inbound Traffic (Bps)',
                data: metrics.in_traffic?.slice().reverse(),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59,130,246,0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 0,
            },
            {
                label: 'Outbound Traffic (Bps)',
                data: metrics.out_traffic?.slice().reverse(),
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239,68,68,0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 0,
            }
        ],
    };

    return (
        <div className="dashboard-container animate-fade">
            <header className="dashboard-header">
                <button className="back-btn" onClick={onBack}>← Sidebar</button>
                <div className="header-titles">
                    <h1>{device?.name || 'Performance Analytics'}</h1>
                    <p className="subtitle">ID: {device?.id} • IP: {device?.ip} • MAC: <span className="mac-val">{device?.mac_address || 'Unassigned'}</span></p>
                </div>
                <div className="header-actions">
                    <button className={`force-btn glass ${polling ? 'loading' : ''}`} onClick={onForcePoll} disabled={polling}>
                        {polling ? '⚡ Polling...' : '🔄 Force Heavy Poll'}
                    </button>
                    <div className="live-status">
                        <span className="live-dot"></span> LIVE DATA
                    </div>
                </div>
            </header>

            <div className="analytics-layout">
                <div className="chart-section glass">
                    <div className="chart-header">
                        <h3>Bandwidth Utilization (FCAPS Accounting)</h3>
                        <div className="chart-legend-custom">
                             <span className="dot in"></span> Inbound
                             <span className="dot out"></span> Outbound
                        </div>
                    </div>
                    <div className="chart-wrapper">
                        {loading ? <p>Loading throughput charts...</p> : <Line data={mainChartData} options={chartOptions} />}
                    </div>
                </div>

                <div className="metrics-side">
                    <div className="mini-stat glass">
                         <span className="label">Peak Throughput</span>
                         <span className="value">4.2 Gbps</span>
                         <span className="trend positive">↑ 12% vs last hour</span>
                    </div>
                    <div className="mini-stat glass">
                         <span className="label">Uptime Delta</span>
                         <span className="value">+32h 12m</span>
                         <span className="trend positive">↑ Stable</span>
                    </div>
                </div>
            </div>

            <section className="history-section glass">
                <h3>Historical Metric Audit</h3>
                <div className="history-table-wrapper scroll-thin">
                    <table className="history-table">
                        <thead>
                            <tr><th>Polling Timestamp</th><th>sysUpTime</th><th>In_Octets</th><th>Out_Octets</th></tr>
                        </thead>
                        <tbody>
                            {metrics.timestamps.slice(0, 15).map((ts, idx) => (
                                <tr key={idx}>
                                    <td>{ts}</td>
                                    <td>{metrics.sysUpTime[idx]}</td>
                                    <td>{metrics.in_traffic ? metrics.in_traffic[idx] : '-'}</td>
                                    <td>{metrics.out_traffic ? metrics.out_traffic[idx] : '-'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
};

export default Dashboard;