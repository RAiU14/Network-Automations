import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bar, Pie } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    Title,
    Tooltip,
    Legend,
    ArcElement,
} from 'chart.js';
import './Analytics.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend, ArcElement);

const Analytics = ({ theme }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const API_URL = 'http://localhost:8000/api';

    useEffect(() => {
        fetchAnalytics();
    }, []);

    const fetchAnalytics = async () => {
        try {
            const res = await axios.get(`${API_URL}/analytics`);
            setData(res.data);
        } catch (err) {
            console.error(err);
        }
        setLoading(false);
    };

    if (loading) return <div className="loader">Aggregating big data performance...</div>;

    const isLight = theme === 'light';
    const textColor = isLight ? '#4a4a4a' : '#bfbfbf';

    const barOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: { 
                backgroundColor: isLight ? '#fff' : '#14141e',
                titleColor: '#3b82f6',
                bodyColor: isLight ? '#1a1a1a' : '#fff',
                borderColor: isLight ? '#e0e0e0' : '#333',
                borderWidth: 1 
            }
        },
        scales: {
            x: { ticks: { color: textColor, font: { weight: '600' } }, grid: { display: false } },
            y: { ticks: { color: textColor }, grid: { color: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)' } }
        }
    };

    const barData = {
        labels: data?.bandwidth_peaks.map(p => p.name) || [],
        datasets: [{
            label: 'Peak Throughput (Bps)',
            data: data?.bandwidth_peaks.map(p => p.peak) || [],
            backgroundColor: 'hsla(210, 100%, 50%, 0.6)',
            borderColor: 'hsl(210, 100%, 50%)',
            borderWidth: 1,
        }]
    };

    const pieData = {
        labels: ['Up', 'Down'],
        datasets: [{
            data: [data?.uptime_stats.up, data?.uptime_stats.total - data?.uptime_stats.up],
            backgroundColor: ['#10b981', '#ef4444'],
            borderWidth: 0,
        }]
    };

    return (
        <div className="analytics-container animate-fade">
            <header className="analytics-header">
                <h1>Network Analytics</h1>
                <p className="subtitle">Historical Trends & Inventory Intelligence</p>
            </header>

            <div className="analytics-grid">
                <div className="chart-large glass">
                    <h3>Bandwidth Heavy Hitters (Top 5 Devices)</h3>
                    <div className="chart-container">
                         <Bar data={barData} options={barOptions} />
                    </div>
                </div>

                <div className="summary-side">
                    <div className="chart-small glass">
                        <h3>Uptime Distribution</h3>
                        <div className="pie-wrapper">
                             <Pie data={pieData} />
                        </div>
                        <div className="pie-labels">
                             <span className="percentage">{data?.uptime_stats.percentage.toFixed(1)}%</span>
                             <span className="label">Network Availability</span>
                        </div>
                    </div>

                    <div className="recent-activity glass">
                        <h3>Inventory Activity</h3>
                        <div className="activity-list scroll-thin">
                            {data?.recent_activity.map((log, i) => (
                                <div key={i} className="activity-item">
                                    <span className="time">{new Date(log.timestamp).toLocaleTimeString()}</span>
                                    <span className="msg">{log.message}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Analytics;
