import React, { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from './MetricCard';
import './Overview.css';

const Overview = ({ onSelectDevice }) => {
  const [stats, setStats] = useState(null);
  const [recentDevices, setRecentDevices] = useState([]);
  const API_URL = 'http://localhost:8000/api';

  useEffect(() => {
    fetchStats();
    fetchRecentDevices();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_URL}/dashboard/stats`);
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats', err);
    }
  };

  const fetchRecentDevices = async () => {
    try {
      const res = await axios.get(`${API_URL}/devices`);
      setRecentDevices(res.data.slice(0, 5));
    } catch (err) {
      console.error('Failed to fetch devices', err);
    }
  };

  return (
    <div className="overview-container animate-fade">
      <header className="overview-header">
        <h1>Overview</h1>
        <p className="subtitle">Network Health & Accounting Dashboard</p>
      </header>

      <div className="metrics-grid">
        <MetricCard
          title="Total Devices"
          value={stats?.total_devices || 0}
          icon="🖥️"
          color="hsl(210, 100%, 50%)"
          subValue="Registered nodes"
        />
        <MetricCard
          title="Active Now"
          value={stats?.active_devices || 0}
          icon="🟢"
          color="hsl(150, 80%, 40%)"
          trend={+2.4}
          subValue="Live monitoring"
        />
        <MetricCard
          title="Polls (24h)"
          value={stats?.total_metrics_24h || 0}
          icon="⚡"
          color="hsl(30, 100%, 50%)"
          subValue="Metrics collected"
        />
        <MetricCard
          title="Health Score"
          value={stats?.health_score || 0}
          unit="%"
          icon="🛡️"
          color="hsl(280, 80%, 50%)"
          trend={-0.5}
          subValue="Network stability"
        />
      </div>

      <div className="overview-content">
        <div className="section recently-polled glass">
          <h3>Recently Active Devices</h3>
          <div className="device-list-mini">
            {recentDevices.map(device => (
              <div key={device.id} className="device-item-mini" onClick={() => onSelectDevice(device.id)}>
                <div className="status-dot"></div>
                <div className="device-info">
                  <span className="device-name">{device.name}</span>
                  <span className="device-ip">{device.ip}</span>
                </div>
                <button className="view-btn">View Metrics</button>
              </div>
            ))}
          </div>
        </div>

        <div className="section quick-actions glass">
          <h3>Quick Accounting</h3>
          <div className="actions-grid">
            <div className="action-card">
              <span className="action-icon">💸</span>
              <span>Billing Export</span>
            </div>
            <div className="action-card">
              <span className="action-icon">📊</span>
              <span>Usage Report</span>
            </div>
            <div className="action-card">
              <span className="action-icon">🛠️</span>
              <span>Maint. Mode</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Overview;
